import os
import json
import requests
from google.cloud import storage

def upload_images_to_gcs(local_folder, bucket_name, credentials_json):
    """
    Belirtilen klasördeki (.jpg, .jpeg, .png) tüm görselleri Google Cloud Storage
    bucket'ına yükler ve public URL’lerini döner.
    """
    storage_client = storage.Client.from_service_account_json(credentials_json)
    bucket = storage_client.bucket(bucket_name)
    image_urls = []
    
    for filename in os.listdir(local_folder):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            local_file_path = os.path.join(local_folder, filename)
            blob = bucket.blob(filename)
            blob.upload_from_filename(local_file_path)
            blob.make_public()
            image_urls.append(blob.public_url)
            print(f"{filename} yüklendi: {blob.public_url}")
    
    return image_urls

def transform_product_data(product_data, image_urls):
    """
    product.json dosyasındaki verileri eBay Inventory API şemasına uyacak şekilde dönüştürür.
    ItemSpecifics içindeki her değeri diziye çevirir.
    """
    raw_aspects = product_data.get("ItemSpecifics", {})
    aspects = {key: [value] if not isinstance(value, list) else value for key, value in raw_aspects.items()}

    transformed = {
        "sku": product_data.get("SKU", "jac-1s412892"),
        "condition": "NEW",
        "availability": {
            "shipToLocationAvailability": {
                "quantity": int(product_data.get("Quantity", 1))
            }
        },
        "product": {
            "title": product_data.get("Title", "Ürün Başlığı"),
            "description": product_data.get("Description", "Ürün açıklaması."),
            "aspects": aspects,
            "imageUrls": image_urls
        }
    }
    return transformed

def create_inventory_item(transformed_data, ebay_auth_token):
    """
    eBay Inventory API'sını kullanarak ürünün envanter öğesini oluşturur veya günceller.
    """
    sku = transformed_data.get("sku")
    endpoint = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    
    session = requests.Session()
    session.headers.clear()
    session.headers.update({
        "Authorization": f"Bearer {ebay_auth_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    })
    
    response = session.put(endpoint, json=transformed_data)

    if response.status_code == 204:
        print("✅ Envanter öğesi başarıyla oluşturuldu/güncellendi, ancak API herhangi bir içerik döndürmedi.")
        return None  
    
    if response.status_code in [200, 201]:
        print("✅ Envanter öğesi başarıyla oluşturuldu/güncellendi.")
        return response.json()

    print(f"❌ Envanter öğesi oluşturulurken hata: {response.status_code}\n{response.text}")
    
    return None

def create_offer(product_data, ebay_auth_token):
    """
    Envanter öğesine bağlı olarak satış teklifi (offer) oluşturur.
    """
    endpoint = "https://api.ebay.com/sell/inventory/v1/offer"
    
    session = requests.Session()
    session.headers.clear()
    session.headers.update({
        "Authorization": f"Bearer {ebay_auth_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    })
    
    response = session.post(endpoint, json=product_data)

    if response.status_code == 204:
        print("✅ Teklif başarıyla oluşturuldu, ancak API herhangi bir içerik döndürmedi.")
        return None  

    if response.status_code in [200, 201]:
        print("✅ Teklif başarıyla oluşturuldu.")
        return response.json()
    
    print(f"❌ Teklif oluşturulurken hata: {response.status_code}\n{response.text}")
    
    return None

def publish_offer(offer_id, ebay_auth_token):
    """
    Oluşturulan teklifi yayınlar, yani ürünü canlı satışa sunar.
    """
    endpoint = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish"
    
    session = requests.Session()
    session.headers.clear()
    session.headers.update({
        "Authorization": f"Bearer {ebay_auth_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Content-Language": "en-US"
    })
    
    response = session.post(endpoint)

    if response.status_code == 204:
        print("✅ Teklif başarıyla yayınlandı, ancak API herhangi bir içerik döndürmedi.")
        return None  

    if response.status_code in [200, 201]:
        print("✅ Teklif başarıyla yayınlandı.")
        return response.json()
    
    print(f"❌ Teklif yayınlanırken hata: {response.status_code}\n{response.text}")
    
    return None

def main():
    product_folder = '/Users/ayberkturk/ayb/Trendyol_Products/Kadın/Mavi ceket'
    product_json_path = os.path.join(product_folder, 'product.json')
    
    gcs_credentials = '/Users/ayberkturk/Desktop/melodic-splicer-449022-g3-5c9382c7b0ea.json'
    gcs_bucket_name = "aybebay-ai-1"
    
    ebay_auth_token = 'v^1.1#i^1#r^0#f^0#p^3#I^3#t^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'

    
    try:
        with open(product_json_path, 'r', encoding='utf-8') as f:
            product_data = json.load(f)
        print("Ürün detayları yüklendi.")
    except Exception as e:
        print(f"Ürün JSON dosyası okunamadı: {e}")
        return

    try:
        image_urls = upload_images_to_gcs(product_folder, gcs_bucket_name, gcs_credentials)
    except Exception as e:
        print(f"Görseller yüklenirken hata oluştu: {e}")
        return

    if "SKU" not in product_data or not product_data["SKU"]:
        product_data["SKU"] = "jac-1s412892"
    if "MarketplaceID" not in product_data or not product_data["MarketplaceID"]:
        product_data["MarketplaceID"] = "EBAY_US"

    transformed_data = transform_product_data(product_data, image_urls)
    transformed_data["sku"] = product_data["SKU"]

    inventory_response = create_inventory_item(transformed_data, ebay_auth_token)

    if inventory_response is None:
        print("⚠️ Envanter API yanıtı boş geldi (204 No Content). Devam ediliyor...")
    else:
        print("Envanter API yanıtı:", inventory_response)

    offer_response = create_offer(product_data, ebay_auth_token)

    if offer_response is None:
        print("⚠️ Teklif API yanıtı boş geldi (204 No Content). Devam ediliyor...")
        return

    offer_id = offer_response.get("offerId")
    if offer_id:
        publish_response = publish_offer(offer_id, ebay_auth_token)
        print("Publish API yanıtı:", publish_response)
    else:
        print("❌ Teklif oluşturulamadığı için yayınlama adımına geçilemiyor.")

if __name__ == "__main__":
    main()