from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
import time
import json
import os
import re
from pathlib import Path
from TRENDYOL import aybtrend
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import os
import re
import time
import json
import requests


# WebDriver kurulumu
service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
driver = webdriver.Chrome(service=service)

# Arama terimi ve ana klasör oluşturma
search_term = "elbise"
sanitized_search_term = re.sub(r'[\\/*?:"<>|&]', '_', search_term).strip()
main_folder = Path(sanitized_search_term)
main_folder.mkdir(parents=True, exist_ok=True)

aybtrend.search_trendyol(driver, search_term)
driver.fullscreen_window()
time.sleep(3)

def process_product(link_xpath, product_index):
    try:
        # Ürün elementini bul ve scroll et
        link_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, link_xpath))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_element)
        time.sleep(1)
        
        # Ürün detay sayfasına git
        link_url = link_element.get_attribute('href')
        driver.get(link_url)
        time.sleep(3)

        # Konum bilgisi atlama
        try:
            skip_location = '//button[contains(text(), "Anladım")]'
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, skip_location))
            ).click()
            time.sleep(2)
        except TimeoutException:
            pass

        # Ürün bilgilerini çek
        product_details = {
            'name': '',
            'price': '',
            'review_count': 0,
            'rating': ''
        }

        try:
            product_details['name'] = driver.find_element(By.CSS_SELECTOR, 'h1.pr-new-br').text
            product_details['price'] = driver.find_element(By.CSS_SELECTOR, 'span.prc-dsc').text
            review_text = driver.find_element(By.CSS_SELECTOR, 'span.rv-count').text
            product_details['review_count'] = int(review_text.split()[0]) if review_text else 0
            product_details['rating'] = driver.find_element(By.CSS_SELECTOR, 'span.pr-rnr-sm-p').text
        except Exception as e:
            print(f"Bilgi toplama hatası: {str(e)}")

        # Klasör yapısı oluştur
        product_name = re.sub(r'[\\/*?:"<>|]', '_', product_details['name']).strip()[:30]
        folder_suffix = "_potential" if product_details['review_count'] > 200 else ""
        product_folder = main_folder / f"{product_index}_{product_name}{folder_suffix}"
        product_folder.mkdir(parents=True, exist_ok=True)

        # JSON kaydet
        with open(product_folder/'product.json', 'w', encoding='utf-8') as f:
            json.dump(product_details, f, ensure_ascii=False, indent=4)

        # Görselleri indir
        try:
            driver.find_element(By.CSS_SELECTOR, 'div.image-container').click()
            time.sleep(2)
            
            for i, img in enumerate(driver.find_elements(By.CSS_SELECTOR, 'div.image-slide img')[:3]):
                img_url = img.get_attribute('src').split('?')[0]
                response = requests.get(img_url)
                if response.status_code == 200:
                    with open(product_folder/f'image_{i+1}.jpg', 'wb') as f:
                        f.write(response.content)
        except Exception as e:
            print(f"Görsel indirme hatası: {str(e)}")

    except Exception as e:
        print(f"Genel hata: {str(e)}")
    finally:
        driver.back()
        time.sleep(2)

# Ürünleri işleme döngüsü
for idx in range(2, 20):
    try:
        # Her 8 üründe bir scroll
        if (idx-4) % 8 == 0 and idx != 4:
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(2)
            
        product_xpath = f'//*[@id="search-app"]/div/div/div/div[2]/div[4]/div[1]/div/div[{idx}]/div/a'
        process_product(product_xpath, idx)
        
    except Exception as e:
        print(f"Ürün {idx} işlenemedi: {str(e)}")
        continue

driver.quit()