import os
import io
import requests
import json
from google.cloud import vision
from PIL import Image
import concurrent.futures

class GoogleProductSearch:
    def __init__(self, google_credentials_path, google_api_key, cse_id):
        self.google_credentials_path = google_credentials_path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.google_credentials_path
        self.client = vision.ImageAnnotatorClient()
        self.google_api_key = google_api_key
        self.cse_id = cse_id

    def analyze_image(self, image_path):
        """Görsel analizi yaparak renk, kategori ve açıklama çıkarır"""
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        
        # Renk analizi
        color_response = self.client.image_properties(image=image)
        dominant_colors = [color.color for color in color_response.image_properties_annotation.dominant_colors.colors]
        
        # Etiket ve kategori analizi
        label_response = self.client.label_detection(image=image)
        labels = [label.description for label in label_response.label_annotations]
        
        # Nesne tespiti
        object_response = self.client.object_localization(image=image)
        objects = [obj.name for obj in object_response.localized_object_annotations]

        # Renkleri HEX formatına çevirme
        color_palette = []
        for color in dominant_colors[:3]:  # En dominant 3 renk
            r = int(color.red)
            g = int(color.green)
            b = int(color.blue)
            color_palette.append(f'#{r:02x}{g:02x}{b:02x}'.upper())

        # Açıklama oluşturma
        description = f"{', '.join(objects[:3])} - {', '.join(labels[:3])} - Renkler: {', '.join(color_palette)}"
        
        return {
            'colors': color_palette,
            'category': labels[0] if labels else 'Belirsiz',
            'description': description,
            'objects': objects,
            'labels': labels
        }

    def product_search_by_keywords(self, keywords, num_results=5):
        """Anahtar kelimelerle ürün arama"""
        query = "+".join(keywords)
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&cx={self.cse_id}&searchType=image&key={self.google_api_key}&num={num_results}"
        
        response = requests.get(url)
        results = response.json()
        
        return [{
            'title': item.get('title', ''),
            'link': item.get('link', ''),
            'displayLink': item.get('displayLink', '')
        } for item in results.get('items', [])]

    def reverse_image_search(self, image_path, num_results=5):
        """Tersine görsel arama"""
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = self.client.web_detection(image=image)
        web_detection = response.web_detection

        results = []
        if web_detection.visually_similar_images:
            results = [{'link': img.url} for img in web_detection.visually_similar_images[:num_results]]
        return results

    def download_images(self, urls, save_dir):
        """Görselleri paralel indirme"""
        os.makedirs(save_dir, exist_ok=True)
        
        def download(url):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    filename = os.path.join(save_dir, url.split('/')[-1].split('?')[0])
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    return filename
                return None
            except Exception as e:
                print(f"İndirme hatası: {str(e)}")
                return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(download, urls))
        
        return [r for r in results if r]

    def process_image(self, image_path):
        """Tüm işlemleri entegre eden ana fonksiyon"""
        # Dosya yapısını oluştur
        base_dir = os.path.dirname(image_path)
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(base_dir, f"{image_name}_analysis")
        os.makedirs(output_dir, exist_ok=True)

        # Görsel analizi
        analysis = self.analyze_image(image_path)
        print(f"Analiz Sonucu: {analysis['description']}")

        # Anahtar kelime ile arama
        keyword_results = self.product_search_by_keywords(analysis['labels'][:3])
        reverse_search_results = self.reverse_image_search(image_path)

        # Görsel indirme
        all_image_urls = [item['link'] for item in keyword_results + reverse_search_results]
        downloaded_images = self.download_images(all_image_urls, output_dir)

        # Sonuçları kaydetme
        result_data = {
            'original_image': image_path,
            'analysis': analysis,
            'keyword_search_results': keyword_results,
            'reverse_search_results': reverse_search_results,
            'downloaded_images': downloaded_images
        }

        json_path = os.path.join(output_dir, 'results.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)

        print(f"Tüm sonuçlar kaydedildi: {output_dir}")
        return output_dir

# Kullanım Örneği
if __name__ == "__main__":
    searcher = GoogleProductSearch(
        google_credentials_path="/Users/ayberkturk/Downloads/melodic-splicer-449022-g3-5e81e9599c73.json",
        google_api_key="AIzaSyATHIptem_0Bem35nqGyb31vULxi5jDL5w",
        cse_id="a0cde0adb2a584800"
    )

    image_path = '/Users/ayberkturk/Desktop/SCFAI/untitled folder/ebay_data/Test Pictures/71N2-+T50pL._AC_SL1500_.jpg'  # Analiz edilecek görselin yolu
    output_folder = searcher.process_image(image_path)