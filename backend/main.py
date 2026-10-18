from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, User, Transaction, init_db
from ai_service import process_receipt_image
from passlib.context import CryptContext
from jose import jwt, JWTError
import io
import os
from PIL import Image
from pydantic import BaseModel
import json
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get("SECRET_KEY", "finanser_secret_key_2026")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Finanser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sunucu çökmelerini önlemek için güvenli veritabanı başlatma
@app.on_event("startup")
def on_startup():
    init_db()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

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

# API Test Rotaları
@app.get("/")
@app.get("/api")
@app.get("/api/")
def read_root():
    return {"status": "success", "message": "Finanser API Çalışıyor!"}

# Kayıt Olma (Çift Rota Desteği)
@app.post("/api/auth/register")
@app.post("/auth/register")
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

# Giriş Yapma (Çift Rota Desteği)
@app.post("/api/auth/login")
@app.post("/auth/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Hatalı email veya şifre")
    
    access_token = create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer", "user_name": db_user.full_name}

# Yapay Zeka Okuma
@app.post("/api/analyze-receipt")
@app.post("/analyze-receipt")
async def analyze_receipt(file: UploadFile = File(...)):
    if not file: raise HTTPException(status_code=400, detail="Dosya yok")
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        result_text = await process_receipt_image(image)
        return {"status": "success", "data": json.loads(result_text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# İşlem Kaydetme
@app.post("/api/transactions")
@app.post("/transactions")
def create_transaction(transaction: TransactionCreate, token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    new_tx = Transaction(**transaction.dict(), user_id=user.id)
    db.add(new_tx)
    db.commit()
    return {"status": "success", "message": "İşlem kaydedildi"}

# İşlemleri Çekme
@app.get("/api/transactions")
@app.get("/transactions")
def get_transactions(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    return transactions

# Admin Paneli
@app.get("/api/admin/stats")
@app.get("/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    all_transactions = db.query(Transaction).all()
    total_amount = sum(t.amount for t in all_transactions)
    return {"total_users": total_users, "total_document_amount": total_amount}
