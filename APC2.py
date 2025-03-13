import os
import re
import time
import json
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from TRENDYOL import aybtrend  # Kendi modülünüz

# Chromedriver servisini başlatma
service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
driver = webdriver.Chrome(service=service)

# Arama terimi
search_term = "elbise"
aybtrend.search_trendyol(driver, search_term)
driver.fullscreen_window()
time.sleep(3)

# Main kategori klasörünü oluştur (boşlukları alt çizgi ile değiştirdik)
category_folder = os.path.join(os.getcwd(), search_term.replace(" ", "_"))
if not os.path.exists(category_folder):
    os.makedirs(category_folder)

def process_product(link_xpath, product_index):
    try:
        # Ürün linkini bulup detay sayfasına git
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

        # Ürün bilgilerini çekmek için Xpath'ler
        trendyolname = '/html/body/div[1]/div[6]/main/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[1]/h1'
        trendyolstar = '/html/body/div[1]/div[6]/main/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[3]'
        trendyolavarage = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[2]/div/div[1]/div/div[1]/div/div[1]'
        trendyolprice = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[2]/div/div[1]/div[2]/div/div/div[3]/div/div/span'
        time.sleep(2)

        product_details = {}
        try:
            # Bilgileri çekiyoruz
            product_details['name'] = driver.find_element(By.XPATH, trendyolname).text
            product_details['review'] = driver.find_element(By.XPATH, trendyolstar).text
            product_details['average'] = driver.find_element(By.XPATH, trendyolavarage).text
            product_details['price'] = driver.find_element(By.XPATH, trendyolprice).text

            print(f"Ürün Adı: {product_details['name']}")
            print(f"Review: {product_details['review']}")
            print(f"Average: {product_details['average']}")
            print(f"Price: {product_details['price']}")
        except NoSuchElementException:
            print("Brand, Name veya Price bulunamadı")

        # Ürüne ait klasörü oluşturma
        product_name = product_details.get('name', f"product_{product_index}")
        # Klasör isimlerinde dosya ismi için geçersiz karakterleri temizleyelim
        product_folder_name = re.sub(r'[\\/*?:"<>|]', "", product_name)
        # review bilgisindeki sayı değeri kontrol edelim (200'ün üzerindeyse "(potential)" ibaresi ekleyelim)
        try:
            # Sadece rakamları alıp integer'a çeviriyoruz
            review_digits = int(''.join(filter(str.isdigit, product_details.get('review', '0'))))
        except Exception:
            review_digits = 0

        if review_digits > 200:
            product_folder_name += " (potential)"
        # Kategori klasörü altında ürüne özel klasör
        product_folder = os.path.join(category_folder, product_folder_name)
        if not os.path.exists(product_folder):
            os.makedirs(product_folder)

        # Ürün bilgilerini JSON olarak kaydetme
        json_file_path = os.path.join(product_folder, "product.json")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(product_details, f, ensure_ascii=False, indent=4)

        # Step 3: Görsel Galerisi Açma
        step3_xpath = '//*[@id="product-detail-app"]/div/div[2]/div/div[2]/div[1]/div'
        gallery_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, step3_xpath))
        )
        gallery_button.click()
        time.sleep(3)

        # Galeri içerisindeki görselleri çekme ve indirme
        css_selector = '#product-detail-app > div > div.flex-container > div > div:nth-child(2) > div:nth-child(1) > div > div.gallery-modal > div > img'
        for i in range(1, 4):
            try:
                image_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
                )
                image_url = image_element.get_attribute('src')
                print(f"Görsel URL'si ({product_index}-{i}): {image_url}")

                if image_url:
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        img_file_path = os.path.join(product_folder, f"image_{i}.jpg")
                        with open(img_file_path, "wb") as file:
                            file.write(response.content)
                        print(f"Görsel başarıyla indirildi: {img_file_path}")
                    else:
                        print(f"Görsel indirilemedi, HTTP Durum Kodu: {response.status_code}")
                else:
                    print(f"Görsel URL'si bulunamadı ({product_index}-{i}).")

                # Sağ ok tuşu ile galeride sonraki görsele geçme
                ActionChains(driver).send_keys(Keys.ARROW_RIGHT).perform()
                time.sleep(2)
            except Exception as e:
                print(f"Görsel indirme sırasında hata oluştu ({product_index}-{i}): {e}")

    except Exception as e:
        print(f"Ürün işlenirken hata oluştu: {e}")

    finally:
        # Ürün detay sayfasından geri dön
        driver.back()
        time.sleep(3)

# Ürünleri sırayla işleme
# Örneğin: 4 ile 20 arasında ürünleri işlemek isteyebilirsiniz
start_index = 2
end_index = 20
for product_index in range(start_index, end_index):
    product_xpath = f'//*[@id="search-app"]/div/div/div/div[2]/div[4]/div[1]/div/div[{product_index}]/div/a'
    process_product(product_xpath, product_index)
    
    # Her 8 üründen sonra sayfayı hafifçe aşağı kaydırıyoruz
    if (product_index - start_index + 1) % 8 == 0:
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(2)

# Tarayıcıyı kapatıyoruz
driver.quit()