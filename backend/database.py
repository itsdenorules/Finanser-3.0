# backend/database.py
import sqlite3
import hashlib
import uuid
import os
from datetime import datetime

DB_PATH = "finanser.db"
ADMIN_EMAIL = "denizzdinc@icloud.com"
VALID_REF_CODES = ["finans101", "finans102", "finans103"]

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "ad TEXT NOT NULL,"
        "email TEXT UNIQUE NOT NULL,"
        "sifre_hash TEXT NOT NULL,"
        "rol TEXT DEFAULT 'user',"
        "paket TEXT DEFAULT 'Ucretsiz',"
        "kota INTEGER DEFAULT 5,"
        "kullanilan_belge INTEGER DEFAULT 0,"
        "referans_kodu TEXT,"
        "session_token TEXT,"
        "created_at TEXT DEFAULT (datetime('now','localtime')))"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS transactions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL,"
        "tarih TEXT,"
        "islem_tipi TEXT,"
        "kategori TEXT,"
        "firma TEXT,"
        "tutar REAL DEFAULT 0,"
        "kdv REAL DEFAULT 0,"
        "aciklama TEXT,"
        "belge_turu TEXT,"
        "kaynak TEXT DEFAULT 'Manuel',"
        "created_at TEXT DEFAULT (datetime('now','localtime')),"
        "FOREIGN KEY (user_id) REFERENCES users(id))"
    )
    conn.commit()
    conn.close()

def hash_password(pw, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${h}"

def verify_password(pw, stored):
    parts = stored.split("$")
    if len(parts) != 2: return False
    return hash_password(pw, parts[0]) == stored

def generate_token():
    return uuid.uuid4().hex

# --- KULLANICI İŞLEMLERİ ---
def register_user(ad, email, pw, ref_code=""):
    conn = get_db()
    c = conn.cursor()
    try:
        rol = "admin" if email.lower() == ADMIN_EMAIL else "user"
        token = generate_token()
        c.execute(
            "INSERT INTO users (ad,email,sifre_hash,rol,referans_kodu,session_token) VALUES (?,?,?,?,?,?)",
            (ad, email.lower(), hash_password(pw), rol, ref_code, token)
        )
        conn.commit()
        uid = c.lastrowid
        return {"ok": True, "token": token, "id": uid}
    except sqlite3.IntegrityError:
        return {"ok": False, "err": "Bu e-posta adresi zaten kayitli."}
    finally:
        conn.close()

def login_user(email, pw):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email.lower(),))
    row = c.fetchone()
    if not row or not verify_password(pw, row["sifre_hash"]):
        conn.close()
        return {"ok": False, "err": "E-posta veya sifre hatali."}
    
    token = generate_token()
    c.execute("UPDATE users SET session_token=? WHERE id=?", (token, row["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "token": token, "id": row["id"]}

def get_user_by_token(token):
    if not token: return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE session_token=?", (token,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def increment_belge(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET kullanilan_belge=kullanilan_belge+1 WHERE id=?", (uid,))
    conn.commit()
    conn.close()

# --- FİNANSAL İŞLEMLER ---
def add_transaction(uid, tarih, islem_tipi, kategori, firma, tutar, kdv, aciklama, belge_turu, kaynak):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id,tarih,islem_tipi,kategori,firma,tutar,kdv,aciklama,belge_turu,kaynak) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (uid, tarih, islem_tipi, kategori, firma, tutar, kdv, aciklama, belge_turu, kaynak)
    )
    conn.commit()
    conn.close()

def get_user_transactions(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC", (uid,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_stats(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN islem_tipi='Gelir' THEN tutar ELSE 0 END),0) as toplam_gelir,"
        "COALESCE(SUM(CASE WHEN islem_tipi='Gider' THEN tutar ELSE 0 END),0) as toplam_gider,"
        "COUNT(*) as islem_sayisi "
        "FROM transactions WHERE user_id=?",
        (uid,)
    )
    row = c.fetchone()
    conn.close()
    return dict(row)

# --- ADMİN İŞLEMLERİ ---
def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_transactions_admin():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT t.*,u.ad,u.email FROM transactions t "
        "JOIN users u ON t.user_id=u.id ORDER BY t.created_at DESC LIMIT 200"
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_package(uid, paket):
    kota = 5 if paket == "Ucretsiz" else 1500
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET paket=?,kota=? WHERE id=?", (paket, kota, uid))
    conn.commit()
    conn.close()
