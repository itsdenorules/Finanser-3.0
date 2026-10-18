import os
import json
import re
import google.generativeai as genai

# Ortam değişkeninden API anahtarını güvenle al
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def process_document_with_ai(file_bytes, mime_type):
    """
    Fatura, Fiş, Banka Dekontu ve Ekstreleri güncel Gemini 3.8 Flash ile okur.
    """
    if not GEMINI_API_KEY:
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            genai.configure(api_key=key)
        else:
            return {"ok": False, "err": "Sunucuda GEMINI_API_KEY bulunamadı!"}

    prompt = (
        "Sen uzman bir mali müşavir ve OCR analiz uzmanısın.\n"
        "Sana verilen görsel/PDF bir Türk mali belgesidir (fatura, perakende satış fişi, banka dekontu veya banka ekstresi).\n"
        "Belgeyi dikkatlice analiz et ve aşağıdaki bilgileri ÇIKAR:\n\n"
        "KURALLAR:\n"
        "1. tutar: ÖDENECEK NİHAİ GENEL TOPLAM TUTARDIR. KDV veya ara toplam değildir. Türk Lirası formatındaki binlik nokta ve kuruş virgülünü float'a çevir (Örn: 1.450,50 -> 1450.50).\n"
        "2. kdv: Belgede yazan toplam KDV tutarıdır (float). Yoksa 0.00 yaz.\n"
        "3. tarih: GG.AA.YYYY formatında olmalıdır. Bulamazsan bugünün tarihini ver.\n"
        "4. islem_tipi: Harcama/fatura/fiş ise 'Gider', gelir/tahsilat ise 'Gelir'.\n"
        "5. kategori: ['Kira', 'Fatura / Aidat', 'Personel', 'Malzeme / Hammadde', 'Ulaşım', 'Yemek', 'Ofis', 'Pazarlama / Reklam', 'Vergi / Harç', 'Sigorta', 'Satış', 'Hizmet Geliri', 'Diğer'] arasından en uygun olanı seç.\n\n"
        "JSON ŞEMASI (SADECE JSON döndür, başka hiçbir metin yazma):\n"
        "{\n"
        '  "belge_turu": "Fatura / Fiş / Banka Dekontu / Banka Ekstresi",\n'
        '  "tarih": "GG.AA.YYYY",\n'
        '  "firma": "Firma veya kişi adı",\n'
        '  "kategori": "Uygun kategori",\n'
        '  "tutar": 0.00,\n'
        '  "kdv": 0.00,\n'
        '  "islem_tipi": "Gelir veya Gider",\n'
        '  "aciklama": "Kısa açıklama"\n'
        "}"
    )

    if not mime_type or mime_type == "application/octet-stream":
        mime_type = "image/jpeg"

    # Şu an devrede olan güncel modeller
    candidate_models = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

    last_error = ""
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
            )

            response = model.generate_content([
                prompt,
                {"mime_type": mime_type, "data": file_bytes}
            ])

            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)

            data = json.loads(raw_text)
            data["tutar"] = float(data.get("tutar", 0.0))
            data["kdv"] = float(data.get("kdv", 0.0))

            return {"ok": True, "data": data}

        except Exception as e:
            last_error = str(e)
            continue

    return {"ok": False, "err": f"Belge okunamadı: {last_error}"}
