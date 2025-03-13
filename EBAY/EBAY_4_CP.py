from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
import time

class ProductCollectorAI:
    def __init__(self, driver_path):
        """
        driver_path: ChromeDriver (veya Firefox için geckodriver) executable yolunu belirtir.
        """
        service = Service(driver_path)
        # Opsiyonel ayarlar
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")  # tarayıcıyı tam ekran aç
        # options.add_argument("--headless")  # eğer görünmez modda çalıştırmak istersen
        
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def go_to_ebay(self):
        """ eBay'in anasayfasına gider. """
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)  # sayfanın yüklenmesi için kısa bekleme
    
    def explore_main_categories(self, start_index=5, end_index=12):
        """
        eBay sayfasındaki ana kategori listesinde, li[3]'den li[11]'e kadar kategoriye tıklar.
        Her bir kategoriye tıkladıktan sonra alt kategorileri gezmek için ilgili fonksiyonları çağırır.
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
                
                # Tıklanılan kategoriden geri dön
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
        Ana kategoriye girdikten sonra:
         - /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[3]
         - /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[4]
         - vs...
         
        xpath'lerini kullanarak alt kategori linklerini tıklamayı dener.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Daha derin kategorileri gez
                self.explore_deeper_categories()
                
                # Kategori içindeki ürün sayısını bul
                product_count = self.get_category_product_count()
                print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
                
                # Geliştirme: Ürün sonuçlarını taramak için yeni fonksiyon çağrılıyor
                self.scrape_products()
                
                # Geri dön ve diğer alt kategoriyi dene
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
        Bir alt kategoriye tıklandıktan sonra, daha derin seviyedeki kategori öğelerini inceler.
        (Kendi site yapınıza göre düzenlemeniz gerekebilir.)
        """
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_text = deeper_elem.text.strip()
                
                print(f"        [INFO] Daha derin kategori bulundu: {deeper_text}")
                # Eğer derin kategoriyi de gezmek isterseniz buraya ekleyebilirsiniz.
                
            except NoSuchElementException:
                break
            except ElementClickInterceptedException:
                break
    
    def get_category_product_count(self):
        """
        Belirtilen xpath'ten, o kategorideki toplam ürün sayısını döndürür.
        """
        try:
            count_xpath = '/html/body/div[2]/div[2]/section[3]/section[3]/div[1]/div[2]'
            count_element = self.driver.find_element(By.XPATH, count_xpath)
            count_text = count_element.text.strip()
            
            return count_text
        except NoSuchElementException:
            return "0"
    
    def scrape_products(self, start_index=3, max_attempts=50):
        """
        Bu fonksiyon, sonuçlar listesindeki her bir ürünü tarar.
        İyileştirmeler:
          - Sonuçlar bölümüne geçmeden önce sayfayı aşağı kaydırır.
          - Her bir ürün için sayfanın görünür alanına getirmek amacıyla scrollIntoView ve window.scrollBy kullanılır.
          - Ürünün fiyatı ve (varsa) satış (sold) bilgisi çekilir.
          - Eğer ürünün satış adedi 50'den büyükse, ürünün fiyatı ve satış bilgisi ekrana yazdırılır.
        
        xpath detayları:
          - Ürün listesi için temel xpath:
              /html/body/div[2]/div[2]/section[3]/section[3]/ul/li[<i>]
          - Ürün fiyatı:
              /html/body/div[2]/div[2]/section[3]/section[6]/ul/li[<i>]/div/div/div[2]/div[2]/div[1]
          - Ürün satış bilgisi (varsa):
              /html/body/div[2]/div[2]/section[3]/section[6]/ul/li[<i>]/div/div/div[2]/div[2]/div[3]
        """
        # Sonuçlar bölümünün görünmesi için sayfayı biraz aşağı kaydır
        self.driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(2)
        
        for i in range(start_index, start_index + max_attempts):
            product_xpath = f'/html/body/div[2]/div[2]/section[3]/section[3]/ul/li[{i}]'
            try:
                product_element = self.driver.find_element(By.XPATH, product_xpath)
                # Ürünü görünür kılmak için scrollIntoView kullan
                self.driver.execute_script("arguments[0].scrollIntoView();", product_element)
                time.sleep(1)
                
                # Ürünün fiyatını çek
                price_xpath = f'/html/body/div[2]/div[2]/section[3]/section[6]/ul/li[{i}]/div/div/div[2]/div[2]/div[1]'
                price_text = self.driver.find_element(By.XPATH, price_xpath).text.strip()
                
                sold_number = 0
                try:
                    # Ürün satış bilgisi (örneğin "178 sold") çekiliyor
                    sold_xpath = f'/html/body/div[2]/div[2]/section[3]/section[6]/ul/li[{i}]/div/div/div[2]/div[2]/div[3]'
                    sold_text = self.driver.find_element(By.XPATH, sold_xpath).text.strip()
                    # Metin "178 sold" gibi ise ilk kelime sayıya dönüştürülüyor
                    sold_number = int(sold_text.split()[0])
                except NoSuchElementException:
                    # Satış bilgisi yoksa sold_number 0 olarak kalır
                    pass
                
                if sold_number > 50:
                    print(f"Ürün {i}: Fiyat = {price_text}, Sold = {sold_number}")
                
                # Her ürün işleminden sonra sayfayı biraz daha aşağı kaydır (lazy load etkileri için)
                self.driver.execute_script("window.scrollBy(0, 200);")
                time.sleep(1)
            except NoSuchElementException:
                print(f"Ürün elemanı bulunamadı: li[{i}]. Tarama sonlandırılıyor.")
                break
    
    def close(self):
        """ Tarayıcıyı kapatır. """
        self.driver.quit()


if __name__ == "__main__":
    # Kendi ChromeDriver yolunuzu belirtin
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"

    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    
    # Ana kategorileri gez (li[3] ile li[11] arası)
    collector.explore_main_categories(start_index=3, end_index=12)
    
    # Tarayıcıyı kapat
    collector.close()
