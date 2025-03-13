import json
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        self.base_dir = "ebay_data"
        os.makedirs(self.base_dir, exist_ok=True)
        self.processed_categories = set()

    def sanitize_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', '', name).strip()[:50]

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "vl-flyout-nav"))
        )

    def explore_main_categories(self):
        main_categories = list(range(3, 12))
        for i in main_categories:
            try:
                category = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'))
                )
                category_name = self.sanitize_filename(category.text)
                if not category_name or category_name in self.processed_categories:
                    continue

                print(f"\n[ANA KATEGORI] {category_name}")
                category.click()
                time.sleep(1.5)

                self.process_category_level([category_name])
                self.processed_categories.add(category_name)
                self.driver.back()
                time.sleep(1.5)

            except Exception as e:
                print(f"Ana kategori hatası: {str(e)}")
                continue

    def process_category_level(self, category_path, depth=0):
        for section_num in [2, 1]:  # Önce kapalı sonra açık kategoriler
            try:
                section = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, f'//section[@class="b-module b-carousel b-display--landscape"]/section[{section_num}]'))
                )
                self.process_category_section(section, category_path, depth)
            except Exception:
                continue

    def process_category_section(self, section, category_path, depth):
        categories = section.find_elements(By.XPATH, './/li[contains(@class, "brwrvr__nav-item")]')
        print(f"  Bulunan kategoriler: {len(categories)}")

        for idx in range(1, len(categories)+1):
            try:
                category = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f'{section.get_attribute("xpath")}/div/ul/li[{idx}]'))
                )
                self.process_single_category(category, category_path, depth)
            except (StaleElementReferenceException, NoSuchElementException):
                continue

    def process_single_category(self, category, category_path, depth):
        category_name = self.sanitize_filename(category.text)
        if not category_name:
            return

        print(f"\n{'  ' * depth}[KATEGORI] {category_name}")
        current_path = category_path + [category_name]
        dir_path = os.path.join(self.base_dir, *current_path)
        os.makedirs(dir_path, exist_ok=True)

        try:
            category.click()
            time.sleep(1.5)
            
            if self.handle_product_page(current_path):
                return
                
            self.process_deep_categories(current_path, depth)
            
        except Exception as e:
            print(f"Kategori işleme hatası: {str(e)}")
        finally:
            self.driver.back()
            time.sleep(1.5)

    def handle_product_page(self, current_path):
        self.scroll_page()
        products = self.driver.find_elements(By.CSS_SELECTOR, 'li[class*="brwrvr__item-card--"]')
        
        if products:
            print(f"  !! Ürün bulundu ({len(products)} adet)")
            self.scrape_products(current_path, products)
            return True
        return False

    def process_deep_categories(self, current_path, depth):
        try:
            deep_section = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//section[contains(@class, "b-module b-list")]'))
            )
            deep_categories = deep_section.find_elements(By.XPATH, './/li[contains(@class, "brwlv__item")]')
            
            for d_idx in range(1, len(deep_categories)+1):
                try:
                    deep_category = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, f'{deep_section.get_attribute("xpath")}/div/ul/li[{d_idx}]'))
                    )
                    self.process_single_category(deep_category, current_path, depth+1)
                except Exception:
                    continue
                    
        except Exception:
            pass

    def scrape_products(self, category_path, products):
        products_data = []
        
        for product in products:
            try:
                self.scroll_to_element(product)
                product_data = self.extract_product_data(product, category_path)
                if product_data:
                    products_data.append(product_data)
            except Exception as e:
                print(f"Ürün işleme hatası: {str(e)}")

        if products_data:
            self.save_products_data(category_path, products_data)
            self.check_and_click_more_button(category_path)

    def extract_product_data(self, product, category_path):
        container = product.find_element(By.XPATH, './/div[@class="brwrvr__item-info"]')
        text = container.text.strip()
        
        if "sold" not in text.lower():
            return None

        product_name = self.sanitize_filename(text.split("\n")[0]) or f"urun_{time.time()}"
        screenshot_dir = os.path.join(self.base_dir, *category_path, product_name)
        os.makedirs(screenshot_dir, exist_ok=True)
        
        screenshot_path = os.path.join(screenshot_dir, "screenshot.png")
        product.screenshot(screenshot_path)
        
        return {
            "name": product_name,
            "text": text,
            "screenshot": screenshot_path
        }

    def save_products_data(self, category_path, data):
        json_path = os.path.join(self.base_dir, *category_path, "products.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  {len(data)} ürün kaydedildi")

    def check_and_click_more_button(self, category_path):
        try:
            button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(translate(., "LESS", "less"), "more")]'))
            )
            if "more" in button.text.lower():
                button.click()
                print("  Load More tıklandı")
                time.sleep(2)
                self.scrape_products(category_path, self.driver.find_elements(By.CSS_SELECTOR, 'li[class*="brwrvr__item-card--"]'))
        except Exception:
            pass

    def scroll_page(self):
        for _ in range(3):
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(0.5)

    def scroll_to_element(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.3)

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path)
    
    try:
        collector.go_to_ebay()
        collector.explore_main_categories()
    finally:
        collector.close()