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
        return path if Path(path).exists() else None
    
    def crop_image(self, image_path, crop_ratio=0.4):
        """Görseli sol taraftan belirli oranda kes"""
        if not image_path or not Path(image_path).exists():
            return None
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
        if not image_path:
            return []
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
            # API anahtarları burada sabit tanımlanmış, güvenlik açısından ortam değişkenlerinden alınması önerilir.
            API_KEY = "AIzaSyATHIptem_0Bem35nqGyb31vULxi5jDL5w"
            CSE_ID = "Ya0cde0adb2a584800"
            
            if not API_KEY or not CSE_ID:
                print("Google API bilgileri eksik!")
                return []
            
            product_type = self._detect_product_type(product_info.get('product_name', ''))
            query = f"{product_type} {product_info.get('description', '')}"
            
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
        
        # Burada Spacy etiketlerinden PRODUCT, ORG, GPE veya NOUN olanları göz önünde bulunduruyoruz.
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "GPE", "NOUN"]:
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
        all_keywords.extend(self.analyze_product_name(product_data.get('product_name', '')))
        
        # Görsel analiz: ürün verisinde görsel yolu 'screenshot_path' key'i altında saklanmalıdır.
        screenshot_path = product_data.get('screenshot_path')
        if screenshot_path:
            corrected_path = self.process_image_path(screenshot_path)
            cropped_image = self.crop_image(corrected_path, 0.4)
            if cropped_image:
                all_keywords.extend(self.google_image_search(cropped_image))
        
        # Metin araması
        all_keywords.extend(self.google_text_search(product_data))
        
        # Fiyat ve satış bilgileri
        if product_data.get('current_price'):
            all_keywords.append(f"under_{product_data['current_price']}$")
        if product_data.get('units_sold'):
            all_keywords.append(f"popular_{product_data['units_sold']}_sold")
        
        return list(set(all_keywords))[:25]

if __name__ == "__main__":
    # Google Cloud kimlik bilgileri dosyasının yolunu ayarlıyoruz.
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/ayberkturk/Downloads/melodic-splicer-449022-g3-5e81e9599c73.json"
    
    analyzer = ProductAnalyzer()
    
    # Ürün verilerini içeren JSON dosyasını açıyoruz.
    with open('products_1738500199.json') as f:
        products = json.load(f)
    
    for product in products:
        keywords = analyzer.generate_keywords(product)
        print("="*50)
        print("Önerilen Anahtar Kelimeler:")
        print("\n".join(keywords))