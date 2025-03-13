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
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
        self.current_category_path = []

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)

    def explore_main_categories(self, start_index=3, end_index=12):
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"\n[ANA KATEGORI] {category_text}")
                self.current_category_path = [category_text]
                category_element.click()
                time.sleep(2)
                
                self.process_category_page()
                
                self.driver.back()
                time.sleep(2)
            except Exception as e:
                print(f"Hata: {str(e)}")
                continue

    def process_category_page(self, depth=0, max_depth=4):
        if depth > max_depth:
            return

        # 1. Intermediate kategorileri kontrol et
        intermediate_cats = self.driver.find_elements(By.XPATH, '//div[@class="b-visualnav__grid"]/a')
        if intermediate_cats:
            print(f"  {'  ' * depth}-> Intermediate kategoriler bulundu")
            for idx, cat in enumerate(intermediate_cats[:5], 1):
                try:
                    cat_name = cat.text.strip()
                    print(f"  {'  ' * depth}-> Intermediate kategori ({idx}): {cat_name}")
                    self.current_category_path.append(cat_name)
                    cat.click()
                    time.sleep(2)
                    
                    self.process_category_page(depth+1)
                    
                    self.driver.back()
                    time.sleep(2)
                    self.current_category_path.pop()
                except Exception as e:
                    print(f"  Hata: {str(e)}")
                    continue
            return

        # 2. Sonuç sayısını kontrol et
        results_count = self.get_results_count()
        product_count = self.get_product_count()
        
        if results_count > 0 or product_count > 0:
            print(f"  {'  ' * depth}-> Ürünler bulundu ({results_count} sonuç, {product_count} ürün)")
            self.scrape_products()
        else:
            print(f"  {'  ' * depth}-> Ürün bulunamadı, mini kategoriler aranıyor...")
            self.explore_mini_categories(depth)

    def explore_mini_categories(self, depth):
        mini_cats = self.driver.find_elements(By.XPATH, '//section[contains(@class, "b-module")]//a[@class="b-textlink"]')
        for idx, cat in enumerate(mini_cats[:10], 1):
            try:
                cat_name = cat.text.strip()
                if not cat_name:
                    continue
                    
                print(f"  {'  ' * depth}-> Mini kategori ({idx}): {cat_name}")
                self.current_category_path.append(cat_name)
                cat.click()
                time.sleep(2)
                
                self.process_category_page(depth+1)
                
                self.driver.back()
                time.sleep(2)
                self.current_category_path.pop()
            except Exception as e:
                print(f"  Hata: {str(e)}")
                continue

    def get_results_count(self):
        try:
            results_element = self.driver.find_element(By.XPATH, '//h2[contains(@class, "srp-controls__count-heading")]')
            results_text = results_element.text.strip()
            count_str = re.search(r'[\d,]+', results_text).group().replace(',', '')
            return int(count_str) if count_str.isdigit() else 0
        except:
            return 0

    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.XPATH, '//li[contains(@class, "s-item")]'))
        except:
            return 0

    def scrape_products(self):
        product_elements = self.driver.find_elements(By.XPATH, '//li[contains(@class, "s-item")]')
        products_data = []
        
        for idx, product in enumerate(product_elements[:5], 1):
            try:
                product_data = self.extract_product_info(product, idx)
                if product_data:
                    products_data.append(product_data)
            except Exception as e:
                print(f"Ürün çekme hatası: {str(e)}")

        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"  -> {len(products_data)} ürün kaydedildi: {filename}")

    def extract_product_info(self, product, idx):
        self.scroll_to_element(product)
        title = product.find_element(By.XPATH, './/div[@class="s-item__title"]').text.strip()
        price = product.find_element(By.XPATH, './/span[@class="s-item__price"]').text.strip()
        screenshot_path = self.take_product_screenshot(product, title, idx)
        
        return {
            "title": title,
            "price": price,
            "category_path": " > ".join(self.current_category_path),
            "screenshot_path": screenshot_path
        }

    def take_product_screenshot(self, element, title, idx):
        try:
            sanitized_title = re.sub(r'[\\/*?:"<>|]', '', title)[:50]
            filename = f"{sanitized_title}_{idx}.png"
            category_dir = os.path.join(self.base_screenshot_dir, *self.current_category_path)
            os.makedirs(category_dir, exist_ok=True)
            path = os.path.join(category_dir, filename)
            element.screenshot(path)
            return path
        except Exception as e:
            print(f"Ekran görüntüsü hatası: {str(e)}")
            return None

    def scroll_to_element(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.5)

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    collector = ProductCollectorAI(driver_path="/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
    collector.go_to_ebay()
    collector.explore_main_categories()
    collector.close()