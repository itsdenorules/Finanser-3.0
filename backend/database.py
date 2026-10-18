from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import datetime

# .env dosyasından (Vercel ayarlarına gireceğin) veritabanı linki
DATABASE_URL = os.environ.get("DATABASE_URL") 

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# KULLANICI TABLOSU (Kayıt olanlar burada tutulacak)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    referral_code = Column(String, nullable=True)

# İŞLEMLER TABLOSU (Kullanıcıların fişleri/faturaları burada tutulacak, silinmeyecek)
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(String)
    amount = Column(Float)
    tax = Column(Float)
    company = Column(String)
    type = Column(String) # Gelir/Gider
    category = Column(String)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Veritabanı bağlantısını sağlayan fonksiyon
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
