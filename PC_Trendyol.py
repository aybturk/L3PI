import os
import re
import json
import time
import logging
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')



#######################################################################
# 1. Kategori Sayfasına Ulaşma (Trendyol Kategori Seçimi)
#######################################################################
class Trendyol_Category_Search:
    def __init__(self, driver_path, base_url="https://www.trendyol.com/butik/liste/2/erkek"):
        # Chrome seçenekleri: bildirimleri kapatıyoruz.
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
        """Sayfa yüklendikten sonra çıkan çerez popup’ını kapatır."""
        try:
            cookie_xpath = "/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div/button[3]"
            cookie_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, cookie_xpath)))
            cookie_btn.click()
            time.sleep(1)
        except Exception as e:
            logging.info("Çerez popup'ı bulunamadı veya zaten kapalı: %s", e)

    def open_categories_menu(self):
        """'Tüm Kategoriler' butonuna tıklayarak kategori menüsünü açar."""
        tum_kategoriler_xpath = "/html/body/div[1]/div[2]/div/div/div[1]/nav/div/div/div/div"
        menu_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, tum_kategoriler_xpath)))
        menu_element.click()
        time.sleep(1)  # Menü açılma animasyonu için bekleme
        main_category_container_xpath = "//*[@id='navigation-wrapper']/nav/div/div/div/div[2]/div/div[1]"
        self.wait.until(EC.visibility_of_element_located((By.XPATH, main_category_container_xpath)))

    def get_main_categories(self):
        """
        Ana kategorilerin isimlerini ve XPath’lerini liste olarak döndürür.
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
        Belirtilen alt kategori bloğu içerisindeki ürün kategorilerini (ul/li yapısı) döndürür.
        """
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

    def navigate_to_category_by_name(self, category_string):
        """
        Kullanıcının girdiği "AnaKategori AltKategori ÜrünKategorisi" formatındaki ifadeye göre ilgili
        kategori butonlarına tıklayarak ürünlerin listelendiği sayfaya yönlendirir.
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

            # Ana kategori üzerinde hover yapıyoruz.
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

            old_url = self.driver.current_url
            logging.info("Tıklamadan önceki URL: %s", old_url)

            prod_category_element.click()

            # URL değişikliğini veya ürün listeleme alanını bekliyoruz.
            try:
                self.wait.until(lambda d: d.current_url != old_url, message="URL değişmedi.")
                new_url = self.driver.current_url
                logging.info("Yeni URL: %s", new_url)
            except TimeoutException:
                logging.info("URL değişmedi, AJAX yönlendirmesi olabilir. Ürün listeleme bölgesi bekleniyor.")
                product_container_xpath = "//*[@class='prdct-cntnr-wrppr']"
                self.wait.until(EC.visibility_of_element_located((By.XPATH, product_container_xpath)))
                new_url = self.driver.current_url
                logging.info("Ürün listeleme bölgesi yüklendi. Mevcut URL: %s", new_url)

            return new_url

        except Exception as e:
            logging.error("navigate_to_category_by_name çalışırken hata oluştu: %s", e)
            return None

    def close(self):
        """Tarayıcıyı kapatır."""
        self.driver.quit()


#######################################################################
# Yardımcı Fonksiyon: XPath'lerden İlk Bulunan Text'i Döndürme
#######################################################################
def get_text_from_xpaths(driver, xpaths):
    """
    Verilen XPath listesinde sırayla arar ve ilk boş olmayan text değerini döndürür.
    """
    for xpath in xpaths:
        try:
            element = driver.find_element(By.XPATH, xpath)
            text = element.text.strip()
            if text:
                return text
        except Exception:
            continue
    return None


#######################################################################
# 2. Ürün Sayfasındaki Detayları İşleme ve Dışa Aktarma
#######################################################################
def process_product(driver, link_xpath, product_index, category_folder):
    """
    Verilen ürün link XPath’ine göre ürün detay sayfasına gidip;
      - Ürün bilgilerini (ürün adı, review, average, fiyat) farklı XPath’lerden deneme yoluyla çeker,
      - Ürüne ait klasörü (ürün ismine göre) oluşturup bilgileri JSON olarak kaydeder,
      - Ürün linkini "ProductLink" anahtarı altında JSON’a ekler,
      - Görsel galerisindeki ilk 3 resmi indirir.
    İşlem sonunda ürün detay sayfasından liste sayfasına geri döner.
    """
    try:
        # Ürün linkini bulup detay sayfasına geçiş yapıyoruz.
        link_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, link_xpath))
        )
        link_url = link_element.get_attribute("href")
        driver.get(link_url)
        driver.fullscreen_window()
        time.sleep(3)

        # Step 2: Konum seçme butonunu atla (varsa)
        try:
            skip_location = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/aside/div/div/div[2]/div/div[2]/div/div/button'
            skip_button = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, skip_location))
            )
            skip_button.click()
            time.sleep(5)
        except TimeoutException:
            pass  # Buton görünmüyorsa devam et

        # --- Ürün Bilgilerini Çekme ---
        # Ürün adı için çoklu XPath listesi
        name_xpaths = [
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[1]/h1/span',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[1]',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/div[1]/h1/span',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/div[1]/h1'
        ]

        # Review için çoklu XPath listesi
        review_xpaths = [
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/div[2]/div/div[3]/a',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/div[2]/div/div[3]',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[3]/a',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[3]'
        ]

        # Average için çoklu XPath listesi
        average_xpaths = [
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[1]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]'
        ]

        # Fiyat için çoklu XPath listesi
        price_xpaths = [
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/div',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/div/div[2]',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/span',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]',
            '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/div/div[2]/span[2]'
        ]

        product_name = get_text_from_xpaths(driver, name_xpaths)
        if product_name:
            logging.info(f"Ürün Adı: {product_name}")
        else:
            logging.error("Ürün adı bulunamadı.")

        review = get_text_from_xpaths(driver, review_xpaths)
        if review:
            logging.info(f"Review: {review}")
        else:
            logging.error("Review bilgisi bulunamadı.")

        average = get_text_from_xpaths(driver, average_xpaths)
        if average:
            logging.info(f"Average: {average}")
        else:
            logging.error("Average bilgisi bulunamadı.")

        price = get_text_from_xpaths(driver, price_xpaths)
        if price:
            logging.info(f"Price: {price}")
        else:
            logging.error("Fiyat bilgisi bulunamadı.")

        # Ürün linkini de ekleyelim
        product_link = link_url

        product_details = {
            'name': product_name if product_name else "",
            'review': review if review else "",
            'average': average if average else "",
            'price': price if price else "",
            'ProductLink': product_link
        }

        # --- Ürün Klasörü Oluşturma ---
        product_folder_name = re.sub(r'[\\/*?:"<>|]', "", product_name) if product_name else f"product_{product_index}"
        try:
            review_digits = int(''.join(filter(str.isdigit, review))) if review else 0
        except Exception:
            review_digits = 0
        if review_digits > 200:
            product_folder_name += " (potential)"
        product_folder = os.path.join(category_folder, product_folder_name)
        if not os.path.exists(product_folder):
            os.makedirs(product_folder)

        json_file_path = os.path.join(product_folder, "product.json")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(product_details, f, ensure_ascii=False, indent=4)
        logging.info(f"Ürün bilgileri JSON olarak kaydedildi: {json_file_path}")

        # --- Görsel Galerisi İşlemleri ---
        step3_xpath = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[1]/div'
        gallery_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, step3_xpath))
        )
        gallery_button.click()
        time.sleep(3)

        css_selector = '#product-detail-app > div > div.flex-container > div > div:nth-child(2) > div:nth-child(1) > div > div.gallery-modal > div > img'
        for i in range(1, 4):
            try:
                image_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
                )
                image_url = image_element.get_attribute('src')
                logging.info(f"Görsel URL'si ({product_index}-{i}): {image_url}")

                if image_url:
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        img_file_path = os.path.join(product_folder, f"image_{i}.jpg")
                        with open(img_file_path, "wb") as file:
                            file.write(response.content)
                        logging.info(f"Görsel başarıyla indirildi: {img_file_path}")
                    else:
                        logging.error(f"Görsel indirilemedi, HTTP Durum Kodu: {response.status_code}")
                else:
                    logging.error(f"Görsel URL'si bulunamadı ({product_index}-{i}).")

                ActionChains(driver).send_keys(Keys.ARROW_RIGHT).perform()
                time.sleep(2)
            except Exception as e:
                logging.error(f"Görsel indirme sırasında hata oluştu ({product_index}-{i}): {e}")

    except Exception as e:
        logging.error(f"Ürün işlenirken hata oluştu: {e}")
    finally:
        driver.back()
        time.sleep(3)


#######################################################################
# 3. Ana Program: Kategoriye Git, Sıralama Uygula, Ürünleri İşle ve Dışa Aktar
#######################################################################
if __name__ == "__main__":
    # Chromedriver yolunuzu belirtin.
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"  # Kendi yolunuzu ekleyin.
    
    # Kategori parametresi: "AnaKategori AltKategori ÜrünKategorisi" formatında olmalı.
    kategori_param = "Deri"
    
    # Sıralama metodu: "BEST_SELLER", "MOST_FAVOURITE" veya "MOST_RATED"
    sorting_method = "BEST_SELLER"  # İstediğiniz metodu buradan değiştirebilirsiniz.
    
    # Trendyol kategori sayfasına ulaşmak için nesneyi oluşturuyoruz.
    category_search = Trendyol_Category_Search(driver_path)
    
    try:
        target_url = category_search.navigate_to_category_by_name(kategori_param)
        if not target_url:
            logging.error("Kategoriye yönlendirme tamamlanamadı.")
            category_search.close()
            exit(1)
        logging.info("Final Yönlendirilen URL: %s", target_url)

        # Sıralama metoduna göre URL'yi güncelleyelim.
        sorted_url = target_url + "?sst=" + sorting_method
        driver = category_search.driver
        driver.get(sorted_url)
        time.sleep(3)
        logging.info("Sıralama metoduna göre URL: %s", driver.current_url)

        # Ana kategori adı, klasör yapısında kullanılacak (örneğin "Kozmetik")
        main_category_name = kategori_param.split()[0]
        base_output_folder = os.path.join(os.getcwd(), "Trendyol_Products", main_category_name)
        if not os.path.exists(base_output_folder):
            os.makedirs(base_output_folder)

        # Artık ürün listeleme sayfasındayız; ürünleri sırayla işleyelim.
        # Örneğin ürün indeksleri 2'den 6'ya kadar işlenecek (sayfa yapısına göre ayarlayın)
        start_index = 2
        end_index = 6
        for product_index in range(start_index, end_index):
            product_xpath = f'//*[@id="search-app"]/div/div/div/div[2]/div[4]/div[1]/div/div[{product_index}]/div/a'
            process_product(driver, product_xpath, product_index, base_output_folder)
            if (product_index - start_index + 1) % 8 == 0:
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(2)

    except Exception as e:
        logging.error("Ana program çalışırken hata oluştu: %s", e)
    finally:
        category_search.close()