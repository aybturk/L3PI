import requests
import json
import re

class EbayAPI:
    def __init__(self, env="sandbox"):
        """
        Sandbox ortamını kullanarak API kimlik bilgileri ve endpoint ayarlanır.
        """
        self.env = env.lower()
        if self.env == "sandbox":
            # Sandbox ortamı için kimlik bilgileri ve endpoint
            self.app_id = "ayberktu-AYB-SBX-866f7ac08-588309b9"
            self.dev_id = "123adc65-d3e8-435f-aca9-75fcf20a9e2d"
            self.cert_id = "SBX-66f7ac08274c-cf73-4a9c-b1f4-b6c7"
            self.endpoint = "https://open.api.sandbox.ebay.com/shopping"
        else:
            # Eğer production ortamı kullanılacaksa (şimdilik kullanılmayacak)
            self.app_id = "ayberktu-AYB-PRD-c66f7a2fb-ff49d7ea"
            self.dev_id = "123adc65-d3e8-435f-aca9-75fcf20a9e2d"
            self.cert_id = "PRD-66f7a2fb4712-4013-4945-a837-3fae"
            self.endpoint = "https://open.api.ebay.com/shopping"

        # eBay Shopping API için kullanılacak sürüm numarası (dokümantasyona göre belirlenmiştir)
        self.api_version = "967"

    def get_item_details(self, item_id):
        """
        Verilen item_id için GetSingleItem API çağrısı yapar ve JSON cevabı döner.
        """
        params = {
            "callname": "GetSingleItem",
            "responseencoding": "JSON",
            "appid": self.app_id,
            "siteid": "0",  # Global eBay sitesi; ihtiyaca göre değiştirilebilir.
            "version": self.api_version,
            "ItemID": item_id,
            "IncludeSelector": "Details,ItemSpecifics"  # Ürün detayları ve özellikleri
        }

        try:
            response = requests.get(self.endpoint, params=params)
            response.raise_for_status()  # HTTP hatası varsa burada yakalar.
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API isteği sırasında bir hata oluştu: {e}")
            return None

def extract_item_id_from_link(item_link):
    """
    Verilen eBay ürün linkinden item ID'sini çıkarır.
    Örnek: https://www.ebay.com/itm/295203092483  → 295203092483
    """
    match = re.search(r'/itm/(\d+)', item_link)
    if match:
        return match.group(1)
    else:
        print("Item ID bulunamadı. Lütfen linki kontrol edin.")
        return None

if __name__ == "__main__":
    # Deneme için örnek ürün linki
    item_link = "https://www.ebay.com/itm/295203092483"
    
    # Ürün linkinden item ID'sini çıkarıyoruz.
    item_id = extract_item_id_from_link(item_link)
    
    if not item_id:
        print("Geçerli bir item ID elde edilemedi, program sonlandırılıyor.")
    else:
        # Sandbox ortamında API çağrısı yapmak için EbayAPI sınıfı örneğini oluşturuyoruz.
        ebay_api = EbayAPI(env="sandbox")
        
        # API çağrısı yapılarak ürün detayları çekiliyor.
        item_details = ebay_api.get_item_details(item_id)
        
        if item_details:
            # Gelen JSON verisi, 'item_details.json' dosyasına kaydediliyor.
            with open("item_details.json", "w", encoding="utf-8") as f:
                json.dump(item_details, f, indent=4, ensure_ascii=False)
            print("Ürün detayları 'item_details.json' dosyasına kaydedildi.")
        else:
            print("Ürün detayları alınamadı.")