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
    
    def explore_main_categories(self, start_index=3, end_index=12):
        """
        eBay sayfasındaki ana kategori listesinde, li[3] den li[11]'e kadar kategoriye tıklar.
        Bu numaralar senin paylaştığın xpath'lerle uyumlu olsun diye varsayım.
        end_index = 12, çünkü range fonksiyonunda üst sınır hariç tutulur.
        
        Her bir kategoriye tıkladıktan sonra alt kategorileri tarayacak bir alt fonksiyon çağrısı yapabiliriz.
        """
        for i in range(start_index, end_index):
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = self.driver.find_element(By.XPATH, xpath)
                category_text = category_element.text.strip()
                
                print(f"[INFO] Ana kategoriye tıklanıyor: {category_text}")
                category_element.click()
                time.sleep(2)
                
                # Ana kategoriye tıkladıktan sonra alt kategorileri gez
                self.explore_sub_categories()
                
                # Tıklanılan kategoriden geri dönmek için
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
         
        gibi xpath'leri kullanarak alt kategori linklerini tıklamayı deneriz.
        Bu örnekte basit bir for döngüsü ile deniyoruz.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Daha da derin bir kategori yapısı varsa, başka bir fonksiyonla devam edebiliriz
                self.explore_deeper_categories()
                
                # Kategori içindeki ürün sayısını bul
                product_count = self.get_category_product_count()
                print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
                
                # Geri dön ve diğer alt kategoriyi dene
                self.driver.back()
                time.sleep(2)
            except NoSuchElementException:
                # Bu alt kategori olmayabilir veya bitmiş olabilir
                # O yüzden for'u kırabiliriz veya devam edebiliriz; burada kırmak mantıklı olabilir
                print("    [WARNING] Daha fazla alt kategori bulunamadı.")
                break
            except ElementClickInterceptedException:
                print("    [WARNING] Alt kategoriye tıklanamadı. Engelleniyor olabilir.")
                break
    
    def explore_deeper_categories(self, start_index=3, max_attempts=50):
        """
        Bir alt kategoriye tıklandıktan sonra, tekrar benzer bir yapı varsa
        /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[3]
        gibi daha derin seviyedeki kategori öğelerini inceleyebilirsin.
        
        (Şimdilik bu fonksiyonu basit bıraktım. Kullandığın site yapısına göre düzenlemelisin.)
        """
        # Örnek: tekrar benzer bir döngü
        for i in range(start_index, start_index + max_attempts):
            deeper_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li/section/div/ul/li[{i}]'
            try:
                deeper_elem = self.driver.find_element(By.XPATH, deeper_xpath)
                deeper_text = deeper_elem.text.strip()
                
                print(f"        [INFO] Daha derin kategori bulundu: {deeper_text}")
                # Eğer bu aşamada da tıklamak istersen:
                # deeper_elem.click()
                # time.sleep(2)
                #
                # # Kategori içi ürün sayısı vb.
                # product_count = self.get_category_product_count()
                # print(f"        [INFO] Bu derin kategoride ürün sayısı: {product_count}")
                #
                # # Geri dön
                # self.driver.back()
                # time.sleep(2)
                
            except NoSuchElementException:
                # daha ileri kategori yok
                break
            except ElementClickInterceptedException:
                # tıklanamadı
                break
    
    def get_category_product_count(self):
        """
        /html/body/div[2]/div[2]/section[3]/section[3]/div[1]/div[2] xpath'inden,
        o kategorideki toplam ürün sayısını döndürür.
        """
        try:
            count_xpath = '/html/body/div[2]/div[2]/section[3]/section[3]/div[1]/div[2]'
            count_element = self.driver.find_element(By.XPATH, count_xpath)
            count_text = count_element.text.strip()
            
            return count_text
        except NoSuchElementException:
            return "0"  # veya None
    
    def close(self):
        """ Tarayıcıyı kapat. """
        self.driver.quit()


if __name__ == "__main__":
    # Kendi ChromeDriver yolunu yaz
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"

    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    
    # Ana kategorileri gez (li[3] ile li[11] arası)
    collector.explore_main_categories(start_index=3, end_index=12)
    
    # Tarayıcıyı kapat
    collector.close()
