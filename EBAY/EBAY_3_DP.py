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
        self.scroll_pause_time = 1  # Kaydırma arası bekleme süresi
    
    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)

    # ... Diğer mevcut metodlar aynı kalacak ...

    def get_category_product_count(self):
        """Sayfayı biraz kaydırarak ürün sayısını bulma"""
        try:
            # Sayfayı 500 piksel aşağı kaydır
            self.driver.execute_script("window.scrollBy(0,500);")
            time.sleep(1)
            
            count_xpath = '/html/body/div[2]/div[2]/section[3]/section[3]/div[1]/div[2]'
            count_element = self.driver.find_element(By.XPATH, count_xpath)
            return count_element.text.strip()
        except NoSuchElementException:
            return "0"

    def collect_product_details(self):
        """Ürün detaylarını topla ve filtrele"""
        print("        [INFO] Ürün detayları toplanıyor...")
        
        # Sayfayı ürünlerin yüklenmesi için kaydır
        self._scroll_page()
        
        # Ürün konteynırını bul
        products_xpath = '/html/body/div[2]/div[2]/section[3]/section[3]/ul/li'
        products = self.driver.find_elements(By.XPATH, products_xpath)
        
        for product in products:
            try:
                # Ürün fiyatını al
                price = product.find_element(
                    By.XPATH, './/div/div/div[2]/div[2]/div[1]'
                ).text.strip()
                
                # Satış bilgisini kontrol et
                try:
                    sales_element = product.find_element(
                        By.XPATH, './/div/div/div[2]/div[2]/div[3]'
                    )
                    sales_text = sales_element.text.strip()
                    sales_count = int(sales_text.split()[0])
                except (NoSuchElementException, IndexError):
                    sales_count = 0

                # Filtreleme ve yazdırma
                if sales_count > 50:
                    print(f"            [HOT PRODUCT] Fiyat: {price} | Satış: {sales_count}+")
                    
            except Exception as e:
                print(f"            [WARNING] Ürün okunamadı: {str(e)}")
                continue

    def _scroll_page(self, scroll_amount=1000):
        """Sayfayı kaydırma yardımcı fonksiyonu"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Belirtilen miktarda kaydır
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(self.scroll_pause_time)
            
            # Yeni sayfa yüksekliğini kontrol et
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def explore_sub_categories(self, start_index=3, max_attempts=50):
        for i in range(start_index, start_index + max_attempts):
            # ... Mevcut kodun aynısı ...
            
            # Ürün sayısını aldıktan sonra detayları topla
            product_count = self.get_category_product_count()
            print(f"    [INFO] Bu alt kategoride ürün sayısı: {product_count}")
            
            # Yeni eklenen ürün detay toplama
            self.collect_product_details()
            
            # Geri dön ve devam et
            self.driver.back()
            time.sleep(2)

# ... Diğer kodlar aynı kalacak ...

if __name__ == "__main__":
    # Kendi ChromeDriver yolunu yaz
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"

    collector = ProductCollectorAI(driver_path=driver_path)
    collector.go_to_ebay()
    
    # Ana kategorileri gez (li[3] ile li[11] arası)
    collector.explore_main_categories(start_index=3, end_index=12)
    
    # Tarayıcıyı kapat
    collector.close()