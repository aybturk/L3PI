import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class Trendyol_Category_Search:
    def __init__(self, driver_path, base_url="https://www.trendyol.com/butik/liste/2/erkek"):
        # Chrome seçenekleri: bildirimleri kapatıyoruz
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-notifications")
        service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.action = ActionChains(self.driver)
        self.driver.get(base_url)
        time.sleep(2)  # Sayfanın tam yüklenmesi için bekleme
        self.dismiss_cookies()

    def dismiss_cookies(self):
        """
        Sayfa yüklendikten sonra çıkan çerez popup’ını kapatır.
        """
        try:
            cookie_xpath = "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div/button[3]"
            cookie_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, cookie_xpath)))
            cookie_btn.click()
            time.sleep(1)
        except Exception as e:
            logging.info("Çerez popup'ı bulunamadı veya zaten kapalı: %s", e)

    def open_categories_menu(self):
        """
        'Tüm Kategoriler' butonuna tıklayarak kategori menüsünü açar.
        """
        tum_kategoriler_xpath = "/html/body/div[1]/div[2]/div/div/div[1]/nav/div/div/div/div"
        menu_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, tum_kategoriler_xpath)))
        menu_element.click()
        time.sleep(1)  # Menü açılma animasyonu için bekleme
        main_category_container_xpath = "//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]"
        self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_container_xpath)))

    def get_main_categories(self):
        """
        Ana kategorilerin isimlerini ve XPath'lerini liste olarak döndürür.
        Örnek çıktı:
           [{"name": "Kadın", "xpath": "…"}, {"name": "Erkek", "xpath": "…"}, ...]
        """
        main_categories = []
        for i in range(1, 11):
            xpath = f"//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]/div[{i}]"
            try:
                element = self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
                category_name = element.text.strip()
                if category_name:
                    main_categories.append({"name": category_name, "xpath": xpath})
            except Exception as e:
                logging.info("Ana kategori bulunamadı, index %d: %s", i, e)
                break
        return main_categories

    def get_alt_categories(self, main_category_index):
        """
        Seçilen ana kategori üzerinde hover yapıldığında açılan alt kategori bloklarını döndürür.
        Her alt kategori için isim ve XPath bilgisini içeren liste oluşturur.
        """
        main_category_xpath = f"//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]/div[{main_category_index}]"
        main_category_element = self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_xpath)))
        self.action.move_to_element(main_category_element).perform()
        time.sleep(1)  # Alt kategori panelinin açılması için bekleme

        alt_container_xpath = "//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[2]/div"
        self.wait.until(EC.visibility_of_element_located((By.XPATH, alt_container_xpath)))
        alt_elements = self.driver.find_elements(By.XPATH, alt_container_xpath + "/div")
        alt_categories = []
        for idx, element in enumerate(alt_elements, start=1):
            alt_name = element.text.strip().split('\n')[0]
            if alt_name:
                xpath = f"{alt_container_xpath}/div[{idx}]"
                alt_categories.append({"name": alt_name, "xpath": xpath})
        return alt_categories

    def get_product_categories(self, alt_category_xpath):
        """
        Belirtilen alt kategori bloğu içerisinde yer alan ürün kategorilerini (ul/li yapısı) liste olarak döndürür.
        Güncelleme: Eğer li içerisinde <a> etiketi varsa, clickable öğe olarak <a> hedeflenir.
        """
        try:
            product_list_xpath = alt_category_xpath + "/div/ul/li"
            self.wait.until(EC.visibility_of_element_located((By.XPATH, product_list_xpath)))
            product_elements = self.driver.find_elements(By.XPATH, product_list_xpath)
            product_categories = []
            for idx, element in enumerate(product_elements, start=1):
                # Eğer li içerisinde <a> varsa, onu hedefleyelim
                try:
                    a_elem = element.find_element(By.TAG_NAME, "a")
                    prod_name = a_elem.text.strip()
                    if prod_name:
                        xpath = f"({product_list_xpath})[{idx}]/a"
                        product_categories.append({"name": prod_name, "xpath": xpath})
                    else:
                        # Eğer a etiketi varsa fakat text boşsa, li içindeki metni kullan
                        prod_name = element.text.strip()
                        if prod_name:
                            xpath = f"({product_list_xpath})[{idx}]"
                            product_categories.append({"name": prod_name, "xpath": xpath})
                except Exception:
                    # Eğer <a> etiketi bulunamazsa li elementini kullan.
                    prod_name = element.text.strip()
                    if prod_name:
                        xpath = f"({product_list_xpath})[{idx}]"
                        product_categories.append({"name": prod_name, "xpath": xpath})
            return product_categories
        except Exception as e:
            logging.info("Ürün kategorileri alınırken hata: %s", e)
            return []

    def navigate_to_category_by_name(self, category_string):
        """
        Kullanıcıdan alınan "AnaKategori AltKategori ÜrünKategorisi" şeklindeki metni boşluklara göre ayırıp,
        sırasıyla ilgili kategori butonlarına tıklayarak ürünlerin listelendiği sayfaya yönlendirir.
        Tıklamanın gerçekleştiğinden emin olmak için URL değişikliği veya belirli bir ürün listeleme öğesinin görünürlüğü beklenir.
        """
        try:
            parts = category_string.split()
            if len(parts) != 3:
                logging.error("Lütfen kategori ifadesini 'AnaKategori AltKategori ÜrünKategorisi' formatında verin.")
                return None

            main_cat_name, alt_cat_name, prod_cat_name = parts

            # 1. Kategori menüsünü açıyoruz.
            self.open_categories_menu()
            time.sleep(1)

            # 2. Ana kategorileri alıp arıyoruz.
            main_categories = self.get_main_categories()
            found_main = None
            main_index = None
            for idx, cat in enumerate(main_categories, start=1):
                if main_cat_name.lower() in cat['name'].lower():
                    found_main = cat
                    main_index = idx
                    break
            if not found_main:
                logging.error("Ana kategori '%s' bulunamadı.", main_cat_name)
                return None

            # Ana kategori üzerinde hover yaparak alt kategorilerin açılmasını sağlıyoruz.
            main_category_xpath = found_main['xpath']
            main_category_element = self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_xpath)))
            self.action.move_to_element(main_category_element).perform()
            time.sleep(1)

            # 3. Alt kategorileri alıp arıyoruz.
            alt_categories = self.get_alt_categories(main_index)
            found_alt = None
            for alt in alt_categories:
                if alt_cat_name.lower() in alt['name'].lower():
                    found_alt = alt
                    break
            if not found_alt:
                logging.error("Alt kategori '%s' bulunamadı.", alt_cat_name)
                return None

            alt_category_xpath = found_alt['xpath']
            alt_category_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, alt_category_xpath)))
            alt_category_element.click()
            time.sleep(1)

            # 4. Ürün kategorilerini alıp arıyoruz.
            product_categories = self.get_product_categories(alt_category_xpath)
            found_prod = None
            for prod in product_categories:
                if prod_cat_name.lower() in prod['name'].lower():
                    found_prod = prod
                    break
            if not found_prod:
                logging.error("Ürün kategorisi '%s' bulunamadı.", prod_cat_name)
                return None

            prod_category_xpath = found_prod['xpath']
            prod_category_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, prod_category_xpath)))

            # Tıklamadan önce mevcut URL'yi alalım.
            old_url = self.driver.current_url
            logging.info("Tıklamadan önceki URL: %s", old_url)

            # Tıklama işlemi: (Gerekirse JavaScript click de denenebilir.)
            prod_category_element.click()
            # Alternatif: self.driver.execute_script("arguments[0].click();", prod_category_element)

            # URL değişikliğini bekleyelim.
            try:
                self.wait.until(lambda d: d.current_url != old_url, message="URL değişmedi.")
                new_url = self.driver.current_url
                logging.info("Yeni URL: %s", new_url)
            except TimeoutException:
                logging.info("URL değişmedi, AJAX yönlendirmesi olabilir. Ürün liste öğesi bekleniyor.")
                # AJAX yönlendirmesi durumunda ürün listelemenin başladığını gösteren bir öğeyi bekleyin.
                # Aşağıdaki XPath, Trendyol ürün listeleme container'ı için örnek bir değer; gerekirse güncelleyin.
                product_container_xpath = "//*[@class='prdct-cntnr-wrppr']"
                self.wait.until(EC.visibility_of_element_located((By.XPATH, product_container_xpath)))
                new_url = self.driver.current_url
                logging.info("Ürün listeleme bölgesi yüklendi. Mevcut URL: %s", new_url)

            return new_url

        except Exception as e:
            logging.error("navigate_to_category_by_name metodu çalışırken hata oluştu: %s", e)
            return None

    def close(self):
        """Tarayıcıyı kapatır."""
        self.driver.quit()

# Örnek kullanım:
if __name__ == "__main__":
    # ChromeDriver'ın tam yolunu sisteminize göre ayarlayın.
    driver_path = "/Users/ayberkturk/ayb/env/bin/chromedriver"  # Kendi yolunuzu ekleyin.
    category_search = Trendyol_Category_Search(driver_path)
    
    try:
        # Örneğin "Erkek Giyim Ceket" ifadesi;
        # Ana kategori: "Erkek", Alt kategori: "Giyim", Ürün kategorisi: "Ceket" şeklinde değerlendirilecek.
        target_url = category_search.navigate_to_category_by_name("Erkek Bere")
        if target_url:
            logging.info("Final Yönlendirilen URL: %s", target_url)
        else:
            logging.info("Yönlendirme tamamlanamadı.")
    finally:
        category_search.close()