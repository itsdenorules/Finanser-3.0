from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, User, Transaction
from ai_service import process_receipt_image
from passlib.context import CryptContext
from jose import jwt, JWTError
import io
import os
from PIL import Image
from pydantic import BaseModel
from typing import List
import json

# Üretim için Şifreleme ve Token Ayarları
SECRET_KEY = os.environ.get("SECRET_KEY", "bunu_vercel_de_degistir_cok_gizli_anahtar")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Finanser API")

# Üretim ortamı için CORS (Vercel domainini buraya ekleyeceğiz)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Üretime çıkarken burayı "https://finanser-six.vercel.app" yapacağız
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ŞİFRELEME VE GÜVENLİK FONKSİYONLARI ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Her işlemde kullanıcının kim olduğunu anlayan (Token çözen) fonksiyon
async def get_current_user(token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Geçersiz kimlik")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None: raise credentials_exception
    return user

# --- Pydantic Modelleri (Frontend'den gelen veriyi kontrol etmek için) ---
class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str
    referral_code: str = None

class UserLogin(BaseModel):
    email: str
    password: str

class TransactionCreate(BaseModel):
    date: str
    amount: float
    tax: float
    company: str
    type: str
    category: str
    description: str = ""

# --- 1. KAYIT OLMA (REGISTER) ---
@app.post("/api/auth/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(full_name=user.full_name, email=user.email, hashed_password=hashed_password, referral_code=user.referral_code)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Kayıt başarılı"}

# --- 2. GİRİŞ YAPMA (LOGIN) - Token Verir, Çıkış Yapılmaz ---
@app.post("/api/auth/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Hatalı email veya şifre")
    
    access_token = create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer", "user_name": db_user.full_name}

# --- 3. YAPAY ZEKA İLE FATURA OKUMA ---
@app.post("/api/analyze-receipt")
async def analyze_receipt(file: UploadFile = File(...)):
    if not file: raise HTTPException(status_code=400, detail="Dosya yok")
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        result_text = await process_receipt_image(image)
        # Gelen metni gerçek JSON nesnesine çeviriyoruz ki frontend kolay okusun
        return {"status": "success", "data": json.loads(result_text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. OKUNAN VEYA MANUEL GİRİLEN VERİYİ VERİTABANINA KAYDETME ---
@app.post("/api/transactions")
def create_transaction(transaction: TransactionCreate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db) # Kim olduğunu anla
    new_tx = Transaction(**transaction.dict(), user_id=user.id)
    db.add(new_tx)
    db.commit()
    return {"status": "success", "message": "İşlem kaydedildi"}

# --- 5. KULLANICININ KENDİ VERİLERİNİ ÇEKME (İşlemlerim Ekranı İçin) ---
@app.get("/api/transactions")
def get_transactions(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    return transactions

# --- 6. ADMİN BİLGİSİ (Kullanıcı Sayısı ve Toplam Tutar) ---
@app.get("/api/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    # Üretime alırken buraya ekstra bir "sadece admin görebilir" şifresi koyacağız
    total_users = db.query(User).count()
    all_transactions = db.query(Transaction).all()
    total_amount = sum(t.amount for t in all_transactions)
    return {"total_users": total_users, "total_document_amount": total_amount}
