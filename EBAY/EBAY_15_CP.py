import os
import json
import time
import requests  # <--- Görsel indirmek için ekleniyor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class ProductCollectorAI:
    def __init__(self, driver_path):
        """
        driver_path: ChromeDriver (veya Firefox için geckodriver) executable yolunu belirtir.
        """
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def go_to_ebay(self):
        """eBay'in anasayfasına gider."""
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=3, end_index=12):
        """
        Ana kategorilerde dolaşır; her kategoriye tıkladığında alt kategorileri gezip,
        ürün (results) varlığını kontrol eder ve varsa ürün detaylarını toplar.
        """
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Alt kategorileri gez
                self.explore_sub_categories()
                
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı. Muhtemelen daha fazla kategori yok.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı. Muhtemelen görünmüyor veya engelleniyor.")
                break
    
    def explore_sub_categories(self, start_index=3, max_attempts=50):
        """
        Ana kategori altında yer alan alt kategorileri sırayla tıklar.
        Her alt kategori için:
          - Varsa daha derin kategoriler incelenir.
          - Sayfadaki ürün elemanları (results) CSS seçiciyle kontrol edilir.
          - Eğer ürün varsa, ürün detaylarını toplayıp JSON dosyasına kaydeder (veya görüntüleri indirir).
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Daha derin kategorileri kontrol edelim (varsa)
                self.explore_deeper_categories()
                
                # Sayfadaki ürün listesini kontrol edelim.
                product_count = self.get_product_count()
                print(f"    [INFO] Bu alt kategoride {product_count} ürün tespit edildi.")
                
                # Eğer en az 1 ürün varsa, ürün detaylarını topla
                if product_count > 0:
                    self.scrape_products()
                else:
                    print("    [INFO] Ürün bulunamadı, devam ediliyor.")
                
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print("    [WARNING] Daha fazla alt kategori bulunamadı.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı. Engelleniyor olabilir.")
                break
    
    def explore_deeper_categories(self, start_index=3, max_attempts=50):
        """
        Alt kategoriye tıklandıktan sonra, varsa daha derin kategori öğelerini inceler.
        """
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_text = deeper_elem.text.strip()
                print(f"        [INFO] Daha derin kategori bulundu: {deeper_text}")
            except NoSuchElementException:
                break
            except ElementClickInterceptedException:
                break
    
    def get_product_count(self):
        """
        Sayfa içerisindeki ürün elemanlarını, 
        CSS sınıfı "brwrvr__item-card brwrvr__item-card--list" olan li etiketleri üzerinden tespit eder.
        """
        try:
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
            return len(product_elements)
        except Exception:
            return 0
    
    def scrape_products(self):
        """
        Alt kategori sayfasındaki ürünleri detaylı olarak çeker:
          - 'sold' ifadesi (küçük harf) içeriyorsa işlenir.
          - Ürün adı, fiyat, görsel URL ve benzeri bilgileri ayrı bir JSON listesinde biriktirir.
          - Ürüne ait görsel, images/ klasörü altına kaydedilir.
        """
        # Ürün sayısını kontrol edelim
        count = self.get_product_count()
        if count == 0:
            print("    [INFO] Ürün bulunamadı, devam ediliyor.")
            return
        else:
            print(f"    [INFO] Ürün sayısı tespit edildi: {count}")
        
        # Ürün elemanlarının yüklenebilmesi için kısa süreli yavaş scroll (ör. 10-15 saniye)  
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.get_product_count() > 0:
                break
            self.driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(1)
        
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        if len(product_elements) == 0:
            print("    [INFO] Scroll sonrası ürün elemanı bulunamadı.")
            return
        
        print(f"    [INFO] Toplam ürün elemanı sayısı: {len(product_elements)}")
        products_data = []
        
        for idx, product in enumerate(product_elements, start=1):
            try:
                # Metinsel bilgiler (örneğin satılıp satılmadığını anlamak için) 
                text_container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = text_container.text.strip()
                
                # 'sold' ifadesi yoksa atla (orijinal mantığınızı koruyorum)
                if "sold" not in container_text.lower():
                    continue
                
                # ---------------------------------------------------------------
                # 1) Ürün ismi çekme
                #    (Aşağıdaki örnek XPath tamamen eBay'in gerçek yapısına 
                #     göre uyarlanmalıdır. Örnek amaçlı veriyorum.)
                try:
                    # Örn: "./div/div/div[2]/a/h3" gibi bir XPath ya da
                    # başka bir CSS seçici: ".s-item__title" ...
                    product_name_elem = product.find_element(By.XPATH, './/h3')  
                    product_name = product_name_elem.text.strip()
                except NoSuchElementException:
                    product_name = "Unnamed product"
                
                # ---------------------------------------------------------------
                # 2) Fiyat bilgisi çekme
                try:
                    # Örneğin "./div/div/div[2]/div/span" vb. bir XPath. 
                    # Yine gerçek eBay yapısına göre test edip uyarlamak gerekir.
                    price_elem = product.find_element(By.XPATH, './/span[@class="s-item__price"]')
                    product_price = price_elem.text.strip()
                except NoSuchElementException:
                    product_price = "N/A"
                
                # ---------------------------------------------------------------
                # 3) Görsel URL çekme
                # product için: ./div/div/div[1]/div[1]/... gibi bir yapı olabilir.
                try:
                    # Örneğin:
                    # img_elem = product.find_element(By.XPATH, './div/div/div[1]/div[1]/div/div/ul/li[1]/a/img')
                    # ya da daha genel bir CSS: '.s-item__image-img'
                    img_elem = product.find_element(By.CSS_SELECTOR, 'img.s-item__image-img')
                    img_url = img_elem.get_attribute('src')
                except NoSuchElementException:
                    img_url = None
                
                # ---------------------------------------------------------------
                # 4) Görseli kaydet (eğer varsa)
                saved_image_path = None
                if img_url:
                    saved_image_path = self.download_image(img_url, product_name)
                
                # ---------------------------------------------------------------
                # 5) Toplanan veriyi listeye ekle
                products_data.append({
                    "name": product_name,
                    "price": product_price,
                    "image": saved_image_path,   # Kaydedilen dosyanın lokal yolu
                    "text": container_text       # Orijinal metni de ekleyebilirsiniz
                })
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
                continue
        
        # Eğer bu alt kategoride 'sold' içeren ürün yoksa products_data boş olabilir
        if products_data:
            filename = f"products_details_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] Toplam {len(products_data)} ürün JSON dosyasına kaydedildi: {filename}")
        else:
            print("    [INFO] 'sold' ifadesini içeren veya işlenecek uygun ürün bulunamadı.")
    
    def download_image(self, img_url, product_name):
        """
        Verilen URL'deki resmi indirip images/ klasörüne kaydeder.
        Dosya adını, ürün ismindeki özel karakterleri temizleyerek oluşturur.
        """
        # Dosya adı olarak ürün ismini kullanalım (özel karakterleri arındırmak şart!)
        safe_name = "".join(c for c in product_name if c.isalnum() or c in (" ", "_", "-")).rstrip()
        if not safe_name:
            safe_name = "product"
        
        # Klasör adı
        images_folder = "images"
        if not os.path.exists(images_folder):
            os.makedirs(images_folder)
        
        # Dosya tam pathi
        file_path = os.path.join(images_folder, f"{safe_name}.jpg")
        
        try:
            # requests ile indiriyoruz
            response = requests.get(img_url, timeout=10)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return file_path
            else:
                print(f"        [ERROR] Görsel indirme başarısız: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"        [ERROR] Görsel indirilirken hata: {str(e)}")
            return None
    
    def close(self):
        """Tarayıcıyı kapatır."""
        self.driver.quit()


if __name__ == "__main__":
    # Kendi ChromeDriver yolunuzu belirtin
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    
    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    collector.explore_main_categories(start_index=3, end_index=12)
    collector.close()