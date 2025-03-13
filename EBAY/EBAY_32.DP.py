import json
import os
import time
import re
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
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.base_screenshot_dir = "product_screenshots"
        self.current_main_category = "Unknown"
        self.current_sub_category = "Unknown"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self):
        """Sadece 4, 6 ve 8 numaralı ana kategorileri ziyaret eder"""
        for i in [4, 6, 8]:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                self.current_main_category = category_element.text.strip().replace("/", "_")
                print(f"[INFO] Ana kategoriye tıklanıyor: {self.current_main_category}")
                category_element.click()
                time.sleep(2)
                
                self.explore_sub_categories()
                self.driver.back()
                time.sleep(2)
                
            except (NoSuchElementException, ElementClickInterceptedException) as e:
                print(f"[WARNING] Kategori işlenirken hata: {str(e)}")
    
    def explore_sub_categories(self, max_attempts=15):
        """Alt kategori işleme mantığı geliştirildi"""
        for i in range(1, max_attempts + 1):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                self.current_sub_category = sub_cat_element.text.strip().replace("/", "_")
                print(f"    [INFO] Alt kategoriye tıklanıyor: {self.current_sub_category}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Sayfayı aşağı kaydır ve ürün yüklemelerini tetikle
                self.full_scroll()
                
                product_count = self.get_product_count()
                if product_count == 0:
                    print("    [INFO] Ürün bulunamadı, derin kategoriler aranıyor...")
                    if self.explore_deeper_categories():
                        continue  # Derin kategoride ürün bulundu, sonraki alt kategoriye geç
                else:
                    self.scrape_products()
                
                # Alt kategoriye geri dön
                self.driver.back()
                time.sleep(2)
                
            except (NoSuchElementException, ElementClickInterceptedException):
                break
    
    def explore_deeper_categories(self, max_depth=5):
        """Derin kategorilerde ürün arama"""
        for depth in range(1, max_depth + 1):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{depth}]'
            try:
                deeper_element = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_category = deeper_element.text.strip().replace("/", "_")
                print(f"        [INFO] Derin kategoriye tıklanıyor: {deeper_category}")
                deeper_element.click()
                time.sleep(2)
                
                self.full_scroll()
                
                product_count = self.get_product_count()
                if product_count > 0:
                    self.current_sub_category += f"_{deeper_category}"
                    self.scrape_products()
                    self.driver.back()
                    time.sleep(2)
                    return True  # Ürün bulunduğunu belirt
                
                self.driver.back()
                time.sleep(2)
                
            except (NoSuchElementException, ElementClickInterceptedException):
                break
        return False  # Hiçbir derin kategoride ürün bulunamadı
    
    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0
    
    def scrape_products(self):
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        if not product_elements:
            return
        
        products_data = []
        for product in product_elements:
            try:
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                # Ürün ismini ilk satırdan al ve temizle
                product_name = container_text.split('\n')[0].strip()
                product_name = re.sub(r'[\\/*?:"<>|]', '', product_name)[:50]  # Dosya ismi için güvenli hale getir
                
                # Klasör yapısını oluştur
                category_path = os.path.join(
                    self.base_screenshot_dir,
                    self.current_main_category,
                    self.current_sub_category
                )
                os.makedirs(category_path, exist_ok=True)
                
                # Ekran görüntüsü al
                screenshot_path = self.take_product_screenshot(product, product_name, category_path)
                
                products_data.append({
                    "product_name": product_name,
                    "category": f"{self.current_main_category}/{self.current_sub_category}",
                    "full_text": container_text,
                    "screenshot_path": screenshot_path
                })
                
            except Exception as e:
                print(f"    [WARNING] Ürün işlenirken hata: {str(e)}")
        
        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] {len(products_data)} ürün kaydedildi: {filename}")
    
    def full_scroll(self):
        """Sayfayı tamamen kaydırarak tüm ürünleri yükletme"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    
    def take_product_screenshot(self, element, product_name, category_path):
        """Ürün ismine göre ekran görüntüsü kaydetme"""
        try:
            safe_name = f"{product_name[:30]}_{int(time.time())}.png".replace(" ", "_")
            screenshot_path = os.path.join(category_path, safe_name)
            element.screenshot(screenshot_path)
            return screenshot_path
        except Exception as e:
            print(f"    [ERROR] Ekran görüntüsü hatası: {str(e)}")
            return None
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    
    try:
        collector.go_to_ebay()
        collector.explore_main_categories()
    finally:
        collector.close()