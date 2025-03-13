import os
import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    TimeoutException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def sanitize_filename(name):
    """Dosya/screenshot ismi olarak kullanılacak metni temizler."""
    # Örnek basit temizlik: Alfanumerik karakterler ve bazı semboller dışındakileri "-" ile değiştirir
    return re.sub(r'[^\w\s\-_]', '', name).strip().replace(' ', '_')


class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        # Görsel işlemler için headless olmaması önerilir, ancak dilerseniz açabilirsiniz.
        # options.add_argument("--headless")
        options.add_argument("--start-maximized")
        
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Kayıtların tutulacağı ana klasör
        self.base_dir = "ebay_data"
        os.makedirs(self.base_dir, exist_ok=True)
    
    def go_to_ebay(self):
        """eBay ana sayfasına gider."""
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=3, end_index=12):
        """
        Ana sayfadaki ana kategorilere tıklar.
        - Örnek olarak li[3]..li[11] arası, siz ihtiyaca göre değiştirebilirsiniz.
        """
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_name = category_element.text.strip().replace("/", "-")
                if not category_name:
                    continue

                print(f"\n[ANA KATEGORI] {category_name}")
                category_element.click()
                time.sleep(2)
                
                # Klasör oluştur
                category_path = [category_name]
                category_dir = os.path.join(self.base_dir, category_name)
                os.makedirs(category_dir, exist_ok=True)
                
                # Bu ana kategori içerisindeki tüm alt kategorileri ve/veya ürünleri incele
                self.explore_category_sections(category_path)
                
                # Ana kategoriye geri dön
                self.driver.back()
                time.sleep(2)
            
            except (NoSuchElementException, ElementClickInterceptedException) as e:
                print(f"[WARNING] Ana kategori {i}. sırada işlenemedi: {str(e)}")
                continue
            except Exception as e:
                print(f"[ERROR] Ana kategori {i}. sırada beklenmeyen hata: {str(e)}")
                continue

    def explore_category_sections(self, category_path):
        """
        /html/body/div[2]/div[2]/section[2]/section[1] ve [2] içinde yer alan
        alt kategorilerde gezinir ve ürünleri arar.
        """
        # section[1] ve section[2] için işlem yapmaya çalışıyoruz
        for section_num in [1, 2]:
            section_xpath = f'/html/body/div[2]/div[2]/section[2]/section[{section_num}]/div/ul'
            try:
                section_element = WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, section_xpath))
                )
            except TimeoutException:
                # O section yoksa sorun etme, diğerini dene
                continue
            
            # Bu section içindeki tüm li'ları bulalım
            li_elements = section_element.find_elements(By.XPATH, "./li")
            if not li_elements:
                continue
            
            print(f"  [INFO] section[{section_num}] içinde {len(li_elements)} alt kategori bulundu.")
            
            for idx, li_el in enumerate(li_elements, start=1):
                try:
                    cat_text = li_el.text.strip().replace("/", "-")
                    if not cat_text:
                        continue

                    print(f"    -> Alt Kategori: {cat_text}")
                    
                    # Tıklamadan önce elemente kaydırıyoruz ( görünür olması için )
                    self.scroll_to_element(li_el)
                    time.sleep(1)
                    
                    # Tıklama
                    li_el.click()
                    time.sleep(2)
                    
                    new_path = category_path + [cat_text]
                    # Ürün var mı yok mu kontrol et
                    product_count = self.get_product_count()
                    if product_count > 0:
                        # Ürünleri çek
                        print(f"    [INFO] {product_count} ürün bulundu. Veri toplanıyor...")
                        self.scrape_products(new_path)
                        
                        # Geri dön
                        self.driver.back()
                        time.sleep(2)
                        
                    else:
                        print(f"    [INFO] Ürün bulunamadı, alt/derin kategoriler aranacak.")
                        # Alt kategorilerin altındaki final kategorilere veya daha derin kategorilere bak
                        self.explore_deeper_categories(new_path)
                        
                        # Ardından geri dön
                        self.driver.back()
                        time.sleep(2)
                
                except (NoSuchElementException, ElementClickInterceptedException) as e:
                    print(f"    [WARNING] Alt kategoriye tıklanamadı: {str(e)}")
                    continue
                except Exception as e:
                    print(f"    [ERROR] Alt kategori işlenirken hata: {str(e)}")
                    continue

    def explore_deeper_categories(self, category_path):
        """
        Daha derin kategoriler için:
        /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[1]/section/div/section/div/ul/li[1]
        benzeri yapılara gidip varsa tıklar ve ürün arar.
        
        Ek olarak /html/body/div[2]/div[2]/section[2]/section/div/ul/li/section/div/ul/li[*] gibi final butonları da kapsar.
        """
        # Farklı derinlikteki xpath'leri deneyeceğiz.
        # 1) /html/body/div[2]/div[2]/section[2]/section[1 or 2]/div/ul/li[*]/section/div/section/div/ul/li[*]
        # 2) /html/body/div[2]/div[2]/section[2]/section/div/ul/li/section/div/ul/li[*]
        # ... gibi varyantları.
        
        # Denenecek XPath listesi (ihtiyaca göre genişletilebilir).
        xpaths_to_try = [
            '/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/section/div/ul/li',
            '/html/body/div[2]/div[2]/section[2]/section[2]/div/ul/li/section/div/section/div/ul/li',
            '/html/body/div[2]/div[2]/section[2]/section/div/ul/li/section/div/ul/li'
        ]
        
        for base_xpath in xpaths_to_try:
            try:
                deeper_elements = self.driver.find_elements(By.XPATH, base_xpath)
                if not deeper_elements:
                    continue
                
                print(f"      [INFO] {base_xpath} altında {len(deeper_elements)} alt kategori butonu bulundu.")
                
                for idx, de in enumerate(deeper_elements, start=1):
                    try:
                        deep_text = de.text.strip().replace("/", "-")
                        if not deep_text:
                            continue
                        
                        print(f"        -> Derin Alt Kategori: {deep_text}")
                        self.scroll_to_element(de)
                        time.sleep(1)
                        
                        de.click()
                        time.sleep(2)
                        
                        new_path = category_path + [deep_text]
                        product_count = self.get_product_count()
                        if product_count > 0:
                            print(f"        [INFO] {product_count} ürün bulundu. Veri toplanıyor...")
                            self.scrape_products(new_path)
                            self.driver.back()
                            time.sleep(2)
                        else:
                            print(f"        [INFO] Ürün bulunamadı. Daha derin arama gerekebilir.")
                            # Kendi içinde tekrar explore_deeper_categories yapılabilir
                            self.explore_deeper_categories(new_path)
                            self.driver.back()
                            time.sleep(2)
                    
                    except Exception as e:
                        print(f"        [WARNING] Derin alt kategori işlenemedi: {str(e)}")
                        continue
            
            except Exception as e:
                # Bu xpath yapısı yok veya hata oluştu, bir sonrakini dene.
                continue

    def get_product_count(self):
        """ 
        Sayfada bulunan ürün adetini döndürür. 
        Hem 'list' hem de 'gallery' tipindeki kartları kapsayacak şekilde arıyoruz.
        """
        try:
            products = self.driver.find_elements(By.CSS_SELECTOR, "li[class*='brwrvr__item-card']")
            return len(products)
        except Exception:
            return 0
    
    def scrape_products(self, category_path):
        """
        Mevcut sayfadaki ürünleri tarar ve kaydeder.
        - 'sold' ifadesi filtresini halen kullanıyor, isterseniz kaldırabilirsiniz.
        - Screenshot isimlerini ürün ismine göre oluşturur.
        - 'Load More' butonu var ise tıklayıp devam eder (tekrarlı şekilde).
        """
        # Kategori klasörünü oluşturalım
        dir_path = os.path.join(self.base_dir, *category_path)
        os.makedirs(dir_path, exist_ok=True)
        
        all_products_data = []
        
        while True:
            # Ürünleri topla
            product_elements = self.driver.find_elements(By.CSS_SELECTOR, "li[class*='brwrvr__item-card']")
            
            # Her bir ürünün verisini alma
            page_products_data = self._extract_product_data(product_elements, dir_path)
            all_products_data.extend(page_products_data)
            
            # "Load More" butonu var mı kontrol edelim
            if not self.check_and_click_more_button():
                break
            
            # "Load More" tıklandıysa biraz bekleyip tekrar ürünleri toplayacağız
            time.sleep(2)
        
        # JSON kaydı
        if all_products_data:
            json_path = os.path.join(dir_path, "products.json")
            # Mevcut products.json varsa eski veriyi okuyup yenisi ile birleştirebilirsiniz
            # Şimdilik basitçe overwrite ediyoruz.
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(all_products_data, f, indent=2, ensure_ascii=False)
            print(f"    [INFO] Toplam {len(all_products_data)} ürün kaydedildi -> {json_path}")

    def _extract_product_data(self, product_elements, dir_path):
        """Ürünlerin metnini okur, screenshot alır ve dict olarak döndürür."""
        products_data = []
        
        for product_el in product_elements:
            try:
                self.scroll_to_element(product_el)
                container = product_el.find_element(By.XPATH, ".//div/div/div[2]")
                container_text = container.text.strip()
                
                # Örnek filtre (sold yazmıyorsa atla) - İsterseniz kaldırın
                if "sold" not in container_text.lower():
                    continue
                
                # Ürün adı ilk satır olabilir (ya da daha iyi bir locatordan yakalayabilirsiniz)
                product_name = container_text.split("\n")[0]
                safe_name = sanitize_filename(product_name)[:70]  # 70 karakteri geçmesin
                
                screenshot_filename = f"{safe_name}.png"
                screenshot_path = os.path.join(dir_path, screenshot_filename)
                
                product_el.screenshot(screenshot_path)
                
                products_data.append({
                    "name": product_name,
                    "full_text": container_text,
                    "screenshot_path": screenshot_path
                })
            except Exception as e:
                print(f"      [WARNING] Ürün işlenirken hata: {str(e)}")
                continue
        
        return products_data
    
    def check_and_click_more_button(self):
        """
        "Load More" veya benzer metinli buton varsa tıklar, yoksa False döner.
        XPATH: //button[contains(translate(., 'MORE', 'more'), 'more')]
        """
        try:
            button = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(translate(., 'MORE', 'more'), 'more')]")
                )
            )
            if button.is_displayed():
                button_text = button.text.strip().lower()
                if "more" in button_text:
                    print("    [INFO] 'Load More' butonu tıklandı, ek ürünler yükleniyor...")
                    button.click()
                    return True
            return False
        
        except TimeoutException:
            return False
        except Exception as e:
            print(f"    [WARNING] 'Load More' butonuna tıklanırken hata: {str(e)}")
            return False
    
    def scroll_to_element(self, element):
        """Verilen elementin ekranda görünür hale gelmesi için kaydırma."""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        except Exception:
            pass
    
    def close(self):
        """Tarayıcıyı kapatır."""
        self.driver.quit()


if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path)
    
    try:
        collector.go_to_ebay()
        collector.explore_main_categories(start_index=3, end_index=12)
    finally:
        collector.close()