import json
import os
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
        
        self.base_dir = "ebay_data"
        os.makedirs(self.base_dir, exist_ok=True)
    
    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self):
        """Sadece belirli ana kategorileri işler (li[3] ile li[11] arası)"""
        main_categories = list(range(4, 12))  # li[3] - li[11]
        for i in main_categories:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_name = category_element.text.strip().replace("/", "-")
                print(f"\n[ANA KATEGORI] {category_name}")
                category_element.click()
                time.sleep(2)
                
                # Alt kategori işlemleri için kök klasör oluştur
                category_dir = os.path.join(self.base_dir, category_name)
                os.makedirs(category_dir, exist_ok=True)
                
                # Alt kategori işlemleri
                self.process_category_level(category_path=[category_name])
                
                self.driver.back()
                time.sleep(2)
                
            except Exception as e:
                print(f"Ana kategori hatası: {str(e)}")
                continue
    
    def process_category_level(self, category_path, section_type=None):
        """
        Rekürsif kategori işleme fonksiyonu
        section_type: closed (section2) veya open (section1)
        """
        try:
            # Önce kapalı kategorileri kontrol et (section2)
            if not section_type or section_type == "closed":
                self.check_and_process_section(
                    category_path=category_path,
                    section_num=2,
                    section_type="closed"
                )
            
            # Sonra açık kategorileri kontrol et (section1)
            if not section_type or section_type == "open":
                self.check_and_process_section(
                    category_path=category_path,
                    section_num=1,
                    section_type="open"
                )
                
        except Exception as e:
            print(f"Kategori işleme hatası: {str(e)}")
    
    def check_and_process_section(self, category_path, section_num, section_type):
        """Belirli bir section'daki kategorileri işler"""
        section_xpath = f'/html/body/div[2]/div[2]/section[2]/section[{section_num}]/div/ul'
        try:
            section = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, section_xpath))
            )
            
            categories = section.find_elements(By.TAG_NAME, "li")
            print(f"  Bulunan {section_type} kategoriler: {len(categories)}")
            
            for idx, cat in enumerate(categories, 1):
                try:
                    cat_name = cat.text.strip().replace("/", "-")
                    if not cat_name: continue
                    
                    print(f"\n  [{section_type.upper()} KATEGORI] {cat_name}")
                    
                    # Klasör yapısını oluştur
                    current_path = category_path + [cat_name]
                    dir_path = os.path.join(self.base_dir, *current_path)
                    os.makedirs(dir_path, exist_ok=True)
                    
                    # Kategoriye tıkla ve işle
                    cat.click()
                    time.sleep(1.5)
                    
                    # Ürün kontrolü yap
                    product_count = self.get_product_count()
                    
                    if product_count > 0:
                        print(f"  !! Ürün bulundu ({product_count} adet), veri toplanıyor...")
                        self.scrape_products(current_path)
                        self.driver.back()
                        time.sleep(1.5)
                    else:
                        # Derin kategorileri kontrol et
                        print("  Ürün bulunamadı, derin kategoriler aranıyor...")
                        self.process_category_level(
                            category_path=current_path,
                            section_type="closed"  # Önce kapalıları kontrol et
                        )
                        self.driver.back()
                        time.sleep(1.5)
                        
                except Exception as e:
                    print(f"  Alt kategori işleme hatası: {str(e)}")
                    continue
                    
        except Exception:
            print(f"  {section_type} section bulunamadı")
    
    def get_product_count(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"))
        except Exception:
            return 0
    
    def scrape_products(self, category_path):
        products = self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")
        products_data = []
        
        for idx, product in enumerate(products, 1):
            try:
                self.scroll_to_element(product)
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                text = container.text.strip()
                
                if "sold" not in text.lower():
                    continue
                
                # Ekran görüntüsü yolu
                screenshot_dir = os.path.join(self.base_dir, *category_path, f"urun_{idx}")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, "screenshot.png")
                product.screenshot(screenshot_path)
                
                products_data.append({
                    "text": text,
                    "screenshot": screenshot_path
                })
                
            except Exception as e:
                print(f"  Ürün kaydetme hatası: {str(e)}")
        
        if products_data:
            json_path = os.path.join(self.base_dir, *category_path, "products.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(products_data, f, indent=2, ensure_ascii=False)
            print(f"  {len(products_data)} ürün kaydedildi")
            
        # Load More butonu kontrolü
        self.check_and_click_more_button()
    
    def check_and_click_more_button(self):
        try:
            button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(translate(., "LESS", "less"), "more")]'))
            )
            if "more" in button.text.lower():
                button.click()
                print("  Load More tıklandı")
                time.sleep(1.5)
                self.scrape_products()  # Yeni yüklenen ürünleri işle
        except Exception:
            pass
    
    def scroll_to_element(self, element):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(0.5)
    
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