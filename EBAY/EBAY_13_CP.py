import json
import time
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
          - Eğer ürün varsa, ürün detaylarını toplayıp JSON dosyasına kaydeder.
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
                
                # Eğer en az 1 ürün varsa, ürün detaylarını topla ve JSON dosyasına kaydet.
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
        Alt kategori sayfasında ürünler varsa:
          - Sayfadaki ürünler, absolute XPath kullanılarak 
            /html/body/div[2]/div[2]/section[3]/section[3]/ul/li[i]/div/div/div[2]
            yoluyla toplanır.
          - Her bir ürün için, ürünün konteynerindeki tüm metin alınır.
          - Eğer alınan metinde (küçük harf duyarlı) "sold" ifadesi yoksa, o ürün atlanır.
          - "sold" ifadesi varsa, ürünün ilgili konteynerindeki tüm metin JSON formatında kaydedilir.
        """
        # Öncelikle ürün sayısını kontrol edelim
        count = self.get_product_count()
        if count == 0:
            print("    [INFO] Ürün bulunamadı, devam ediliyor.")
            return
        else:
            print(f"    [INFO] Ürün sayısı tespit edildi: {count}")
        
        # Ürün elemanlarının yüklenebilmesi için kısa süreli yavaş scroll (ör. 30 saniye)
        timeout = 30
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
                # Ürünün detaylarının bulunduğu konteyneri alıyoruz.
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                # Eğer konteyner metninde "sold" ifadesi yoksa bu ürüne ilgi duymuyoruz; atlıyoruz.
                if "sold" not in container_text.lower():
                    continue
                # İstenen ürün için konteynerde yer alan tüm metni kaydediyoruz.
                products_data.append({"full_text": container_text})
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
                continue
        
        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] Toplam {len(products_data)} ürün JSON dosyasına kaydedildi: {filename}")
        else:
            print("    [INFO] 'sold' ifadesini içeren ürün bulunamadı.")
    
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