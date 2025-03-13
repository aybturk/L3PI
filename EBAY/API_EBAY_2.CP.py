import requests
import json
import re

class EbayAPI:
    def __init__(self, env="sandbox", token=None):
        """
        Sandbox ortamı için API bilgileri, endpoint ve token ayarlanır.
        
        :param env: "sandbox" veya "production" (şimdilik "sandbox")
        :param token: eBay sandbox kullanıcı token'ınız.
        """
        self.env = env.lower()
        self.token = token
        if self.env == "sandbox":
            # Sandbox ortamı bilgileri
            self.app_id = "ayberktu-AYB-SBX-866f7ac08-588309b9"
            self.endpoint = "https://open.api.sandbox.ebay.com/shopping"
        else:
            # Production ortamı (şimdilik kullanılmayacak)
            self.app_id = "ayberktu-AYB-PRD-c66f7a2fb-ff49d7ea"
            self.endpoint = "https://open.api.ebay.com/shopping"
        
        # API sürüm numarası (dokümantasyonda belirtilmiş sabit değer)
        self.api_version = "967"

    def get_item_details(self, item_id):
        """
        Belirtilen item ID için GetSingleItem API çağrısı yapar.
        
        :param item_id: eBay ürün ID'si
        :return: API'den gelen JSON yanıtı (sözlük) veya hata durumunda None
        """
        params = {
            "callname": "GetSingleItem",
            "responseencoding": "JSON",
            "appid": self.app_id,
            "siteid": "0",  # Global eBay sitesi
            "version": self.api_version,
            "ItemID": item_id,
            "IncludeSelector": "Details,ItemSpecifics"
        }
        
        # Tokenı hem "X-EBAY-API-TOKEN" hem de "Authorization" header'ında ekliyoruz:
        headers = {
            "X-EBAY-API-TOKEN": self.token,
            "Authorization": f"Bearer {self.token}"
        }
        
        # Gönderilen header'ları kontrol etmek için:
        response = requests.get(self.endpoint, params=params, headers=headers)
        print("Gönderilen Header'lar:", response.request.headers)
        
        try:
            response.raise_for_status()  # HTTP hatası varsa burada yakalar
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API isteği sırasında bir hata oluştu: {e}")
            # Yanıtın içeriğini da yazdırmak hata ayıklamaya yardımcı olabilir:
            print("Yanıt içeriği:", response.text)
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
    # Örnek ürün linki:
    item_link = "https://www.ebay.com/itm/295203092483"
    
    # Linkten item ID'sini çıkarıyoruz:
    item_id = extract_item_id_from_link(item_link)
    
    if not item_id:
        print("Geçerli bir item ID elde edilemedi, program sonlandırılıyor.")
    else:
        # Sağladığınız token bilgisini buraya ekleyin:
        token = "v^1.1#i^1#I^3#p^3#f^0#r^1#t^Ul4xMF85OjI5NUE4MDU5NDlFRkU5MDU0QzVGQzgxOTk5QzUxMDE2XzFfMSNFXjEyODQ="
        
        # EbayAPI örneğini sandbox ortamı ve token ile oluşturuyoruz:
        ebay_api = EbayAPI(env="sandbox", token=token)
        
        # API çağrısı ile ürün detaylarını alıyoruz:
        item_details = ebay_api.get_item_details(item_id)
        
        if item_details:
            # Gelen JSON yanıtı 'item_details.json' dosyasına kaydediyoruz:
            with open("item_details.json", "w", encoding="utf-8") as f:
                json.dump(item_details, f, indent=4, ensure_ascii=False)
            print("Ürün detayları 'item_details.json' dosyasına kaydedildi.")
        else:
            print("Ürün detayları alınamadı.")