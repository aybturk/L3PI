import re
import json
import os
from pathlib import Path
from PIL import Image
from google.cloud import vision
import requests
from urllib.parse import quote_plus
import spacy

# NLP modelini yükle
nlp = spacy.load("en_core_web_sm")

class ProductAnalyzer:
    def __init__(self):
        self.keyword_db = {}
        self.image_client = vision.ImageAnnotatorClient()
    
    def analyze_product_name(self, product_name):
        """Ürün adından anahtar kelimeler çıkar"""
        doc = nlp(product_name.lower())
        keywords = [
            chunk.text for chunk in doc.noun_chunks 
            if not chunk.text.isdigit() and len(chunk.text) > 3
        ]
        return list(set(keywords))
    
    def process_image_path(self, raw_path):
        """Hatalı path düzenlemelerini düzelt"""
        path = raw_path.replace("p/", "").replace("//", "/")
        if not Path(path).exists():
            path = os.path.join("downloads", os.path.basename(path))
        return path
    
    def crop_image(self, image_path, crop_ratio=0.4):
        """Görseli sol taraftan belirli oranda kes"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                crop_width = int(width * crop_ratio)
                cropped_img = img.crop((0, 0, crop_width, height))
                cropped_path = f"processed_{os.path.basename(image_path)}"
                cropped_img.save(cropped_path)
                return cropped_path
        except Exception as e:
            print(f"Görsel işleme hatası: {e}")
            return None
    
    def google_image_search(self, image_path):
        """Görsel tabanlı anahtar kelime bulma"""
        try:
            with open(image_path, "rb") as f:
                content = f.read()
            
            image = vision.Image(content=content)
            response = self.image_client.web_detection(image=image)
            
            keywords = []
            if response.web_detection.best_guess_labels:
                keywords.extend([label.label.lower() for label in response.web_detection.best_guess_labels])
            
            if response.web_detection.web_entities:
                keywords.extend([entity.description.lower() 
                               for entity in response.web_detection.web_entities 
                               if entity.score > 0.7])
            
            self._update_keyword_db(keywords)
            return keywords
        except Exception as e:
            print(f"Görsel arama hatası: {e}")
            return []
    
    def google_text_search(self, product_info):
        """Metin tabanlı akıllı arama"""
        try:
            API_KEY = "AIzaSyATHIptem_0Bem35nqGyb31vULxi5jDL5w"
            CSE_ID = "Ya0cde0adb2a584800"
            
            # Ürün tipini belirleme
            product_type = self._detect_product_type(product_info['product_name'])
            query = f"{product_type} {product_info['description']}"
            
            url = f"https://www.googleapis.com/customsearch/v1?q={quote_plus(query)}&key={API_KEY}&cx={CSE_ID}"
            response = requests.get(url).json()
            
            keywords = []
            for item in response.get('items', []):
                keywords.extend(self.analyze_product_name(item.get('title', '')))
                keywords.extend(self.analyze_product_name(item.get('snippet', '')))
            
            self._update_keyword_db(keywords)
            return keywords
        except Exception as e:
            print(f"Metin araması hatası: {e}")
            return []
    
    def _detect_product_type(self, product_name):
        """Ürün tipini NLP ile belirleme"""
        doc = nlp(product_name)
        product_types = []
        
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "NOUN"]:
                product_types.append(ent.text)
        
        return " ".join(product_types[:2]) if product_types else "product"
    
    def _update_keyword_db(self, keywords):
        """Anahtar kelime veritabanını güncelle"""
        for keyword in keywords:
            self.keyword_db[keyword] = self.keyword_db.get(keyword, 0) + 1
    
    def generate_keywords(self, product_data):
        """Tüm veri kaynaklarını kullanarak anahtar kelimeler oluştur"""
        all_keywords = []
        
        # Ürün adı analizi
        all_keywords.extend(self.analyze_product_name(product_data['product_name']))
        
        # Görsel analiz
        if product_data['/Users/ayberkturk/Desktop/ebay_data/EBAY SOLD PRODUCTS 3/product_screenshots/1738497611_16/product_screenshot.png']:
            corrected_path = self.process_image_path(product_data['/Users/ayberkturk/Desktop/ebay_data/EBAY SOLD PRODUCTS 3/product_screenshots/1738497611_16/product_screenshot.png'])
            cropped_image = self.crop_image(corrected_path, 0.4)
            if cropped_image:
                all_keywords.extend(self.google_image_search(cropped_image))
        
        # Metin araması
        all_keywords.extend(self.google_text_search(product_data))
        
        # Fiyat ve satış bilgileri
        if product_data['current_price']:
            all_keywords.append(f"under_{product_data['current_price']}$")
        if product_data['units_sold']:
            all_keywords.append(f"popular_{product_data['units_sold']}_sold")
        
        # Veritabanından öneriler
        sorted_keywords = sorted(self.keyword_db.items(), key=lambda x: x[1], reverse=True)
        all_keywords.extend([k[0] for k in sorted_keywords[:5]])
        
        # Temizleme ve sıralama
        final_keywords = sorted(list(set(
            [k.strip() for k in all_keywords 
             if k.strip() and len(k) > 3 and not k.isdigit()]
        )))
        
        return final_keywords[:25]

# Ana iş akışı
def main(json_file):
    analyzer = ProductAnalyzer()
    
    with open(json_file) as f:
        raw_data = json.load(f)
    
    products = raw_data if isinstance(raw_data, list) else [raw_data]
    
    for product in products:
        print("\n" + "="*50)
        print("Analiz Edilen Ürün:")
        print(json.dumps(product, indent=2, ensure_ascii=False))
        
        # Anahtar kelime üretimi
        keywords = analyzer.generate_keywords({
            'product_name': product.get('full_text', '').split('\n')[0],
            'description': product.get('full_text', '').split('\n')[1] if '\n' in product.get('full_text', '') else '',
            'current_price': float(re.findall(r'\$(\d+\.\d{2})', product.get('full_text', ''))[0]) if re.findall(r'\$(\d+\.\d{2})', product.get('full_text', '')) else None,
            'units_sold': int(re.search(r'(\d+)\s+sold', product.get('full_text', '')).group(1)) if re.search(r'(\d+)\s+sold', product.get('full_text', '')) else 0,
            'screenshot_path': product.get('screenshot_path', '')
        })
        
        print("\nÖnerilen Anahtar Kelimeler:")
        print("\n".join(keywords))

if __name__ == "__main__":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/ayberkturk/Downloads/melodic-splicer-449022-g3-5e81e9599c73.json"
    main('products_1738500199.json')