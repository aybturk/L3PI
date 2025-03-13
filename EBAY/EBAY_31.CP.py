import json
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        # Gerekirse headless modunu açabilirsiniz.
        # options.add_argument("--headless")
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Ekran görüntülerinin kaydedileceği temel klasör
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
    
    def sanitize_filename(self, name):
        """Dosya adı için uygun karakterler kullanmak üzere string’i temizler."""
        return re.sub(r'(?u)[^-\w.]', '_', name)
    
    def go_to_ebay(self):
        """
        eBay ana sayfasına gider.
        """
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self):
        """
        Ana kategori seçiminde yalnızca 4, 6 ve 8 numaralı kategorilere tıklar.
        """
        # Ana kategorilerde kullanılacak indexler:
        main_category_indexes = [4, 6, 8]
        for i in main_category_indexes:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Seçilen ana kategori altındaki alt kategorileri işle
                self.explore_sub_categories(main_category_name=category_text)
                
                # Ana kategori sayfasına geri dön
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı.")
                break
    
    def explore_sub_categories(self, start_index=1, max_attempts=10, main_category_name=""):
        """
        Seçilen ana kategorideki alt kategorileri dolaşır.
        İstenen geliştirme: Eğer alt kategoride ürün bulunmazsa,
        bulunan 'daha derin' kategorilere inerek ürün araması yapar.
        Ayrıca, alt kategoriye tıklanınca sayfayı aşağı kaydırarak ürünlerin görünmesini sağlar.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Alt kategoriye tıklandığında sayfayı aşağı kaydırarak ürünlerin yüklenmesini sağla
                self.scroll_down_a_bit()
                
                # Alt kategoride ürün var mı kontrol et
                product_count = self.get_product_count()
                if product_count > 0:
                    print(f"    [INFO] Bu alt kategoride {product_count} ürün tespit edildi.")
                    self.scrape_products(category_name=sub_cat_text)
                else:
                    print("    [INFO] Alt kategoride ürün bulunamadı, daha derin kategorilere gidiliyor.")
                    deeper_elements = self.get_deeper_category_elements()
                    if deeper_elements:
                        for deeper_cat_element in deeper_elements:
                            deeper_cat_text = deeper_cat_element.text.strip()
                            print(f"        [INFO] Daha derin kategoriye tıklanıyor: {deeper_cat_text}")
                            deeper_cat_element.click()
                            time.sleep(2)
                            self.scroll_down_a_bit()
                            
                            deeper_product_count = self.get_product_count()
                            if deeper_product_count > 0:
                                print(f"        [INFO] Bu daha derin kategoride {deeper_product_count} ürün tespit edildi.")
                                self.scrape_products(category_name=deeper_cat_text)
                            else:
                                print("        [INFO] Daha derin kategoride ürün bulunamadı.")
                            # Daha derin kategori tamamlandıktan sonra alt kategoriye geri dön
                            self.driver.back()
                            time.sleep(2)
                    else:
                        print("    [INFO] Alt kategori için daha derin kategori bulunamadı.")
                
                # Alt kategori işlemi tamamlandıktan sonra ana kategoriye geri dön
                self.driver.back()
                time.sleep(2)
                
                # Alt kategoriler arasında gezinmeden önce sayfayı aşağı kaydır ve "Load More" butonunu kontrol et
                self.scroll_down_a_bit()
                self.check_and_click_more_button()
                
            except NoSuchElementException:
                print("    [WARNING] Daha fazla alt kategori bulunamadı.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı.")
                break
    
    def get_deeper_category_elements(self, start_index=1, max_attempts=50):
        """
        Mevcut alt kategori içinde varsa daha derin kategorileri liste olarak döndürür.
        """
        deeper_elements = []
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_elements.append(deeper_elem)
            except NoSuchElementException:
                break
        return deeper_elements

    def get_product_count(self):
        """
        Sayfadaki ürünlerin (listelenmiş kartların) sayısını döndürür.
        """
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0
    
    def scrape_products(self, category_name=""):
        """
        Sayfadaki ürünlerin metinsel bilgilerini ve ekran görüntülerini toplar.
        Kaydedilen ekran görüntüleri, ürün ismi ve kategori bilgisine göre dosyalandırılır.
        """
        count = self.get_product_count()
        if count == 0:
            return
        
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        if not product_elements:
            return
        
        products_data = []
        for idx, product in enumerate(product_elements, start=1):
            try:
                # Ürünle ilgili bilgi alanını bul
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                # İsteğe bağlı filtre: yalnızca "sold" ifadesi içeren ürünler işleniyor
                if "sold" not in container_text.lower():
                    continue
                
                # Ürün ismini, container içerisindeki ilk satırdan alalım
                product_name = container_text.split("\n")[0].strip()
                print(f"        [INFO] Ürün işleniyor: {product_name}")
                
                # Ürün elementini görünür kılmak için kaydır
                self.scroll_to_element(product)
                
                # Ekran görüntüsünü al (ürün ismi ve kategori bilgisiyle dosyalandırılır)
                screenshot_path = self.take_product_screenshot(product, idx, category_name, product_name)
                
                products_data.append({
                    "product_name": product_name,
                    "full_text": container_text,
                    "screenshot_path": screenshot_path
                })
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
        
        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] {len(products_data)} ürün kaydedildi: {filename}")
        
        # Ürünlerin tam yüklenmesi için sayfayı yavaşça kaydır
        scroll_pause_time = 0.5
        screen_height = self.driver.execute_script("return window.innerHeight")
        scroll_amount = screen_height * 0.8
        for i in range(5):
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(scroll_pause_time)
    
    def scroll_down_a_bit(self):
        """
        Sayfada aşağı doğru kaydırma işlemi yaparak örneğin 'Load More' butonunun veya ürünlerin görünmesini sağlar.
        """
        self.driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)
    
    def scroll_to_element(self, element):
        """
        Verilen elementin ekranda ortalanmasını sağlar.
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(1)
    
    def check_and_click_more_button(self):
        """
        Sayfada varsa '/html/body/div[2]/div[2]/section[2]/section[1]/div/div/button'
        konumundaki 'Load More' butonuna tıklar.
        """
        try:
            more_button_xpath = '/html/body/div[2]/div[2]/section[2]/section[1]/div/div/button'
            more_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, more_button_xpath))
            )
            
            button_text = more_button.text.strip().lower()
            
            if "more" in button_text and more_button.is_displayed() and more_button.is_enabled():
                print(f"    [INFO] 'Load More' butonu bulundu ({button_text}), tıklanıyor...")
                more_button.click()
                time.sleep(2)
            else:
                print(f"    [INFO] Buton tıklanabilir durumda değil veya metin 'More' içermiyor: {button_text}")
                
        except NoSuchElementException:
            pass
        except ElementClickInterceptedException:
            print("    [WARNING] 'Load More' butonuna tıklanamadı.")
        except Exception as e:
            print(f"    [ERROR] Buton kontrolünde beklenmeyen hata: {str(e)}")
    
    def take_product_screenshot(self, product_element, index, category_name, product_name):
        """
        Verilen web elementinin ekran görüntüsünü alır.
        Ekran görüntüsü dosya adı ürün ismi (temizlenmiş hali) ve kategoriye göre klasörlendirilir.
        """
        try:
            # Ürün ismini dosya adı için uygun hale getir
            sanitized_product_name = self.sanitize_filename(product_name)
            unique_id = f"{int(time.time())}_{index}"
            
            # Kategori adına göre klasör oluştur (kategori ismini de sanitize ediyoruz)
            category_dir = os.path.join(self.base_screenshot_dir, self.sanitize_filename(category_name))
            os.makedirs(category_dir, exist_ok=True)
            # Her ürün için benzersiz bir klasör oluştur
            product_dir = os.path.join(category_dir, f"{unique_id}_{sanitized_product_name}")
            os.makedirs(product_dir, exist_ok=True)
            
            screenshot_filename = f"{sanitized_product_name}_product_screenshot.png"
            screenshot_path = os.path.join(product_dir, screenshot_filename)
            
            product_element.screenshot(screenshot_path)
            return screenshot_path
        except Exception as e:
            print(f"    [ERROR] Ekran görüntüsü alma hatası: {str(e)}")
            return None
    
    def close(self):
        """
        Tarayıcıyı kapatır.
        """
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    
    # Ana akış
    collector.go_to_ebay()
    collector.explore_main_categories()
    collector.close()