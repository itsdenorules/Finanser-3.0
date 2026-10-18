from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import database as db
import ai_service as ai
from typing import Optional

app = FastAPI(title="Finanser API")

# Ön yüzün (HTML/JS) bu API'ye sorunsuzca bağlanabilmesi için CORS ayarları (Güvenlik Duvarı İzni)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Canlıya alırken buraya kendi domainini (ör: finanser.com) yazacağız
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Güvenlik: Token Kontrolü (Giriş Yapmış Mı?) ---
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Yetkisiz erisim. Lutfen giris yapin.")
    token = authorization.split(" ")[1]
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Gecersiz veya suresi dolmus oturum.")
    return user

# --- Veri Modelleri ---
class LoginRequest(BaseModel):
    email: str
    sifre: str

class RegisterRequest(BaseModel):
    ad: str
    email: str
    sifre: str
    ref_kodu: Optional[str] = ""

class ManualTransaction(BaseModel):
    tarih: str
    islem_tipi: str
    kategori: str
    firma: str
    tutar: float
    kdv: float
    aciklama: str

# --- SİSTEM BAŞLANGICI ---
@app.on_event("startup")
def startup_db():
    db.init_db() # Sunucu başlarken veritabanı tabloları yoksa otomatik kur

# --- UÇ NOKTALAR (ENDPOINTS - Sitenin Bağlanacağı Adresler) ---

@app.post("/api/auth/register")
def register(req: RegisterRequest):
    res = db.register_user(req.ad, req.email, req.sifre, req.ref_kodu)
    if not res["ok"]:
        raise HTTPException(status_code=400, detail=res["err"])
    return {"token": res["token"]}

@app.post("/api/auth/login")
def login(req: LoginRequest):
    res = db.login_user(req.email, req.sifre)
    if not res["ok"]:
        raise HTTPException(status_code=400, detail=res["err"])
    return {"token": res["token"]}

@app.get("/api/user/me")
def get_me(user: dict = Depends(get_current_user)):
    user.pop("sifre_hash", None) # Güvenlik için şifreyi gizle
    stats = db.get_user_stats(user["id"])
    return {"user": user, "stats": stats}

@app.post("/api/transactions/manual")
def add_manual(tx: ManualTransaction, user: dict = Depends(get_current_user)):
    # KOTA KONTROLÜ: Limit dolduysa işlemi reddet!
    if user["kullanilan_belge"] >= user["kota"]:
        raise HTTPException(status_code=403, detail="Kotaniz doldu. Lutfen paket yukseltin.")
    
    db.add_transaction(
        user["id"], tx.tarih, tx.islem_tipi, tx.kategori, tx.firma,
        tx.tutar, tx.kdv, tx.aciklama, "Manuel", "Manuel"
    )
    db.increment_belge(user["id"]) # Kotayı artır
    return {"ok": True, "msg": "Islem kaydedildi"}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    # KOTA KONTROLÜ (Yapay zeka için de geçerli)
    if user["kullanilan_belge"] >= user["kota"]:
        raise HTTPException(status_code=403, detail="Kotaniz doldu. Lutfen paket yukseltin.")
    
    contents = await file.read()
    ai_result = ai.process_document_with_ai(contents, file.content_type)
    
    if not ai_result["ok"]:
        raise HTTPException(status_code=500, detail=ai_result["err"])
    
    data = ai_result["data"]
    db.add_transaction(
        user["id"], data.get("tarih",""), data.get("islem_tipi",""), data.get("kategori",""),
        data.get("firma",""), data.get("tutar",0.0), data.get("kdv",0.0), data.get("aciklama",""),
        data.get("belge_turu",""), "Yapay Zeka"
    )
    db.increment_belge(user["id"]) # Kotayı artır
    
    return {"ok": True, "data": data}

@app.get("/api/transactions")
def get_transactions(user: dict = Depends(get_current_user)):
    return {"transactions": db.get_user_transactions(user["id"])}
