from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
import time

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
    
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
                print(f"[WARNING] Kategori işlenemedi: {str(e)}")
                break
    
    def explore_sub_categories(self, start_index=3, max_attempts=50):
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'//section[@class="section-wrapper"]//li[{i}]/a'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(3)
                
                # Yavaş scroll ve ürün kontrolü
                if self.has_products():
                    self.scroll_gradually()
                    self.explore_deeper_categories()
                    product_count = self.get_category_product_count()
                    print(f"    [INFO] Ürün sayısı: {product_count}")
                    self.scrape_products()
                
                self.driver.back()
                time.sleep(2)
            except Exception as e:
                print(f"    [WARNING] Alt kategori hatası: {str(e)}")
                break
    
    def has_products(self):
        """Sayfada ürün olup olmadığını kontrol eder"""
        return len(self.driver.find_elements(By.XPATH, '//ul[contains(@class, "srp-results")]/li')) > 0
    
    def scroll_gradually(self, step=500, delay=0.5):
        """Sayfayı yavaşça kaydırarak tüm içeriği yükler"""
        current_height = 0
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while current_height < total_height:
            current_height += step
            self.driver.execute_script(f"window.scrollTo(0, {current_height});")
            time.sleep(delay)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == total_height:
                break
            total_height = new_height
    
    def explore_deeper_categories(self):
        """Daha derin kategoriler için esnek XPath"""
        try:
            categories = self.driver.find_elements(By.XPATH, '//section[contains(@class, "section-wrapper")]//li/a')
            for cat in categories:
                print(f"        [ALT KATEGORI] {cat.text.strip()}")
        except NoSuchElementException:
            pass
    
    def get_category_product_count(self):
        try:
            return self.driver.find_element(By.XPATH, '//h1[contains(@class, "srp-controls__count-heading")]').text
        except NoSuchElementException:
            return "0"
    
    def scrape_products(self):
        try:
            products = self.driver.find_elements(By.XPATH, '//ul[contains(@class, "srp-results")]/li[contains(@class, "s-item")]')
            print(f"    [TARAMA] {len(products)} ürün bulundu")
            
            for product in products[2:]:  # İlk 2 elementi atla
                try:
                    # Fiyat bilgisi
                    price = product.find_element(By.XPATH, './/span[contains(@class, "s-item__price")]').text
                    
                    # Satış bilgisi için esnek arama
                    sold = ""
                    try:
                        sold_element = product.find_element(By.XPATH, './/span[contains(text(), "sold")]')
                        sold = sold_element.text
                    except:
                        pass
                    
                    # Satış adedi kontrolü
                    if sold:
                        sold_num = int(''.join(filter(str.isdigit, sold.split()[0])))
                        if sold_num > 50:
                            print(f"        🔍 Ürün: {price} | Satış: {sold}")
                except Exception as e:
                    print(f"        [HATA] Ürün işlenemedi: {str(e)}")
        except Exception as e:
            print(f"    [HATA] Ürünler alınamadı: {str(e)}")
    
    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path)
    collector.go_to_ebay()
    collector.explore_main_categories()
    collector.close()