import json
import os
import time
import requests
import shutil
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
        
        # Görseller için temel klasör
        self.base_image_dir = "product_images"
        os.makedirs(self.base_image_dir, exist_ok=True)
    
    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=3, end_index=12):
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
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı.")
                break
    
    def explore_sub_categories(self, start_index=3, max_attempts=50):
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                self.explore_deeper_categories()
                product_count = self.get_product_count()
                print(f"    [INFO] Bu alt kategoride {product_count} ürün tespit edildi.")
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
                print("    [WARNING] Alt kategoriye tıklanamadı.")
                break
    
    def explore_deeper_categories(self, start_index=3, max_attempts=50):
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_text = deeper_elem.text.strip()
                print(f"        [INFO] Daha derin kategori bulundu: {deeper_text}")
            except NoSuchElementException:
                break
    
    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0
    
    def scrape_products(self):
        count = self.get_product_count()
        if count == 0:
            return
        
        timeout = 30
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.get_product_count() > 0:
                break
            self.driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(1)
        
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        if not product_elements:
            return
        
        products_data = []
        for idx, product in enumerate(product_elements, start=1):
            try:
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                if "sold" not in container_text.lower():
                    continue

                # Görsel işlemleri
                image_url = self.extract_image_url(product)
                image_path = self.download_image(image_url, idx) if image_url else None

                products_data.append({
                    "full_text": container_text,
                    "image_path": image_path
                })
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
        
        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] {len(products_data)} ürün kaydedildi: {filename}")

    def extract_image_url(self, product_element):
        try:
            image_container = product_element.find_element(By.XPATH, "./div/div/div[1]")
            img = image_container.find_element(By.TAG_NAME, "img")
            return img.get_attribute("src") or img.get_attribute("data-src")
        except Exception as e:
            print(f"    [WARNING] Görsel bulunamadı: {str(e)}")
            return None

    def download_image(self, url, product_index):
        try:
            unique_id = f"{int(time.time())}_{product_index}"
            product_dir = os.path.join(self.base_image_dir, unique_id)
            os.makedirs(product_dir, exist_ok=True)
            
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                image_path = os.path.join(product_dir, "image.jpg")
                with open(image_path, "wb") as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
                return image_path
        except Exception as e:
            print(f"    [ERROR] Görsel indirme hatası: {str(e)}")
        return None
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    collector.explore_main_categories(start_index=3, end_index=12)
    collector.close()