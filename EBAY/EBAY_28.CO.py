import os
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless")  # İsterseniz headless modunu açabilirsiniz
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Ekran görüntüleri için temel klasör
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)
        
        # Ürün verilerini tutmak için liste
        self.all_products_data = []

    def go_to_ebay(self):
        """
        eBay ana sayfasına gider.
        """
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)

    def explore_main_categories(self, indices=[4, 6, 8]):
        """
        eBay ana sayfasında belirtilen ana kategori indekslerine göre dolaşır.
        """
        for i in indices:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Alt ve Main kategorileri keşfet
                self.explore_subcategories_and_main_categories()
                
                # Ana sayfaya geri dön
                self.driver.get("https://www.ebay.com/")
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı.")
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı.")
            except Exception as e:
                print(f"[ERROR] Ana kategori keşfi sırasında hata: {str(e)}")

    def explore_subcategories_and_main_categories(self):
        """
        Mevcut sayfadaki alt kategorileri ve varsa Main kategori 2'leri keşfeder.
        """
        try:
            category_list_xpath = '/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li'
            main_categories = self.driver.find_elements(By.XPATH, category_list_xpath)
            for idx, category in enumerate(main_categories, start=1):
                try:
                    self.scroll_to_element(category)
                    category_text = category.text.strip()
                    print(f"    [INFO] Kategoriye tıklanıyor: {category_text}")
                    category.click()
                    time.sleep(2)
                    
                    if self.is_same_page():
                        print("    [INFO] Aynı sayfada kaldık, alt kategoriler açıldı.")
                        self.explore_subcategories(parent_xpath=f'{category_list_xpath}[{idx}]')
                    else:
                        print("    [INFO] Yeni sayfaya yönlendirildik.")
                        self.process_category()
                        self.driver.back()
                        time.sleep(2)
                        continue

                    # Alt kategorileri gizlemek için tekrar tıkla
                    category.click()
                    time.sleep(1)
                except Exception as e:
                    print(f"    [ERROR] Kategori işlenirken hata: {str(e)}")
                    continue
        except Exception as e:
            print(f"[ERROR] Kategoriler bulunamadı: {str(e)}")

    def is_same_page(self):
        """
        Sayfa URL'sinin değişip değişmediğini kontrol eder.
        """
        # Bu fonksiyonu tıklamadan önceki ve sonraki URL'leri karşılaştırmak için genişletebilirsiniz.
        return True  # Basitçe aynı sayfada kaldığımızı varsayıyoruz

    def explore_subcategories(self, parent_xpath):
        """
        Verilen ana kategorinin alt kategorilerini keşfeder.
        """
        subcategory_xpath = f"{parent_xpath}/section/div/section/div/ul/li"
        try:
            subcategories = self.driver.find_elements(By.XPATH, subcategory_xpath)
            for idx, subcat in enumerate(subcategories, start=1):
                try:
                    self.scroll_to_element(subcat)
                    subcat_text = subcat.text.strip()
                    print(f"        [INFO] Alt kategoriye tıklanıyor: {subcat_text}")
                    subcat.click()
                    time.sleep(2)

                    if self.has_products():
                        self.scrape_products()
                    else:
                        print("        [INFO] Ürün bulunamadı, mini kategorilere bakılıyor.")
                        self.explore_mini_categories()
                    
                    # Geri dön
                    self.driver.back()
                    time.sleep(2)
                except Exception as e:
                    print(f"        [ERROR] Alt kategori işlenirken hata: {str(e)}")
                    self.driver.back()
                    time.sleep(2)
                    continue
        except Exception as e:
            print(f"    [ERROR] Alt kategoriler bulunamadı: {str(e)}")

    def explore_mini_categories(self):
        """
        Alt kategorinin daha derin seviyedeki mini kategorilerini keşfeder.
        """
        mini_cat_xpath = '//section[contains(@class, "b-modules")]//ul/li/a'
        try:
            mini_categories = self.driver.find_elements(By.XPATH, mini_cat_xpath)
            for idx, mini_cat in enumerate(mini_categories, start=1):
                try:
                    self.scroll_to_element(mini_cat)
                    mini_cat_text = mini_cat.text.strip()
                    print(f"            [INFO] Mini kategoriye tıklanıyor: {mini_cat_text}")
                    mini_cat.click()
                    time.sleep(2)
                    
                    if self.has_products():
                        self.scrape_products()
                    else:
                        print("            [INFO] Bu mini kategoride ürün bulunamadı.")
                    
                    # Geri dön
                    self.driver.back()
                    time.sleep(2)
                except Exception as e:
                    print(f"            [ERROR] Mini kategori işlenirken hata: {str(e)}")
                    self.driver.back()
                    time.sleep(2)
                    continue
        except Exception as e:
            print(f"        [ERROR] Mini kategoriler bulunamadı: {str(e)}")

    def has_products(self):
        """
        Sayfada ürün olup olmadığını kontrol eder.
        """
        try:
            for i in range(2, 5):
                results_xpath = f'/html/body/div[2]/div[2]/section[{i}]//h2[contains(@class, "brw-controls__count")]'
                result_element = self.driver.find_element(By.XPATH, results_xpath)
                result_text = result_element.text.strip()
                if "result" in result_text.lower():
                    print(f"        [INFO] Ürün bulundu: {result_text}")
                    return True
        except NoSuchElementException:
            pass
        return False

    def scrape_products(self):
        """
        Sayfadaki ürünlerin metinsel bilgilerini ve ekran görüntülerini toplar.
        """
        try:
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
            if not product_elements:
                print("        [INFO] Ürün listesi bulunamadı.")
                return
            
            print(f"        [INFO] {len(product_elements)} ürün bulundu, işleniyor...")
            products_data = []
            for idx, product in enumerate(product_elements, start=1):
                try:
                    container = product.find_element(By.XPATH, "./div/div/div[2]")
                    container_text = container.text.strip()
                    
                    product_name = container.find_element(By.XPATH, ".//a").text.strip()
                    
                    self.scroll_to_element(product)
                    
                    screenshot_path = self.take_product_screenshot(product, product_name)
                    
                    products_data.append({
                        "product_name": product_name,
                        "full_text": container_text,
                        "screenshot_path": screenshot_path
                    })
                except Exception as e:
                    print(f"            [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
                    continue
            
            if products_data:
                self.all_products_data.extend(products_data)
                print(f"        [INFO] {len(products_data)} ürün kaydedildi.")
        except Exception as e:
            print(f"        [ERROR] Ürünler işlenirken hata: {str(e)}")

    def scroll_to_element(self, element):
        """
        Verilen elementin ekrana kaydırılmasını sağlar.
        """
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                element
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"        [ERROR] Element kaydırılırken hata: {str(e)}")

    def take_product_screenshot(self, product_element, product_name):
        """
        Bir web elementinin ekran görüntüsünü ürün ismiyle kaydeder.
        """
        try:
            safe_product_name = "".join(x for x in product_name if x.isalnum() or x in "._- ")
            timestamp = int(time.time())
            filename = f"{safe_product_name}_{timestamp}.png"
            screenshot_path = os.path.join(self.base_screenshot_dir, filename)
            product_element.screenshot(screenshot_path)
            return screenshot_path
        except Exception as e:
            print(f"            [ERROR] Ekran görüntüsü alma hatası: {str(e)}")
            return None

    def close(self):
        """
        Tarayıcıyı kapatır ve verileri kaydeder.
        """
        # Verileri kaydetme
        if self.all_products_data:
            filename = f"all_products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.all_products_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] Tüm ürünler kaydedildi: {filename}")
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    
    # Ana akış
    collector.go_to_ebay()
    collector.explore_main_categories(indices=[4, 6, 8])
    collector.close()
