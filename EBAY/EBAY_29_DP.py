import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class EnhancedProductCollector:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.base_screenshot_dir = "categorized_products"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
        self.current_category_path = []

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, categories=[4,6,8]):
        for i in categories:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[MAIN] Ana kategori: {category_text}")
                
                self.current_category_path = [category_text]
                category_element.click()
                time.sleep(2)
                
                self.explore_sub_categories()
                
                self.driver.back()
                time.sleep(2)
            except Exception as e:
                print(f"[ERROR] Ana kategori {i} işlenemedi: {str(e)}")
    
    def explore_sub_categories(self, max_attempts=15):
        for sub_idx in range(1, max_attempts+1):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{sub_idx}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"\n[SUB] Alt kategori: {sub_cat_text}")
                
                self.current_category_path.append(sub_cat_text)
                sub_cat_element.click()
                time.sleep(3)
                
                product_count = self.get_product_count()
                
                if product_count > 0:
                    self.scrape_products()
                    self.current_category_path.pop()
                    self.driver.back()
                    time.sleep(2)
                    continue
                
                deeper_found = self.explore_deeper_subcategories()
                if not deeper_found:
                    print("[SUB] Derin kategorilerde ürün bulunamadı")
                    self.driver.back()
                    time.sleep(2)
                    self.current_category_path.pop()
                else:
                    self.current_category_path.pop()
                    
            except Exception as e:
                print(f"[SUB] Alt kategori {sub_idx} hata: {str(e)}")
                break
    
    def explore_deeper_subcategories(self):
        print("[DEEP] Derin kategoriler araştırılıyor...")
        for deep_idx in range(1, 15):
            deep_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{deep_idx}]'
            try:
                deep_element = self.driver.find_element(By.XPATH, deep_xpath)
                deep_text = deep_element.text.strip()
                print(f"[DEEP] Derin kategori: {deep_text}")
                
                self.current_category_path.append(deep_text)
                deep_element.click()
                time.sleep(3)
                
                product_count = self.get_product_count()
                
                if product_count > 0:
                    self.scrape_products()
                    self.current_category_path.pop()
                    self.driver.back()
                    time.sleep(2)
                    return True
                
                self.current_category_path.pop()
                self.driver.back()
                time.sleep(2)
                
            except Exception as e:
                print(f"[DEEP] Derin kategori {deep_idx} hata: {str(e)}")
                return False
        return False
    
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
        for idx, product in enumerate(product_elements, 1):
            try:
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                if "sold" not in container_text.lower():
                    continue
                
                product_name = self.extract_product_name(container_text)
                screenshot_path = self.save_product_screenshot(product, product_name)
                
                products_data.append({
                    "category": "/".join(self.current_category_path),
                    "product_name": product_name,
                    "details": container_text,
                    "screenshot": screenshot_path
                })
                
            except Exception as e:
                print(f"[SCRAPE] Ürün {idx} hata: {str(e)}")
        
        if products_data:
            self.save_to_json(products_data)
    
    def extract_product_name(self, text):
        lines = text.split('\n')
        if lines:
            name = lines[0].strip()
            return self.sanitize_filename(name)
        return "unknown_product"
    
    def sanitize_filename(self, name):
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name[:50]
    
    def save_product_screenshot(self, element, product_name):
        try:
            category_dir = os.path.join(self.base_screenshot_dir, *self.current_category_path)
            os.makedirs(category_dir, exist_ok=True)
            
            timestamp = str(int(time.time()))[-5:]
            filename = f"{product_name}_{timestamp}.png"
            filepath = os.path.join(category_dir, filename)
            
            self.scroll_to_element(element)
            element.screenshot(filepath)
            return filepath
            
        except Exception as e:
            print(f"[SCREENSHOT] Hata: {str(e)}")
            return None
    
    def save_to_json(self, data):
        filename = f"products_{int(time.time())}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SAVE] {len(data)} ürün kaydedildi: {filename}")
    
    def scroll_to_element(self, element):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(0.5)
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    DRIVER_PATH = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = EnhancedProductCollector(DRIVER_PATH)
    
    try:
        collector.go_to_ebay()
        collector.explore_main_categories(categories=[4,6,8])
    finally:
        collector.close()