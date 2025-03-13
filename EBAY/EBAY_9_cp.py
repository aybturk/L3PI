from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
import time
import re

class ProductCollectorAI:
    def __init__(self, driver_path):
        """
        driver_path: ChromeDriver (veya Firefox için geckodriver) executable yolunu belirtir.
        """
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def go_to_ebay(self):
        """eBay'in anasayfasına gider."""
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=3, end_index=12):
        """
        Ana kategorilerde dolaşır; her kategoriye tıkladığında alt kategorileri gezip,
        ürün sayısı ve ürünlerin detaylarını (fiyat, sold bilgisi) inceler.
        """
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Alt kategorileri gez
                self.explore_sub_categories()
                
                # Geri dön
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print(f"[WARNING] Kategori (li[{i}]) bulunamadı. Muhtemelen daha fazla kategori yok.")
                break
            except ElementClickInterceptedException:
                print(f"[WARNING] Kategoriye (li[{i}]) tıklanamadı. Muhtemelen görünmüyor veya engelleniyor.")
                break
    
    def explore_sub_categories(self, start_index=3, max_attempts=50):
        """
        Ana kategori altında yer alan alt kategorileri dolaşır.
        Her alt kategoriye tıkladıktan sonra:
          - Varsa daha derin kategoriler kontrol edilir.
          - Ürün sayısı elde edilir.
          - Ürünler yavaşça aşağı scroll edilip incelenir.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Daha derin kategorileri varsa kontrol et
                self.explore_deeper_categories()
                
                # Ürün sayısını al (elementin görünmesi için ek 2 saniye bekleyelim)
                product_count = self.get_category_product_count()
                print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
                
                # Ürün sayısı sıfır değilse, yavaş scroll ile ürünleri yüklemeyi dene
                self.scrape_products()
                
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                print("    [WARNING] Daha fazla alt kategori bulunamadı.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı. Engelleniyor olabilir.")
                break
    
    def explore_deeper_categories(self, start_index=3, max_attempts=50):
        """
        Alt kategoriye tıklandıktan sonra, varsa daha derin kategori öğelerini inceler.
        """
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_text = deeper_elem.text.strip()
                print(f"        [INFO] Daha derin kategori bulundu: {deeper_text}")
            except NoSuchElementException:
                break
            except ElementClickInterceptedException:
                break
    
    def get_category_product_count(self):
        """
        Kategori sayfasındaki ürün sayısını belirten elementi bulup metnini döndürür.
        (Elementin görünür olması için ek 2 saniye beklenir.)
        """
        time.sleep(2)
        try:
            count_xpath = '/html/body/div[2]/div[2]/section[3]/section[3]/div[1]/div[2]'
            count_element = self.driver.find_element(By.XPATH, count_xpath)
            count_text = count_element.text.strip()
            return count_text
        except NoSuchElementException:
            return "0"
    
    def scrape_products(self):
        """
        Eğer alt kategori için ürün sayısı 0 değilse, sayfanın yavaşça aşağı scroll edilerek ürünlerin yüklenmesi beklenir.
        Daha sonra, bulunan ürün elemanları üzerinden tek tek geçilerek her ürün için
          - Fiyat bilgisi,
          - Satış (sold) bilgisi (önce div[3] kontrol edilip "Free shipping" varsa div[4]'teki bilgi kullanılır)
        alınır.
        
        Eğer ürün elemanı bulunamazsa scroll yapmaya gerek yoktur.
        """
        # İlk olarak, kategori ürün sayısından 0 olmadığını doğrulayalım:
        product_count_str = self.get_category_product_count()
        count = 0
        digits = re.findall(r'[\d,]+', product_count_str)
        if digits:
            try:
                count = int(digits[0].replace(',', ''))
            except Exception:
                count = 0
        
        if count == 0:
            print("    [INFO] Ürün sayısı 0, dolayısıyla scroll yapılmayacak.")
            return
        else:
            print("    [INFO] Ürün sayısı mevcut, slow scroll ile ürünler yükleniyor...")
        
        # Belirli bir süre (örneğin 30 saniye) boyunca yavaş scroll ederek ürünlerin yüklenmesini bekleyelim.
        timeout = 30
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.driver.execute_script("window.scrollBy(0, 200);")
            time.sleep(1)
            product_elements = self.driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/section[3]/section[3]/ul/li')
            if len(product_elements) > 0:
                break  # Ürün elemanları yüklenmeye başladı
        
        # Son durumda, ürün elemanlarını tekrar alalım
        product_elements = self.driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/section[3]/section[3]/ul/li')
        if len(product_elements) == 0:
            print("    [INFO] Ürün bulunamadı, scroll sonrası da ürün elemanı tespit edilemedi.")
            return
        
        print(f"    [INFO] Toplam ürün elemanı sayısı: {len(product_elements)}")
        
        # Bulunan ürün elemanlarını tek tek inceleyelim.
        for idx, product in enumerate(product_elements, start=1):
            # Eğer gerekliyse ilk birkaç eleman header/reklam olabilir; isteğe bağlı atlayabilirsiniz.
            if idx < 3:
                continue
            try:
                self.driver.execute_script("arguments[0].scrollIntoView();", product)
                time.sleep(2)
                
                # Fiyat bilgisini çekelim (relative XPath)
                try:
                    price_element = product.find_element(By.XPATH, ".//div/div/div[2]/div[2]/div[1]")
                    price_text = price_element.text.strip()
                except NoSuchElementException:
                    price_text = "Fiyat bulunamadı"
                
                # Satış (sold) bilgisini çekmeye çalışalım; önce div[3]'ü deneyelim.
                sold_text = None
                try:
                    sold_element = product.find_element(By.XPATH, ".//div/div/div[2]/div[2]/div[3]")
                    sold_text = sold_element.text.strip()
                    # Eğer "Free shipping" ifadesi varsa, div[4]'teki değeri kontrol edelim.
                    if "Free shipping" in sold_text:
                        try:
                            sold_element2 = product.find_element(By.XPATH, ".//div/div/div[2]/div[2]/div[4]")
                            sold_text = sold_element2.text.strip()
                        except NoSuchElementException:
                            sold_text = None
                except NoSuchElementException:
                    sold_text = None
                
                # Çıktı vereceğiz
                if sold_text:
                    try:
                        sold_number = int(sold_text.split()[0].replace(',', ''))
                    except Exception:
                        sold_number = 0
                    if sold_number > 50:
                        print(f"    Ürün {idx}: Fiyat = {price_text}, Sold = {sold_text}")
                    else:
                        print(f"    Ürün {idx}: Sold = {sold_text}, Fiyat = {price_text}")
                else:
                    print(f"    Ürün {idx}: Sold bilgisi yok, Fiyat = {price_text}")
            
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
                continue
        
        # İşlem bitiminde sayfayı yavaşça en üste scroll edelim.
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
    
    def close(self):
        """Tarayıcıyı kapatır."""
        self.driver.quit()


if __name__ == "__main__":
    # Kendi ChromeDriver yolunuzu belirtin
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    
    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    
    # Örneğin, li[3]'ten li[11]'e kadar ana kategorileri gez
    collector.explore_main_categories(start_index=3, end_index=12)
    
    collector.close()
