import re
import json
import os
from pathlib import Path
from PIL import Image
from google.cloud import vision
import requests
from urllib.parse import quote_plus

def parse_product_data(json_data):
    products = json_data if isinstance(json_data, list) else [json_data]
    results = []
    
    for product in products:
        result = {
            'product_name': None,
            'current_price': None,
            'original_price': None,
            'units_sold': 0,
            'description': None,
            'screenshot_path': None
        }
        
        try:
            text = product.get('full_text', '')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            if lines:
                result['product_name'] = lines[0] if len(lines) > 0 else ''
                result['description'] = lines[1] if len(lines) > 1 else ''
                
                # Fiyat çıkarımı
                prices = re.findall(r'\$(\d+\.\d{2})', text)
                if prices:
                    result['current_price'] = float(prices[0])
                    result['original_price'] = float(prices[1]) if len(prices) > 1 else None
                
                # Satış miktarı
                sold_match = re.search(r'(\d+)\s+sold', text)
                result['units_sold'] = int(sold_match.group(1)) if sold_match else 0
                
                # Görsel path düzeltme
                raw_path = product.get('screenshot_path', '')
                result['screenshot_path'] = raw_path.replace("p/", "").replace("//", "/")
            
            results.append(result)
            
        except Exception as e:
            print(f"Ürün ayrıştırma hatası: {e}")
    
    return results

def process_image(image_path):
    try:
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")
            
        with Image.open(image_path) as img:
            width, height = img.size
            crop_width = int(width * 0.4)  # Solun %40'ı
            cropped_img = img.crop((0, 0, crop_width, height))
            cropped_path = f"processed_{Path(image_path).name}"
            cropped_img.save(cropped_path)
            return cropped_path
    except Exception as e:
        print(f"Görsel işleme hatası: {str(e)}")
        return None

def google_image_search(image_path):
    keywords = []
    try:
        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as f:
            content = f.read()
        
        image = vision.Image(content=content)
        response = client.web_detection(image=image)
        
        if response.web_detection.best_guess_labels:
            keywords.extend([label.label.lower() for label in response.web_detection.best_guess_labels])
        
        if response.web_detection.web_entities:
            keywords.extend([entity.description.lower() 
                           for entity in response.web_detection.web_entities 
                           if entity.score > 0.7])
        
        return list(set(keywords))
    except Exception as e:
        print(f"Görsel arama hatası: {str(e)}")
        return []

def google_text_search(product_info):
    try:
        API_KEY = "YOUR_API_KEY"  # Google API key
        CSE_ID = "YOUR_CSE_ID"    # Custom Search Engine ID
        
        query = f"{product_info['product_name']} {product_info['description']}"
        url = f"https://www.googleapis.com/customsearch/v1?q={quote_plus(query)}&key={API_KEY}&cx={CSE_ID}"
        
        response = requests.get(url).json()
        keywords = []
        
        for item in response.get('items', []):
            keywords.extend(re.findall(r'\b\w+\b', item.get('title', '').lower()))
            keywords.extend(re.findall(r'\b\w+\b', item.get('snippet', '').lower()))
        
        return list(set(keywords))
    except Exception as e:
        print(f"Metin araması hatası: {str(e)}")
        return []

def main(json_file):
    with open(json_file) as f:
        raw_data = json.load(f)
    
    products = parse_product_data(raw_data)
    
    for product in products:
        print("\n" + "="*50)
        print("Çıkarılan Ürün Bilgileri:")
        print(json.dumps(product, indent=2, ensure_ascii=False))
        
        keywords = []
        
        # Görsel işleme
        if product['screenshot_path']:
            cropped_image = process_image(product['screenshot_path'])
            if cropped_image:
                keywords += google_image_search(cropped_image)
        
        # Metin araması
        if product['product_name']:
            keywords += google_text_search(product)
        
        # Otomatik anahtar kelimeler
        auto_keywords = []
        if product['product_name']:
            auto_keywords.append(product['product_name'].lower())
            auto_keywords.extend(re.findall(r'\b\w+\b', product['product_name'].lower()))
        
        if product['current_price']:
            auto_keywords.append(f"{product['current_price']}$")
        
        if product['units_sold']:
            auto_keywords.append(f"{product['units_sold']} sold")
        
        keywords += auto_keywords
        
        # Sonuçları temizle
        final_keywords = sorted(list(set(
            [k.strip() for k in keywords if k.strip() and len(k) > 3]
        )))
        
        print("\nÖnerilen Anahtar Kelimeler:")
        print("\n".join(final_keywords[:20]))

if __name__ == "__main__":
    # Google Cloud kimlik bilgileri
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/ayberkturk/Downloads/melodic-splicer-449022-g3-5e81e9599c73.json"
    
    # Çalıştırma
    main('products_1738500199.json')