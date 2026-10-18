import os
import json
import re
import google.generativeai as genai

# Streamlit st.secrets bitti! Artık sunucudan (ortam değişkeninden) şifreyi güvenle çekiyoruz:
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def process_document_with_ai(file_bytes, mime_type):
    if not GEMINI_API_KEY:
        return {"ok": False, "err": "Sunucuda GEMINI_API_KEY bulunamadi!"}

    prompt = (
        "Bu bir mali belgedir (fatura, fis, banka dekontu veya banka ekstresi olabilir). "
        "Belgeyi dikkatlice analiz et ve asagidaki bilgileri JSON formatinda cikar:\n\n"
        '{"belge_turu":"Fatura / Fis / Banka Dekontu / Banka Ekstresi",'
        '"tarih":"GG.AA.YYYY",'
        '"firma":"Firma veya kisi adi",'
        '"kategori":"Uygun kategori",'
        '"tutar":0.00,'
        '"kdv":0.00,'
        '"islem_tipi":"Gelir veya Gider",'
        '"aciklama":"Kisa aciklama"}\n\n'
        "SADECE JSON dondur, baska hicbir sey yazma. "
        "Eger bir bilgiyi cikaramiyorsan mantikli bir tahmin yap."
    )

    # Sistemi yavaşlatan "genai.list_models()" araması TAMAMEN KALDIRILDI!
    # Sadece en güncel ve kesin çalışan görsel modelleri listelendi (Şimşek hızında okuyacak)
    candidate_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-pro",
    ]

    last_err = ""
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                [prompt, {"mime_type": mime_type, "data": file_bytes}]
            )
            text = resp.text.strip()
            # Gelen yanıttaki gereksiz markdown kodlarını (```json ... ```) temizle
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            return {"ok": True, "data": data}
        except Exception as e:
            last_err = str(e)
            continue

    return {"ok": False, "err": last_err}
