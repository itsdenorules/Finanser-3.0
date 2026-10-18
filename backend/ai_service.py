import google.generativeai as genai
import os

# API anahtarını güvenli bir şekilde sunucudan çekeceğiz, koda asla yazmıyoruz.
API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=API_KEY)

# Hızlı ve güncel olan 2.5 Flash modelini kullanıyoruz.
model = genai.GenerativeModel('gemini-2.5-flash')

async def process_receipt_image(image_file):
    try:
        prompt = """
        Bu faturadaki/fişteki bilgileri çok dikkatli analiz et ve SADECE JSON formatında şu anahtarlarla dön:
        - tarih (GG.AA.YYYY formatında)
        - tutar (sayısal, belgedeki 'Genel Toplam', 'Toplam' veya 'Ödenen Tutar' kısmını bul. Kesinlikle KDV dahil en son rakamı yaz. Örn: 450.00)
        - kdv (sayısal, belgedeki toplam KDV tutarı)
        - firma (string, SADECE belgenin üzerindeki logodan, başlıktan veya kaşeden oku. ASLA sana gönderilen dosyanın adını firma adı olarak kullanma!)
        - islem_tipi ("Gider" veya "Gelir")
        - belge_turu ("Fiş", "Fatura", vb.)
        """
        
        response = await model.generate_content_async([prompt, image_file])
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return clean_text
        
    except Exception as e:
        return {"error": str(e)}
