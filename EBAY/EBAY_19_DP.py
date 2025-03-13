import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
    
    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=6, end_index=12):
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                self.explore_sub_categories()
                
                self.driver.back()
                time.sleep(2)
            except (NoSuchElementException, ElementClickInterceptedException) as e:
                print(f"[WARNING] Kategori işlenemedi: {str(e)}")
                break
    
    def explore_sub_categories(self):
        counter = 0
        for i in range(1, 50):  # Alt kategoriler 1'den başlıyor
            # Her 10 kategoride bir daha fazla yükleme butonunu kontrol et
            if counter % 10 == 0:
                self.check_and_click_more_button()
            
            try:
                sub_cat_element = self.driver.find_element(
                    By.XPATH, f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
                )
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                self.explore_deeper_categories()
                
                product_count = self.get_product_count()
                print(f"    [INFO] Ürün sayısı: {product_count}")
                if product_count > 0:
                    self.scrape_products()
                
                self.driver.back()
                time.sleep(2)
                counter += 1
            except Exception as e:
                print(f"    [WARNING] Alt kategori hatası: {str(e)}")
                break
    
    def check_and_click_more_button(self):
        """Daha fazla alt kategori yükleme butonunu kontrol eder"""
        try:
            self.smooth_scroll()
            more_button = self.driver.find_element(
                By.XPATH, '/html/body/div[2]/div[2]/section[2]/section[1]/div/div/button'
            )
            print("    [ACTION] Daha fazla alt kategori yükleniyor...")
            more_button.click()
            time.sleep(2)
        except Exception:
            pass
    
    def explore_deeper_categories(self):
        """Daha derin kategorileri pasif şekilde listeler"""
        for i in range(1, 10):
            try:
                element = self.driver.find_element(
                    By.XPATH, f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
                )
                print(f"        [INFO] Derin kategori: {element.text.strip()}")
            except Exception:
                break
    
    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card"))
        except Exception:
            return 0
    
    def scrape_products(self):
        self.smooth_scroll()
        products = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card")
        
        products_data = []
        for idx, product in enumerate(products[:5], 1):  # İlk 5 ürün
            try:
                self.scroll_to_element(product)
                text_content = product.text.split('\n')
                screenshot_path = self.take_product_screenshot(product, idx)
                
                products_data.append({
                    "title": text_content[0] if len(text_content) > 0 else "",
                    "price": text_content[1] if len(text_content) > 1 else "",
                    "screenshot": screenshot_path
                })
            except Exception as e:
                print(f"    [ERROR] Ürün kaydı: {str(e)}")
        
        if products_data:
            self.save_to_json(products_data)
    
    def take_product_screenshot(self, element, index):
        try:
            filename = f"product_{int(time.time())}_{index}.png"
            path = os.path.join(self.base_screenshot_dir, filename)
            element.screenshot(path)
            return path
        except Exception as e:
            print(f"    [ERROR] Ekran görüntüsü: {str(e)}")
            return ""
    
    def smooth_scroll(self):
        self.driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(0.5)
    
    def scroll_to_element(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth'});", element)
        time.sleep(1)
    
    def save_to_json(self, data):
        filename = f"products_{int(time.time())}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"    [SUCCESS] {len(data)} ürün kaydedildi")
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    collector = ProductCollectorAI("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
    try:
        collector.go_to_ebay()
        collector.explore_main_categories()
    finally:
        collector.close()