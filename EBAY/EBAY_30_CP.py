import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        # Headless mod kapalı tutulduğunda görsel ve element işlemleri daha doğru çalışabilir.
        # options.add_argument("--headless")
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Ekran görüntülerinin kaydedileceği temel klasör
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
        
        # Mevcut kategori bilgilerini saklamak için
        self.current_main_category = None
        self.current_sub_category = None
        self.current_deeper_category = None

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self):
        """
        Ana kategorileri dolaşır. Artık yalnızca 4, 6 ve 8 numaralı indeksler işlenecek.
        """
        main_indexes = [4, 6, 8]
        for i in main_indexes:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                main_cat_element = self.driver.find_element(By.XPATH, xpath)
                self.current_main_category = main_cat_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {self.current_main_category}")
                main_cat_element.click()
                time.sleep(2)
                
                self.explore_sub_categories()
                
                self.driver.back()  # Ana kategori listesinin bulunduğu sayfaya geri dön
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Ana kategori (li[{i}]) bulunamadı.")
            except ElementClickInterceptedException:
                print(f"[WARNING] Ana kategoriye (li[{i}]) tıklanamadı.")
    
    def explore_sub_categories(self, start_index=1, max_attempts=50):
        """
        Seçilen ana kategorinin alt kategorilerini dolaşır. 
        Eğer alt kategoride ürün bulunmazsa, mevcut derin kategorilere gidilerek ürünler aranır.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                self.current_sub_category = sub_cat_element.text.strip()
                self.current_deeper_category = None  # Her alt kategori için derin kategori bilgisi sıfırlansın
                print(f"    [INFO] Alt kategoriye tıklanıyor: {self.current_sub_category}")
                sub_cat_element.click()
                time.sleep(2)
                
                product_count = self.get_product_count()
                if product_count > 0:
                    print(f"    [INFO] Bu alt kategoride {product_count} ürün tespit edildi.")
                    self.scrape_products()
                else:
                    print("    [INFO] Alt kategoride ürün bulunamadı, daha derin kategorilere gidiliyor.")
                    # Derin kategorileri dene
                    deeper_categories = self.get_deeper_category_elements()
                    deeper_found = False
                    for deeper_elem, deeper_text in deeper_categories:
                        try:
                            print(f"        [INFO] Daha derin kategoriye tıklanıyor: {deeper_text}")
                            self.current_deeper_category = deeper_text
                            deeper_elem.click()
                            time.sleep(2)
                            
                            deeper_product_count = self.get_product_count()
                            if deeper_product_count > 0:
                                print(f"        [INFO] Bu derin kategoride {deeper_product_count} ürün tespit edildi.")
                                self.scrape_products()
                                deeper_found = True
                            else:
                                print("        [INFO] Derin kategoride ürün bulunamadı.")
                            
                            self.driver.back()  # Derin kategori sayfasından alt kategori sayfasına geri dön
                            time.sleep(2)
                        except Exception as e:
                            print(f"        [WARNING] Derin kategoriye tıklanırken hata: {str(e)}")
                    if not deeper_found:
                        print("    [INFO] Hiçbir derin kategoride ürün bulunamadı.")
                
                self.driver.back()  # Alt kategori sayfasından, ana kategori alt kategori listesinin bulunduğu sayfaya geri dön
                time.sleep(2)
            except NoSuchElementException:
                print("    [WARNING] Daha fazla alt kategori bulunamadı.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı.")
                break
    
    def get_deeper_category_elements(self, start_index=1, max_attempts=50):
        """
        Alt kategorideki daha derin (altın alt) kategori elementlerini döndürür.
        """
        deeper_categories = []
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                elem = self.driver.find_element(By.XPATH, deeper_xpath)
                text = elem.text.strip()
                if text:
                    deeper_categories.append((elem, text))
            except NoSuchElementException:
                break
        return deeper_categories
    
    def get_product_count(self):
        """
        Sayfadaki ürün kartı elementlerinin sayısını döndürür.
        """
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0
    
    def scrape_products(self):
        """
        Sayfadaki ürünlerin metinsel bilgilerini ve ekran görüntülerini toplar.
        Ürün adı, ekran görüntüsü dosya isminde kullanılacak ve ürünler, kategori hiyerarşisine göre klasörlendirilecektir.
        """
        count = self.get_product_count()
        if count == 0:
            return
        
        # Gerekirse sayfanın aşağı kaydırılması gibi işlemler eklenebilir.
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        if not product_elements:
            return
        
        products_data = []
        for idx, product in enumerate(product_elements, start=1):
            try:
                # Ürünün metinsel bilgilerinin bulunduğu alan
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                # Örneğin "sold" kelimesi geçiyorsa, ürünü işleyelim.
                if "sold" not in container_text.lower():
                    continue
                
                # Ürün başlığı, varsayılan olarak metnin ilk satırından alınır.
                product_title = container_text.splitlines()[0]
                print(f"        [INFO] Ürün bulundu: {product_title}")
                
                # Ürün elementini görünür yapmak için kaydır.
                self.scroll_to_element(product)
                
                # Ürünün ekran görüntüsü, ürün ismi ve kategori bilgilerine göre kaydediliyor.
                screenshot_path = self.take_product_screenshot(product, product_title)
                
                products_data.append({
                    "full_text": container_text,
                    "screenshot_path": screenshot_path,
                    "product_title": product_title,
                    "category": {
                        "main": self.current_main_category,
                        "sub": self.current_sub_category,
                        "deeper": self.current_deeper_category
                    }
                })
            except Exception as e:
                print(f"        [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
        
        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] {len(products_data)} ürün kaydedildi: {filename}")
    
    def smooth_scroll(self):
        """
        Ürünlerin tam yüklenebilmesi için sayfayı yavaşça kaydırır.
        """
        scroll_pause_time = 0.5
        screen_height = self.driver.execute_script("return window.innerHeight")
        scroll_amount = screen_height * 0.8
        
        for i in range(5):
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(scroll_pause_time)
    
    def scroll_to_element(self, element):
        """
        Verilen elementin ekrana kaydırılmasını sağlar.
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(1)
    
    def take_product_screenshot(self, product_element, product_title):
        """
        Ürün elementinin ekran görüntüsünü alır. 
        Dosya ismi, ürün adı (sanitize edilmiş) ve zaman damgasını içerir; 
        ekran görüntüleri, kategori hiyerarşisine göre klasörlendirilecektir.
        """
        try:
            sanitized_title = self.sanitize_filename(product_title)
            timestamp = int(time.time())
            
            # Klasör yapısını oluştur: ana kategori / alt kategori / (varsa) derin kategori
            folder_path = os.path.join(self.base_screenshot_dir, self.current_main_category, self.current_sub_category)
            if self.current_deeper_category:
                folder_path = os.path.join(folder_path, self.current_deeper_category)
            os.makedirs(folder_path, exist_ok=True)
            
            screenshot_filename = f"{sanitized_title}_{timestamp}.png"
            screenshot_path = os.path.join(folder_path, screenshot_filename)
            
            product_element.screenshot(screenshot_path)
            print(f"        [INFO] Ekran görüntüsü alındı: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            print(f"        [ERROR] Ekran görüntüsü alma hatası: {str(e)}")
            return None
    
    def sanitize_filename(self, name):
        """
        Dosya isimlerinde kullanılmayacak karakterleri temizler.
        """
        sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
        sanitized = sanitized.strip().replace(" ", "_")
        return sanitized
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    
    collector.go_to_ebay()
    collector.explore_main_categories()
    
    collector.close()