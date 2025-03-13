import time
import logging
import os
import re
import json
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class TrendyolScraper:
    """
    Trendyol üzerinde belirli bir kategoriye yönelip, istenen sıralama (filtre)
    uygulandıktan sonra ürün detaylarını çekip, her ürünü ayrı bir klasör
    altında JSON dosyası ve görseller ile saklayan sınıf.
    
    Klasör yapısı:
      Trendyol Product/
          └─ [AnaKategori]/
              └─ [AltKategori]/
                  └─ [ÜrünKategorisi]/
                      └─ 1_UrunIsmi[_potential]/
                          ├─ product.json
                          ├─ image_1.jpg
                          ├─ image_2.jpg
                          └─ image_3.jpg
    """

    # Güncellenmiş XPath’ler:
    XPATH_PRODUCT_INFO = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[1]/h1'
    XPATH_RATING_INFO = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[3]'
    XPATH_AVERAGE_RATING_INFO = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]'
    XPATH_PRICE_INFO = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/span'

    # Galeri butonunun XPath’i (sayfanın üst kısmında yer alır)
    XPATH_GALLERY_BUTTON = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[1]/div'
    # Galeri modalındaki görseli çeken CSS selector
    CSS_SELECTOR_GALLERY_IMAGE = '#product-detail-app > div > div.flex-container > div > div:nth-child(2) > div:nth-child(1) > div > div.gallery-modal > div > img'

    def __init__(self, driver_path, base_url="https://www.trendyol.com/butik/liste/2/erkek"):
        """
        :param driver_path: ChromeDriver'ın tam yolu.
        :param base_url: Başlangıç URL’si (kategori menüsü açılabilsin diye).
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-notifications")
        service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)
        self.action = ActionChains(self.driver)
        self.driver.get(base_url)
        time.sleep(2)  # Sayfanın tam yüklenmesi için bekleme
        self.dismiss_cookies()

        # Ürünlerin kaydedileceği ana klasörü oluşturuyoruz:
        self.base_folder = Path.cwd() / "Trendyol Product"
        self.base_folder.mkdir(exist_ok=True)
        # Kategori isimlerini saklamak için
        self.current_main = None
        self.current_alt = None
        self.current_prod = None

    def dismiss_cookies(self):
        """Çerez popup’ını kapatır."""
        try:
            cookie_xpath = "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div/button[3]"
            cookie_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, cookie_xpath)))
            cookie_btn.click()
            time.sleep(1)
        except Exception as e:
            logging.info("Çerez popup'ı bulunamadı veya kapalı: %s", e)

    # =====================
    # Kategori Navigasyonu
    # =====================
    def open_categories_menu(self):
        tum_kategoriler_xpath = "/html/body/div[1]/div[2]/div/div/div[1]/nav/div/div/div/div"
        menu_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, tum_kategoriler_xpath)))
        menu_element.click()
        time.sleep(1)
        main_category_container_xpath = "//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]"
        self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_container_xpath)))

    def get_main_categories(self):
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
        main_category_xpath = f"//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]/div[{main_category_index}]"
        main_category_element = self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_xpath)))
        self.action.move_to_element(main_category_element).perform()
        time.sleep(1)
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
        try:
            product_list_xpath = alt_category_xpath + "/div/ul/li"
            self.wait.until(EC.visibility_of_element_located((By.XPATH, product_list_xpath)))
            product_elements = self.driver.find_elements(By.XPATH, product_list_xpath)
            product_categories = []
            for idx, element in enumerate(product_elements, start=1):
                try:
                    a_elem = element.find_element(By.TAG_NAME, "a")
                    prod_name = a_elem.text.strip()
                    if prod_name:
                        xpath = f"({product_list_xpath})[{idx}]/a"
                        product_categories.append({"name": prod_name, "xpath": xpath})
                    else:
                        prod_name = element.text.strip()
                        if prod_name:
                            xpath = f"({product_list_xpath})[{idx}]"
                            product_categories.append({"name": prod_name, "xpath": xpath})
                except Exception:
                    prod_name = element.text.strip()
                    if prod_name:
                        xpath = f"({product_list_xpath})[{idx}]"
                        product_categories.append({"name": prod_name, "xpath": xpath})
            return product_categories
        except Exception as e:
            logging.info("Ürün kategorileri alınırken hata: %s", e)
            return []

    def navigate_to_category(self, main_cat, alt_cat, prod_cat):
        try:
            self.open_categories_menu()
            time.sleep(1)
            main_categories = self.get_main_categories()
            found_main = None
            main_index = None
            for idx, cat in enumerate(main_categories, start=1):
                if main_cat.lower() in cat['name'].lower():
                    found_main = cat
                    main_index = idx
                    break
            if not found_main:
                logging.error("Ana kategori '%s' bulunamadı.", main_cat)
                return False
            main_category_xpath = found_main['xpath']
            main_category_element = self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_xpath)))
            self.action.move_to_element(main_category_element).perform()
            time.sleep(1)
            alt_categories = self.get_alt_categories(main_index)
            found_alt = None
            for alt in alt_categories:
                if alt_cat.lower() in alt['name'].lower():
                    found_alt = alt
                    break
            if not found_alt:
                logging.error("Alt kategori '%s' bulunamadı.", alt_cat)
                return False
            alt_category_xpath = found_alt['xpath']
            alt_category_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, alt_category_xpath)))
            alt_category_element.click()
            time.sleep(1)
            product_categories = self.get_product_categories(alt_category_xpath)
            found_prod = None
            for prod in product_categories:
                if prod_cat.lower() in prod['name'].lower():
                    found_prod = prod
                    break
            if not found_prod:
                logging.error("Ürün kategorisi '%s' bulunamadı.", prod_cat)
                return False
            prod_category_xpath = found_prod['xpath']
            prod_category_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, prod_category_xpath)))
            old_url = self.driver.current_url
            prod_category_element.click()
            try:
                self.wait.until(lambda d: d.current_url != old_url, message="URL değişmedi.")
                logging.info("Yeni URL: %s", self.driver.current_url)
            except TimeoutException:
                product_container_xpath = "//*[@class='prdct-cntnr-wrppr']"
                self.wait.until(EC.visibility_of_element_located((By.XPATH, product_container_xpath)))
                logging.info("Ürün listeleme bölgesi yüklendi. URL: %s", self.driver.current_url)
            self.current_main = main_cat
            self.current_alt = alt_cat
            self.current_prod = prod_cat
            return True
        except Exception as e:
            logging.error("navigate_to_category çalışırken hata: %s", e)
            return False

    def apply_sort_filter(self, filter_name):
        filters = {
            "en çok satan": "BEST_SELLER",
            "en favoriler": "MOST_FAVOURITE",
            "en çok değerlendirilen": "MOST_RATED"
        }
        key = filter_name.lower()
        if key not in filters:
            logging.error("Sıralama filtresi '%s' tanınmıyor.", filter_name)
            return False
        sst_value = filters[key]
        current_url = self.driver.current_url
        parsed_url = urlparse(current_url)
        query = parse_qs(parsed_url.query)
        query['sst'] = sst_value
        new_query = urlencode(query, doseq=True)
        new_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path,
                              parsed_url.params, new_query, parsed_url.fragment))
        self.driver.get(new_url)
        try:
            self.wait.until(EC.url_contains("sst=" + sst_value))
            logging.info("Yeni URL (filtre uygulanmış): %s", self.driver.current_url)
            return True
        except TimeoutException as e:
            logging.error("Filtre uygulanırken hata: %s", e)
            return False

    def process_product(self, product_xpath, product_index, category_folder):
        """
        Ürün detay sayfasını yeni sekmede açıp, ürün bilgilerini (ürün adı, 
        değerlendirme bilgisi, ortalama puan, fiyat) ve görselleri indirir.
        """
        try:
            # Ürün linkini bul ve yeni sekmede aç
            link_element = self.wait.until(EC.presence_of_element_located((By.XPATH, product_xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_element)
            time.sleep(1)
            link_url = link_element.get_attribute('href')

            original_window = self.driver.current_window_handle
            self.driver.execute_script("window.open(arguments[0]);", link_url)
            time.sleep(3)
            all_windows = self.driver.window_handles
            for window in all_windows:
                if window != original_window:
                    self.driver.switch_to.window(window)
                    break

            details = {}

            try:
                product_info_elem = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.XPATH_PRODUCT_INFO)))
                details['product_info'] = product_info_elem.text.strip()
            except Exception as e:
                details['product_info'] = ""
                logging.error("Ürün bilgileri alınırken hata: %s", e)

            try:
                rating_info_elem = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.XPATH_RATING_INFO)))
                details['rating_info'] = rating_info_elem.text.strip()
            except Exception as e:
                details['rating_info'] = ""
                logging.error("Değerlendirme bilgileri alınırken hata: %s", e)

            try:
                average_rating_elem = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.XPATH_AVERAGE_RATING_INFO)))
                details['average_rating'] = average_rating_elem.text.strip()
            except Exception as e:
                details['average_rating'] = ""
                logging.error("Ortalama puan alınırken hata: %s", e)

            try:
                price_info_elem = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.XPATH_PRICE_INFO)))
                details['price_info'] = price_info_elem.text.strip()
            except Exception as e:
                details['price_info'] = ""
                logging.error("Fiyat bilgileri alınırken hata: %s", e)

            # Görsel işleme: Galeri butonuna tıklayıp, açılan modaldan ilk 3 görseli indir
            images = []
            try:
                gallery_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, self.XPATH_GALLERY_BUTTON)))
                gallery_button.click()
                time.sleep(3)
                for i in range(1, 4):
                    try:
                        image_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.CSS_SELECTOR_GALLERY_IMAGE)))
                        image_url = image_element.get_attribute('src')
                        logging.info(f"Görsel URL'si ({product_index}-{i}): {image_url}")
                        if image_url:
                            response = requests.get(image_url)
                            if response.status_code == 200:
                                image_filename = f'image_{i}.jpg'
                                image_path = category_folder / image_filename
                                with open(image_path, 'wb') as f:
                                    f.write(response.content)
                                images.append(str(image_path))
                            else:
                                logging.error(f"Görsel indirilemedi, HTTP Durum Kodu: {response.status_code}")
                        else:
                            logging.error(f"Görsel URL'si bulunamadı ({product_index}-{i}).")
                        # Galeride sonraki görsele geçmek için sağ ok tuşu gönderiyoruz
                        ActionChains(self.driver).send_keys(Keys.ARROW_RIGHT).perform()
                        time.sleep(2)
                    except Exception as e:
                        logging.error(f"Görsel indirme sırasında hata oluştu ({product_index}-{i}): {e}")
            except Exception as e:
                logging.error("Görsel galerisi açılırken hata: %s", e)
            details['images'] = images

            # Klasör ismi oluşturma: Ürün isminden geçersiz karakterleri temizleyip kısaltıyoruz.
            product_name_safe = re.sub(r'[\\/*?:"<>|]', '_', details.get('product_info', 'urun')).strip()[:30]
            folder_suffix = ""
            product_folder = category_folder / f"{product_index}_{product_name_safe}{folder_suffix}"
            product_folder.mkdir(parents=True, exist_ok=True)

            # JSON dosyasına ürün detaylarını kaydetme
            json_path = product_folder / 'product.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(details, f, ensure_ascii=False, indent=4)

            logging.info("Ürün %d işleme alındı: %s", product_index, details.get('product_info', ''))
        except Exception as e:
            logging.error("process_product sırasında genel hata: %s", e)
        finally:
            # Yeni sekmeyi kapatıp ana pencereye geri dönüyoruz
            self.driver.close()
            self.driver.switch_to.window(original_window)
            time.sleep(2)

    def process_products(self, num_products):
        if not (self.current_main and self.current_alt and self.current_prod):
            logging.error("Kategori bilgileri ayarlanmadı. navigate_to_category çağrılmalı.")
            return

        category_folder = self.base_folder / self.current_main / self.current_alt / self.current_prod
        category_folder.mkdir(parents=True, exist_ok=True)

        for idx in range(1, num_products + 1):
            try:
                product_xpath = f'//*[@id="search-app"]/div/div/div/div[2]/div[4]/div[1]/div/div[{idx}]/div/a'
                logging.info("Ürün %d işleniyor...", idx)
                self.process_product(product_xpath, idx, category_folder)
            except Exception as e:
                logging.error("Ürün %d işlenemedi: %s", idx, e)
                continue

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    DRIVER_PATH = "/path/to/chromedriver"  # Kendi chromedriver yolunuzu buraya girin.
    
    # Örnek parametreler:
    main_category = "Kozmetik"
    alt_category = "Makyaj"
    product_category = "Dudak kalemi"
    sort_filter = "en çok satan"
    num_products = 4

    scraper = TrendyolScraper(driver_path=DRIVER_PATH)
    try:
        if scraper.navigate_to_category(main_category, alt_category, product_category):
            if scraper.apply_sort_filter(sort_filter):
                scraper.process_products(num_products)
            else:
                logging.error("Sıralama filtresi uygulanamadı.")
        else:
            logging.error("Kategoriye yönlendirme yapılamadı.")
    finally:
        scraper.close()




        