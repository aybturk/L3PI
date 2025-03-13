import os
import json
import requests
from google.cloud import storage

def upload_images_to_gcs(local_folder, bucket_name, credentials_json):
    """
    Belirtilen klasördeki (.jpg, .jpeg, .png uzantılı) tüm görselleri Google Cloud Storage
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

def create_ebay_listing(product_data, image_urls, ebay_auth_token):
    """
    Ürün detayları (JSON) ve görsel URL’lerini eBay API’ye göndererek ürün listelemesi oluşturur.
    eBay Inventory API gereksinimlerine göre, payload içinde geçerli bir SKU ve marketplaceId bulunmalıdır.
    """
    # Görsel URL’lerini ürün verilerine ekleyelim
    product_data["ImageURLs"] = image_urls

    # SKU kontrolü: Eğer product_data içinde geçerli bir SKU yoksa, örnek geçerli bir SKU ekleyelim.
    if "sku" not in product_data or not product_data["sku"]:
        product_data["sku"] = "jac-141"  # SKU alfanümerik, maksimum 50 karakter uzunluğunda olmalı.

    # marketplaceId kontrolü: Geçerli bir pazar yeri değeri ekleyelim. Örneğin, ABD pazarı için "EBAY_US" kullanın.
    if "marketplaceId" not in product_data or not product_data["marketplaceId"]:
        product_data["marketplaceId"] = "EBAY_US"  # Kendi pazar yerinize göre güncelleyebilirsiniz.

    # eBay Inventory API endpoint'i
    ebay_api_endpoint = "https://api.ebay.com/sell/inventory/v1/offer"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ebay_auth_token}",
        "Content-Language": "en-US"  # Geçerli bir dil değeri
    }
    
    response = requests.post(ebay_api_endpoint, headers=headers, json=product_data)
    
    if response.status_code in [200, 201]:
        print("Ürün başarılı bir şekilde listelendi.")
    else:
        print(f"Listeleme oluşturulurken hata: {response.status_code}\n{response.text}")
    
    return response.json()

def main():
    # Ürün verilerinin bulunduğu klasör ve JSON dosya yolu
    product_folder = '/Users/ayberkturk/ayb/Trendyol_Products/Kadın/Mavi ceket'
    product_json_path = os.path.join(product_folder, 'product.json')
    
    # Google Cloud Storage kimlik bilgileri ve bucket adı
    gcs_credentials = '/Users/ayberkturk/Desktop/melodic-splicer-449022-g3-5c9382c7b0ea.json'
    gcs_bucket_name = "aybebay-ai-1"
    
    # eBay API yetkilendirme token’ı
    ebay_auth_token = 'v^1.1#i^1#p^3#I^3#r^1#f^0#t^Ul4xMF8zOjJBMzcyQjI0NDNENjBCMDcxRjZCQjU2MzhBQjM3NDdFXzFfMSNFXjI2MA=='
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

    try:
        listing_response = create_ebay_listing(product_data, image_urls, ebay_auth_token)
        print("eBay API yanıtı:", listing_response)
    except Exception as e:
        print(f"eBay listeleme oluşturulurken hata: {e}")

if __name__ == "__main__":
    main()