from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
import time

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 15)

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)

    def explore_main_categories(self, start_index=3, end_index=12):
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                category_text = category_element.text.strip()
                
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                
                self.explore_sub_categories()
                self.driver.back()
                time.sleep(2)
                
            except (NoSuchElementException, TimeoutException):
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı.")
                break

    def explore_sub_categories(self):
        try:
            container = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[2]/section[2]/section[1]/div/ul')))
            sub_categories = container.find_elements(By.TAG_NAME, 'li')[2:]  # 3. li'den başla
            
            for index, sub_cat in enumerate(sub_categories, 3):
                try:
                    sub_cat_text = sub_cat.text.strip()
                    print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                    sub_cat.click()
                    time.sleep(1.5)
                    
                    self.explore_deeper_categories()
                    
                    product_count = self.get_category_product_count()
                    print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
                    
                    self.scrape_products()
                    
                    self.driver.back()
                    time.sleep(2)
                    break  # TEST AMAÇLI SADECE İLK ALT KATEGORİYİ İŞLE
                    
                except Exception as e:
                    print(f"    [ERROR] Alt kategori işlenirken hata: {str(e)}")
                    self.driver.back()
                    continue
                    
        except Exception as e:
            print(f"    [ERROR] Alt kategori konteynırı bulunamadı: {str(e)}")

    def explore_deeper_categories(self):
        try:
            deeper_container = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul')))
            deeper_categories = deeper_container.find_elements(By.TAG_NAME, 'li')
            
            for cat in deeper_categories:
                print(f"        [INFO] Daha derin kategori bulundu: {cat.text.strip()}")
                
        except Exception as e:
            print("        [WARNING] Derin kategori bulunamadı")

    def get_category_product_count(self):
        try:
            self.driver.execute_script("window.scrollTo(0, 500)")
            time.sleep(1)
            
            count_element = self.wait.until(EC.visibility_of_element_located(
                (By.XPATH, '//*[@class="srp-controls__count-heading"]')))
            return count_element.text.strip()
            
        except Exception as e:
            print("    [WARNING] Ürün sayısı alınamadı")
            return "Bilinmiyor"

    def scrape_products(self):
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while True:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            products = self.wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, '//li[contains(@class, "s-item")]')))
            
            print(f"    [INFO] Toplam {len(products)} ürün bulundu")
            
            for product in products:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", product)
                    time.sleep(0.3)
                    
                    price = product.find_element(By.XPATH, './/span[@class="s-item__price"]').text
                    sold_info = ""
                    
                    try:
                        sold_info = product.find_element(By.XPATH, './/span[@class="s-item__hotness s-item__itemHotness"]').text
                        sold_number = int(''.join(filter(str.isdigit, sold_info)))
                        if sold_number > 50:
                            print(f"        Ürün: Fiyat={price}, Satış={sold_info}")
                            
                    except NoSuchElementException:
                        pass
                        
                except Exception as e:
                    print(f"        [ERROR] Ürün işlenirken hata: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"    [ERROR] Ürün listesi alınamadı: {str(e)}")

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    collector.explore_main_categories(start_index=3, end_index=12)
    collector.close()