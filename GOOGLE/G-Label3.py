import os
import io
import json
import math
import requests
import concurrent.futures
from typing import List, Tuple, Dict
from google.cloud import vision, storage
from PIL import Image, ImageDraw

# Sabit Proje Bilgisi: Kod içinde proje bilgisi belirlenmiştir.
PROJECT_ID = "melodic-splicer-449022-g3"

def parse_api_keys_from_text(text: str) -> Dict[str, str]:
    """
    Geçerli JSON olmayan formatta (anahtar = "değer" şeklinde) olan dosya içeriğini
    anahtar-değer sözlüğüne çevirir.
    """
    keys = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Yorumları kaldır: '#' karakterinden sonrasını at.
        if '#' in line:
            line = line.split('#', 1)[0].strip()
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            # Değerin hem başındaki hem sondaki tırnak işaretlerini kaldır
            value = value.strip().strip('"').strip("'")
            keys[key] = value
    return keys

def fetch_api_keys_from_gcs(
    bucket_name: str = "g-lab-api-keys",
    file_path: str = "google_api_keys.json"
) -> dict:
    """
    Google Cloud Storage içindeki dosyayı indirir ve içeriğini sözlüğe çevirir.
    Dosya içeriğini önce JSON olarak parse etmeyi dener, başarısız olursa
    basit bir anahtar = "değer" parser'ı kullanır.
    """
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    
    content = blob.download_as_text()
    print("İndirilen dosya içeriği:")
    print(content)
    
    if not content.strip():
        raise ValueError(f"GCS'den çekilen dosya boş: gs://{bucket_name}/{file_path}")
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print("JSON parse hatası, alternatif parser çalıştırılıyor...")
        return parse_api_keys_from_text(content)

def create_vision_client(google_credentials_path: str):
    """
    Belirtilen kimlik dosyasını ortam değişkeni olarak ayarlar ve
    Google Vision Client örneği döndürür.
    """
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
    return vision.ImageAnnotatorClient()

def polygon_area(points: List[Tuple[float, float]]) -> float:
    """
    Basit poligon alanı (Shoelace formülü) hesaplama.
    points: [(x1, y1), (x2, y2), ...]
    """
    area = 0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2.0

def get_largest_object_polygon(object_annotations, img_width, img_height):
    """
    En büyük bounding box'a sahip nesnenin poligonunu döndürür.
    object_annotations: Vision API'den gelen localized_object_annotations
    """
    max_area = 0
    max_polygon = None
    for obj in object_annotations:
        vertices = obj.bounding_poly.normalized_vertices
        polygon = []
        for v in vertices:
            x = v.x * img_width
            y = v.y * img_height
            polygon.append((x, y))
        area = polygon_area(polygon)
        if area > max_area:
            max_area = area
            max_polygon = polygon
    return max_polygon

def create_mask_for_polygon(im: Image.Image, polygon: List[Tuple[float, float]]) -> Image.Image:
    """
    Belirtilen poligon için bir maske (siyah-beyaz) oluşturur.
    Poligon içi: beyaz (255), dışı: siyah (0).
    """
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(polygon, outline=1, fill=255)
    return mask

def get_top_colors_from_pixels(pixels: List[Tuple[int, int, int]], top_k=3) -> List[str]:
    """
    Piksel listesinden en sık geçen (R, G, B) renkleri bulup HEX formatında döndürür.
    """
    freq = {}
    for rgb in pixels:
        freq[rgb] = freq.get(rgb, 0) + 1
    sorted_colors = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    top_colors = [c[0] for c in sorted_colors[:top_k]]
    hex_colors = [f'#{r:02X}{g:02X}{b:02X}' for (r, g, b) in top_colors]
    return hex_colors

def extract_dominant_colors_local(
    image_path: str,
    product_polygon: List[Tuple[float, float]] = None,
    top_k=3,
    background=False
) -> List[str]:
    """
    Lokal piksel analizi ile en sık rastlanan top_k rengi bulur.
    product_polygon: Nesnenin poligon koordinatları. None ise tüm resmi alır.
    background=True ise, poligon dışını analiz eder (arka plan rengi).
    """
    im = Image.open(image_path).convert("RGB")
    im.thumbnail((256, 256), Image.Resampling.LANCZOS)
    width, height = im.size

    if product_polygon is None:
        pixels = list(im.getdata())
        return get_top_colors_from_pixels(pixels, top_k=top_k)

    full_im = Image.open(image_path)
    orig_w, orig_h = full_im.size
    scale_x = width / orig_w
    scale_y = height / orig_h
    scaled_polygon = [(x * scale_x, y * scale_y) for (x, y) in product_polygon]
    mask = create_mask_for_polygon(im, scaled_polygon)
    mask_pixels = mask.load()
    im_pixels = im.load()

    region_pixels = []
    for y in range(height):
        for x in range(width):
            inside_polygon = (mask_pixels[x, y] > 128)
            if background:
                if not inside_polygon:
                    region_pixels.append(im_pixels[x, y])
            else:
                if inside_polygon:
                    region_pixels.append(im_pixels[x, y])
    return get_top_colors_from_pixels(region_pixels, top_k=top_k)

class GoogleProductSearch:
    def __init__(
        self,
        google_credentials_path: str,
        google_api_key: str,
        cse_id: str
    ):
        # Kimlik dosyasını ortam değişkeni yapıp Vision Client'ı oluşturuyoruz.
        self.google_credentials_path = google_credentials_path
        self.client = create_vision_client(google_credentials_path)
        self.google_api_key = google_api_key
        self.cse_id = cse_id

    def analyze_image(self, image_path: str) -> dict:
        """
        Görsel analizi yaparak ürün ve arka plan renklerini, kategori, açıklama, 
        etiketler ve nesneleri çıkarır.
        """
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()
        image = vision.Image(content=content)

        # 1) Tüm resim için Vision "image properties"
        color_response = self.client.image_properties(image=image)
        if color_response.image_properties_annotation:
            all_colors = color_response.image_properties_annotation.dominant_colors.colors
            dominant_colors_full = []
            for c in all_colors[:5]:
                r = int(c.color.red)
                g = int(c.color.green)
                b = int(c.color.blue)
                dominant_colors_full.append(f'#{r:02X}{g:02X}{b:02X}')
        else:
            dominant_colors_full = []

        # 2) Label Detection
        label_response = self.client.label_detection(image=image)
        labels = [label.description for label in label_response.label_annotations]

        # 3) Nesne Tespiti
        object_response = self.client.object_localization(image=image)
        objects = [obj.name for obj in object_response.localized_object_annotations]

        with Image.open(image_path) as pil_im:
            img_w, img_h = pil_im.size
        largest_polygon = get_largest_object_polygon(object_response.localized_object_annotations, img_w, img_h)

        # 4) Ürün rengi (en büyük poligon içi)
        if largest_polygon:
            product_colors = extract_dominant_colors_local(
                image_path,
                product_polygon=largest_polygon,
                top_k=3,
                background=False
            )
        else:
            product_colors = ["#000000", "#FFFFFF"]

        # 5) Arka plan rengi (en büyük poligon dışı)
        if largest_polygon:
            background_colors = extract_dominant_colors_local(
                image_path,
                product_polygon=largest_polygon,
                top_k=3,
                background=True
            )
        else:
            background_colors = ["#000000", "#FFFFFF"]

        # 6) Açıklama oluşturma
        desc_objects = ", ".join(objects[:3]) if objects else ""
        desc_labels = ", ".join(labels[:3]) if labels else ""
        desc_colors = ", ".join(dominant_colors_full[:3])
        description = f"{desc_objects} - {desc_labels} - Renkler: {desc_colors}"

        # 7) Kategori belirleme
        category = labels[0] if labels else 'Belirsiz'

        return {
            'dominant_colors_full': dominant_colors_full,
            'product_colors': product_colors,
            'background_colors': background_colors,
            'category': category,
            'description': description,
            'objects': objects,
            'labels': labels
        }

    def product_search_by_keywords(self, keywords: List[str], num_results: int = 5) -> List[dict]:
        """
        Anahtar kelimelerle ürün araması yapar (Google Custom Search kullanarak).
        """
        query = "+".join(keywords)
        url = (
            f"https://www.googleapis.com/customsearch/v1?q={query}"
            f"&cx={self.cse_id}&searchType=image&key={self.google_api_key}&num={num_results}"
        )
        response = requests.get(url)
        results = response.json()
        return [{
            'title': item.get('title', ''),
            'link': item.get('link', ''),
            'displayLink': item.get('displayLink', '')
        } for item in results.get('items', [])]

    def reverse_image_search(self, image_path: str, num_results: int = 5) -> List[dict]:
        """
        Tersine görsel arama yapar (WebDetection API ile).
        """
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = self.client.web_detection(image=image)
        web_detection = response.web_detection
        results = []
        if web_detection and web_detection.visually_similar_images:
            results = [{'link': img.url} for img in web_detection.visually_similar_images[:num_results]]
        return results

    def download_images(self, urls: List[str], save_dir: str) -> List[str]:
        """
        URL listesindeki görselleri paralel olarak indirir.
        """
        os.makedirs(save_dir, exist_ok=True)
        def download(url: str) -> str:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    filename = os.path.join(save_dir, url.split('/')[-1].split('?')[0])
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    return filename
                return None
            except Exception as e:
                print(f"İndirme hatası: {str(e)} => {url}")
                return None
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(download, urls))
        return [r for r in results if r]

    def process_image(self, image_path: str) -> str:
        """
        Tek bir görsel üzerinde tüm analizleri yapar:
          1) Ürün ve arka plan rengi analizi
          2) Etiket ve kategori çıkarımı
          3) Anahtar kelimelerin (prod_keys) oluşturulması
          4) Google CSE ve tersine görsel arama ile görsellerin indirilmesi
          5) Sonuçların JSON dosyasına kaydedilmesi
        """
        base_dir = os.path.dirname(image_path)
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(base_dir, f"{image_name}_analysis")
        os.makedirs(output_dir, exist_ok=True)

        analysis = self.analyze_image(image_path)
        print(f"Analiz Sonucu: {analysis['description']}")

        prod_keys = []
        if analysis['category'] and analysis['category'].lower() != "belirsiz":
            prod_keys.append(analysis['category'])
        desc_tokens = analysis['description'].replace('-', ' ').split() if analysis['description'] else []
        for token in desc_tokens[:4]:
            if token not in prod_keys:
                prod_keys.append(token)
        label_tokens = analysis['labels'][1:5] if len(analysis['labels']) > 1 else []
        for token in label_tokens:
            if token not in prod_keys:
                prod_keys.append(token)

        search_keywords = prod_keys[:3] if prod_keys else ["sample"]
        keyword_results = self.product_search_by_keywords(search_keywords, num_results=5)
        reverse_search_results = self.reverse_image_search(image_path, num_results=5)
        all_image_urls = [item['link'] for item in (keyword_results + reverse_search_results)]
        downloaded_images = self.download_images(all_image_urls, output_dir)

        result_data = {
            'original_image': image_path,
            'analysis': analysis,
            'prod_keys': prod_keys,
            'keyword_search_results': keyword_results,
            'reverse_search_results': reverse_search_results,
            'downloaded_images': downloaded_images
        }
        json_path = os.path.join(output_dir, 'results.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)

        print(f"Tüm sonuçlar kaydedildi: {output_dir}")
        return output_dir

def main_example():
    """
    Örnek kullanım:
      1) Google Cloud Storage'deki API anahtarları dosyasını alır.
      2) GoogleProductSearch sınıfını oluşturur.
      3) Belirtilen görsel üzerinde işlemleri başlatır.
    """
    api_keys = fetch_api_keys_from_gcs(
        bucket_name="g-lab-api-keys",
        file_path="google_api_keys.json"
    )
    searcher = GoogleProductSearch(
        google_credentials_path=api_keys["GOOGLE_CREDENTIALS"],
        google_api_key=api_keys["GOOGLE_API_KEY"],
        cse_id=api_keys["CSE_ID"]
    )
    image_path = '/Users/ayberkturk/ayb/Trendyol_Products/Erkek/product_4/image_3.jpg'
    output_folder = searcher.process_image(image_path)
    print("İşlemler tamamlandı. Çıktı klasörü:", output_folder)

if __name__ == "__main__":
    main_example()