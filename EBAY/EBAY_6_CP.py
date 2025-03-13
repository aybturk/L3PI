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
        """eBay'in anasayfasına gider."""
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)
    
    def explore_main_categories(self, start_index=3, end_index=12):
        """
        eBay sayfasındaki ana kategori listesinde, li[start_index] ile li[end_index-1]'e kadar kategoriye tıklar.
        Her kategoriye tıkladıktan sonra alt kategorileri ve ilgili ürün sayısını inceler.
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
        Seçilen ana kategori altındaki alt kategorileri sırasıyla tıklar.
        Alt kategoriye tıkladıktan sonra:
          - Daha derin kategori varsa incelemeye çalışır.
          - Kategori içerisindeki ürün sayısını alır.
          - O sayfadaki ürünleri tarayarak, fiyat ve satış (sold) bilgilerini toplar.
        """
        for i in range(start_index, start_index + max_attempts):
            sub_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{i}]'
            try:
                sub_cat_element = self.driver.find_element(By.XPATH, sub_xpath)
                sub_cat_text = sub_cat_element.text.strip()
                
                print(f"    [INFO] Alt kategoriye tıklanıyor: {sub_cat_text}")
                sub_cat_element.click()
                time.sleep(2)
                
                # Daha derin kategorileri kontrol et
                self.explore_deeper_categories()
                
                # Kategori içindeki ürün sayısını al (elementin görünmesi için 2 saniye bekle)
                product_count = self.get_category_product_count()
                print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
                
                # Ürünleri tara (sayfadaki tüm ürünler için)
                self.scrape_products()
                
                # Geri dön
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
        Alt kategoriye tıkladıktan sonra varsa daha derin seviyedeki kategori öğelerini inceler.
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
        Kategori sayfasındaki ürün sayısını belirten elementin metnini döndürür.
        Görünürlüğü sağlamak için ek 2 saniye beklenir.
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
        Kategori sayfasındaki tüm ürünleri tarar.
          - Önce sayfanın en altına scroll yapılarak ürünlerin yüklenmesi sağlanır.
          - Sonrasında ürün elementleri toplanır.
          - Ürün listesinde ilk iki eleman atlanır, çünkü ilgilendiğimiz ürün bilgileri 3. elemandan itibaren yer almaktadır.
          - Her bir ürün için element scrollIntoView ile görünür yapılır ve 2 saniye beklenir.
          - Ürün içerisinden, relative XPath kullanılarak fiyat bilgisi alınır.
          - Aynı şekilde, "sold" bilgisi aranır; bulunursa metin (örn. "65 sold") ekrana yazdırılır.
          - Eğer satış adedi (sold) varsa, sayı parse edilip 50’den büyükse, ürünün fiyatı ve satış bilgisi çıktı olarak verilir.
          - Tarama tamamlandığında sayfa en üste scroll edilir.
        """
        # Sayfanın en altına giderek tüm ürünlerin yüklenmesini sağla
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Ürün elementlerini topla
        product_elements = self.driver.find_elements(By.XPATH, '/html/body/div[2]/div[2]/section[3]/section[3]/ul/li')
        print(f"    [INFO] Toplam ürün sayısı: {len(product_elements)}")
        
        # Ürün listesinde, ilk iki elemanı atlayarak (örneğin header veya reklam olabilir) 3. elemandan itibaren tarama yap
        for idx, product in enumerate(product_elements, start=1):
            if idx < 3:
                continue  # 1 ve 2 numaralı elemanlar atlanıyor
            
            try:
                # Ürünü görünür yapmak için scrollIntoView kullan
                self.driver.execute_script("arguments[0].scrollIntoView();", product)
                time.sleep(2)
                
                # Fiyat bilgisini al (ilgili alt element; relative XPath kullanılıyor)
                try:
                    price_element = product.find_element(By.XPATH, ".//div/div/div[2]/div[2]/div[1]")
                    price_text = price_element.text.strip()
                except NoSuchElementException:
                    price_text = "Fiyat bulunamadı"
                
                # Satış (sold) bilgisini al; burada 3 numaralı değere bakıyoruz
                try:
                    sold_element = product.find_element(By.XPATH, ".//div/div/div[2]/div[2]/div[3]")
                    sold_text = sold_element.text.strip()  # Örn: "65 sold"
                except NoSuchElementException:
                    sold_text = None
                
                if sold_text:
                    # İstenirse sayıya çevirip 50'den büyükse çıktı verelim
                    try:
                        sold_number = int(sold_text.split()[0].replace(',', ''))
                    except Exception:
                        sold_number = 0
                    if sold_number > 50:
                        print(f"    Ürün {idx}: Fiyat = {price_text}, Sold = {sold_text}")
                    # Veya direkt metni çıktı olarak verebilirsiniz:
                    # print(f"    Ürün {idx}: Sold = {sold_text}")
            except Exception as e:
                print(f"    [WARNING] Ürün {idx} işlenirken hata: {str(e)}")
                continue
        
        # Taranan sayfanın sonunda, sayfa en üste scroll edilir
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
    
    # Ana kategorileri gez (örneğin li[3]'ten li[11]'e kadar)
    collector.explore_main_categories(start_index=3, end_index=12)
    
    collector.close()
