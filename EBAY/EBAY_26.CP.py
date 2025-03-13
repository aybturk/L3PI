import json
import os
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless")  # İster headless çalıştırabilirsiniz
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # Ekran görüntüleri için temel klasör
        self.base_screenshot_dir = "product_screenshots"
        os.makedirs(self.base_screenshot_dir, exist_ok=True)

    def go_to_ebay(self):
        """
        eBay ana sayfasına gider.
        """
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
        
    def has_products(self):
        """
        Bu fonksiyon, sayfada '164,916 Results' vb. şekilde 'Results' kelimesi geçiyor mu diye bakar.
        - 4 farklı section içinde arar.
        - metin içinde 'results' geçiyorsa ürün var olarak kabul edilir.
        """
        # Bir miktar scroll yapalım ki sayfa tamamen yüklensin
        self.scroll_down_a_bit(amount=500)

        # CSS sınıfı varsa yakalayalım (bazı sayfalarda "textual-display brw-controls__count" şeklinde olabilir)
        # Artı olarak "Results" kelimesi geçen bir h2 de arıyoruz.
        for i in range(1, 6):  # section(1) ile section(5) arası
            possible_xpath = f"/html/body/div[2]/div[2]/section[{i}]"
            try:
                section_element = self.driver.find_element(By.XPATH, possible_xpath)
                text_content = section_element.text.lower()
                if "results" in text_content:
                    # Sayılar ve "results" ifadesi geçiyorsa ürün var diyoruz
                    return True
            except NoSuchElementException:
                pass
            except Exception:
                pass

        return False

    def explore_main_categories(self, start_index=3, end_index=12):
        """
        eBay ana sayfasında ana kategorileri (li[3..12]) dolaşır.
        """
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Bu sayfada (opsiyonel) main kategori butonları olabilir. Onları keşfet.
                self.explore_main_category_level()

                # Ana kategori sayfasındayız veya oradan yönlendik, alt kategorileri keşfet
                self.explore_sub_categories()

                # Ana kategoriye geri dön
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı.")
                break

    def explore_main_category_level(self, max_attempts=5):
        """
        Ana kategoriye tıkladıktan sonra sayfa içinde "Main kategori" olarak tanımlayabileceğimiz,
        alt kategorileri gizleyen buton vs. var mı kontrol eder.
        - /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[1] gibi XPATH’lerle
          alt kategori açabiliyorsa tıkla ve aynı sayfada kalıyorsa alt kategorileri gösterir.
        - Tıklama sonucu yeni sayfa yükleniyorsa, alt kategori sayfasına geçmişiz demektir (zaten explore_sub_categories'e gideceğiz).
        """
        for i in range(1, max_attempts+1):
            # Örnek XPATH: /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[1]
            main_cat_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                main_cat_elem = self.driver.find_element(By.XPATH, main_cat_xpath)
                text_main_cat = main_cat_elem.text.strip()
                print(f"  [INFO] Main kategori butonu/elemanı bulundu: {text_main_cat}")
                
                # Tıklayalım
                self.scroll_to_element(main_cat_elem)
                main_cat_elem.click()
                time.sleep(2)
                
                # Bu tıklama bizi yeni bir sayfaya yönlendirmiş olabilir.
                # Bunu anlamak için sayfada 'results' var mı bakabiliriz veya URL değişimi kontrol edilebilir.
                # Basit bir yaklaşım: has_products() kontrolü yapalım.
                if self.has_products():
                    # Eğer ürün varsa burası doğrudan alt kategori gibi davranıyordur, 
                    # o zaman scrape yapabiliriz. Fakat alt kategorilere de bir göz atalım.
                    print("  [INFO] Bu main kategori altında ürünler mevcut. Altkategoriler de olabilir.")
                    # Ürünleri alalım
                    self.scrape_products()

                    # Geri dönelim, bir sonraki main kategoriye geçelim
                    self.driver.back()
                    time.sleep(2)
                else:
                    # Ürün yoksa alt kategoriler açılmış olabilir, orada explore_sub_categories() metoduna gidiyoruz.
                    # Ama alt kategorilerin li XPATH’i (/html/body/...) değişebilir. 
                    # Zaten explore_sub_categories() metodunu en son ana sayfa/geri sayfa sonrasında çağırıyoruz.
                    # Burada isterseniz alt kategorilere direkt dalabilirsiniz. Fakat mantığı basit tutmak adına 
                    # şimdilik break deyip `explore_sub_categories()`'in normal akışa geri dönmesine izin veriyoruz.
                    print("  [INFO] Bu main kategoride ürün yok; alt kategorilere (explore_sub_categories) geçilecek.")
                    self.driver.back()
                    time.sleep(2)

            except NoSuchElementException:
                # Bu demek oluyor ki bu sayfada i. main kategori yok
                break
            except ElementClickInterceptedException:
                print("  [WARNING] Main kategoriye tıklanamadı.")
                break

    def explore_sub_categories(self, start_index=1, max_attempts=10):
        """
        Seçilen ana kategorinin (veya Main kategori sonrası) alt kategorilerini dolaşır.
        - Alt kategorilerle ilgili mantık: önce ürün var mı yok mu bak. Varsa ürün topla, yoksa mini kategoriye git.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategori tespit: {sub_cat_text}")
                self.scroll_to_element(sub_cat_element)
                sub_cat_element.click()
                time.sleep(2)
                
                # Ürün var mı diye bak
                if self.has_products():
                    print(f"    [INFO] '{sub_cat_text}' alt kategorisinde ürün var. Topluyoruz...")
                    self.scrape_products()
                    # Geri dön
                    self.driver.back()
                    time.sleep(2)
                else:
                    print(f"    [INFO] '{sub_cat_text}' alt kategorisinde ürün bulunamadı. Mini kategorilere bakılıyor...")
                    # Mini kategorileri explore et
                    self.explore_mini_categories()
                    # Geri dön
                    self.driver.back()
                    time.sleep(2)
                
                # Alt kategorilerde ilerlemeden önce "Load more" butonunu kontrol et
                self.scroll_down_a_bit()
                self.check_and_click_more_button()

            except NoSuchElementException:
                print("    [WARNING] Daha fazla alt kategori bulunamadı veya beklenen yapıda değil.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı.")
                break

    def explore_mini_categories(self, start_index=1, max_attempts=10):
        """
        Alt kategoride ürün yoksa mini kategorileri dolaş.
        - Örnek XPATH: /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/section/div/ul/li[1]
        - Yapı her sayfada farklı olabildiği için esnek olmak şart.
        """
        for i in range(start_index, start_index + max_attempts):
            # Deneme amaçlı farklı yerlerde mini kategori arayabiliriz.
            # Aşağıdaki XPATH, 'li/section/div/section/div/ul/li[i]' şeklinde bir yol deniyor.
            mini_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/section/div/ul/li[{i}]'
            try:
                mini_cat_elem = self.driver.find_element(By.XPATH, mini_xpath)
                mini_text = mini_cat_elem.text.strip()
                print(f"        [INFO] Mini kategori tespit: {mini_text}")
                self.scroll_to_element(mini_cat_elem)
                mini_cat_elem.click()
                time.sleep(2)
                
                # Burada ürün var mı?
                if self.has_products():
                    print(f"        [INFO] '{mini_text}' mini kategorisinde ürün var. Topluyoruz...")
                    self.scrape_products()
                else:
                    print(f"        [INFO] '{mini_text}' mini kategorisinde ürün bulunamadı.")
                
                # Geri dön
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                # Artık bu sayfada daha fazla mini kategori yok
                break
            except ElementClickInterceptedException:
                print("        [WARNING] Mini kategoriye tıklanamadı.")
                break

    def get_product_cards(self):
        """
        Sayfadaki ürün kartlarını döndürür.
        """
        return self.driver.find_elements(By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list")

    def scrape_products(self):
        """
        Sayfadaki ürünlerin metinsel bilgilerini ve ekran görüntülerini toplar.
        Screenshot isimlerini ürün başlığına göre kaydeder.
        """
        product_elements = self.get_product_cards()
        if not product_elements:
            print("    [INFO] Ürün kartı bulunamadı.")
            return
        
        products_data = []
        for idx, product in enumerate(product_elements, start=1):
            try:
                container = product.find_element(By.XPATH, "./div/div/div[2]")
                container_text = container.text.strip()
                
                # İsteğe bağlı bir filtre: "sold" ifadesini arıyorsanız kullanın. (Dilerseniz kaldırabilirsiniz.)
                # if "sold" not in container_text.lower():
                #     continue
                
                self.scroll_to_element(product)

                # Ürün ismini dosya adı olarak almak için:
                product_name = self.extract_product_name(container_text)
                
                screenshot_path = self.take_product_screenshot(product, product_name)
                
                products_data.append({
                    "product_name": product_name,
                    "full_text": container_text,
                    "screenshot_path": screenshot_path
                })
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")

        if products_data:
            filename = f"products_{int(time.time())}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(products_data, f, ensure_ascii=False, indent=2)
            print(f"    [INFO] {len(products_data)} ürün kaydedildi: {filename}")

        # (İsteğe bağlı) sayfayı biraz kaydırarak daha fazla ürün yüklenmesini tetikleme
        scroll_pause_time = 0.5
        screen_height = self.driver.execute_script("return window.innerHeight")
        scroll_amount = screen_height * 0.8
        for _ in range(5):
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(scroll_pause_time)

    def scroll_down_a_bit(self, amount=300):
        """
        Sayfayı biraz kaydırır.
        """
        self.driver.execute_script(f"window.scrollBy(0, {amount});")
        time.sleep(1)

    def scroll_to_element(self, element):
        """
        Verilen elementin ekrana kaydırılmasını sağlar.
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            element
        )
        time.sleep(1)

    def check_and_click_more_button(self):
        """
        /html/body/div[2]/div[2]/section[2]/section[1]/div/div/button
        adresine sahip butonu bulursa tıklar, yoksa geçer.
        """
        try:
            more_button_xpath = '/html/body/div[2]/div[2]/section[2]/section[1]/div/div/button'
            more_button = WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((By.XPATH, more_button_xpath))
            )
            
            button_text = more_button.text.strip().lower()
            
            if "more" in button_text and more_button.is_displayed() and more_button.is_enabled():
                print(f"    [INFO] 'Load More' butonu bulundu ({button_text}), tıklanıyor...")
                more_button.click()
                time.sleep(2)
            else:
                print(f"    [INFO] Buton tıklanabilir durumda değil veya 'More' içermiyor: {button_text}")
                
        except NoSuchElementException:
            pass
        except ElementClickInterceptedException:
            print("    [WARNING] 'Load More' butonuna tıklanamadı.")
        except Exception as e:
            # Örneğin TimeoutException
            pass

    def take_product_screenshot(self, product_element, product_name):
        """
        Bir web elementinin ekran görüntüsünü doğrudan element.screenshot() ile alır.
        Dosya adını ürün ismine göre oluşturur.
        """
        try:
            # Dosya adı olarak ürün ismini temizleyelim
            sanitized_name = re.sub(r'[\\/*?:"<>|]', '', product_name)  # Windows uyumlu kısıtlama
            if len(sanitized_name) == 0:
                sanitized_name = f"product_{int(time.time())}"
                
            unique_id = f"{sanitized_name}"
            product_dir = os.path.join(self.base_screenshot_dir, unique_id)
            os.makedirs(product_dir, exist_ok=True)
            
            screenshot_path = os.path.join(product_dir, f"{sanitized_name}.png")
            product_element.screenshot(screenshot_path)
            
            return screenshot_path
        except Exception as e:
            print(f"    [ERROR] Ekran görüntüsü alma hatası: {str(e)}")
            return None

    def extract_product_name(self, full_text):
        """
        Ürün metninin ilk satırı ya da belirli bir kısmı ürün adı olarak kullanılır.
        Dilerseniz bu mantığı değiştirebilirsiniz (regex vb. ile).
        """
        lines = full_text.split("\n")
        if lines:
            return lines[0][:80]  # Çok uzun isim olmasın diye 80 karakterle sınırlayabilirsiniz
        else:
            return f"product_{int(time.time())}"

    def close(self):
        """
        Tarayıcıyı kapatır.
        """
        self.driver.quit()

if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path=driver_path)
    
    # Ana akış
    collector.go_to_ebay()
    collector.explore_main_categories(start_index=3, end_index=12)
    collector.close()