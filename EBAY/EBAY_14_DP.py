import json
import time
import os
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class EnhancedProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        self.image_dir = "product_images"
        os.makedirs(self.image_dir, exist_ok=True)  # Görseller için klasör oluştur

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
            except (NoSuchElementException, ElementClickInterceptedException) as e:
                print(f"[WARNING] Kategori hatası: {str(e)}")
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
                
                if self.get_product_count() > 0:
                    self.scrape_products()
                
                self.driver.back()
                time.sleep(2)
            except (NoSuchElementException, ElementClickInterceptedException) as e:
                print(f"    [WARNING] Alt kategori hatası: {str(e)}")
                break

    def explore_deeper_categories(self):
        pass  # Gerekirse daha derin kategoriler için implementasyon

    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0

    def scrape_products(self):
        product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        products_data = []
        
        for product in product_elements:
            try:
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                if "sold" not in container_text.lower():
                    continue

                # Ürün Detaylarını Topla
                product_data = {
                    "title": self._extract_product_title(container),
                    "price": self._extract_product_price(container),
                    "condition": self._extract_product_condition(container),
                    "shipping_info": self._extract_shipping_info(container),
                    "sold_status": self._extract_sold_status(container),
                    "image_path": self._download_product_image(product)
                }

                products_data.append(product_data)
                
            except Exception as e:
                print(f"Ürün işlenirken hata: {str(e)}")
                continue

        if products_data:
            self._save_to_json(products_data)

    def _extract_product_title(self, container):
        try:
            return container.find_element(By.CSS_SELECTOR, "div.brwrvr__item-title").text.strip()
        except Exception:
            return "Başlık bulunamadı"

    def _extract_product_price(self, container):
        try:
            return container.find_element(By.CSS_SELECTOR, "span.brwrvr__item-price").text.strip()
        except Exception:
            return "Fiyat bilgisi yok"

    def _extract_product_condition(self, container):
        try:
            return container.find_element(By.CSS_SELECTOR, "div.brwrvr__item-condition").text.strip()
        except Exception:
            return "Durum bilgisi yok"

    def _extract_shipping_info(self, container):
        try:
            return container.find_element(By.CSS_SELECTOR, "div.brwrvr__item-shipping").text.strip()
        except Exception:
            return "Kargo bilgisi yok"

    def _extract_sold_status(self, container):
        try:
            return container.find_element(By.CSS_SELECTOR, "div.brwrvr__item-sold").text.strip()
        except Exception:
            return "Satış bilgisi yok"

    def _download_product_image(self, product_element):
        try:
            img_element = product_element.find_element(By.XPATH, ".//img")
            image_url = img_element.get_attribute("src")
            
            if not image_url:
                return None

            # Dosya adını oluştur
            product_title = self._extract_product_title(product_element)
            safe_title = re.sub(r'[^a-zA-Z0-9_]', '', product_title)[:30]
            timestamp = str(int(time.time()))
            filename = f"{safe_title}_{timestamp}.jpg"
            filepath = os.path.join(self.image_dir, filename)

            # Görseli indir
            response = requests.get(image_url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return filepath
            return None
        except Exception as e:
            print(f"Görsel indirme hatası: {str(e)}")
            return None

    def _save_to_json(self, data):
        filename = f"products_{int(time.time())}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"{len(data)} ürün kaydedildi: {filename}")

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = EnhancedProductCollectorAI(driver_path)
    try:
        collector.go_to_ebay()
        collector.explore_main_categories()
    finally:
        collector.close()