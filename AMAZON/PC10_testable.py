import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

def get_country_text(li_element):
    """
    Verilen li elementi içerisinde <a> etiketi varsa onun metnini,
    yoksa li elementinin metnini döndürür.
    """
    try:
        a_elem = li_element.find_element(By.TAG_NAME, "a")
        return a_elem.text.strip()
    except Exception:
        return li_element.text.strip()

def is_best_sellers_text(text):
    """
    Verilen metin içerisinde, Best Sellers (ve yerel karşılıkları) olabileceğine işaret eden anahtar kelimeler aranır.
    Fransızca için "meilleures ventes" ve "les meilleures ventes" ifadeleri de eklenmiştir.
    """
    candidates = [
        "best sellers",
        "best seller",
        "los más vendidos",
        "bestseller",
        "bestsellery",
        "meilleures ventes",
        "les meilleures ventes"
    ]
    text_lower = text.lower()
    for candidate in candidates:
        if candidate in text_lower:
            return True
    return False

# ChromeDriver ayarları
options = webdriver.ChromeOptions()
options.add_argument("--disable-notifications")
service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 10)

try:
    ###########################################
    # A. ÜLKE VE BEST SELLERS AŞAMALARI
    ###########################################
    driver.get("https://www.amazon.com/customer-preferences/country?")
    time.sleep(2)  # Sayfanın tam yüklenmesi için bekleme

    # Dismiss butonlarını tıklıyoruz.
    dismiss_xpaths = [
        "/html/body/div[1]/header/div/div[3]/div[19]/div/div[3]/span[1]/span/input",
        "/html/body/div[1]/header/div/div[3]/div[19]/div/div[3]/span[1]/span/span"
    ]
    for dismiss_xpath in dismiss_xpaths:
        try:
            dismiss_buttons = driver.find_elements(By.XPATH, dismiss_xpath)
            for btn in dismiss_buttons:
                if btn.is_displayed():
                    btn.click()
                    print(f"Dismiss butonu ({dismiss_xpath}) tıklandı.")
                    time.sleep(1)
        except Exception as e:
            print(f"Dismiss butonu kontrolü ({dismiss_xpath}) hatası: {e}")

    # Ülke listesini açan butona tıklıyoruz.
    country_button_xpath = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[1]/span/span/span/span"
    country_button = wait.until(EC.element_to_be_clickable((By.XPATH, country_button_xpath)))
    country_button.click()
    print("Ülke listesi açma butonuna tıklandı.")
    time.sleep(2)

    # Ülke elemanlarını alıyoruz.
    country_list_xpath = "/html/body/div[3]/div/div/ul/li"
    country_elements = driver.find_elements(By.XPATH, country_list_xpath)
    time.sleep(2)
    print("Bulunan ülke elemanları:")
    for index, li_elem in enumerate(country_elements, start=1):
        text = get_country_text(li_elem)
        print(f"{index}. {text}")

    # İstenen ülkeyi seçiyoruz.
    desired_country = "Germany"  # İstediğiniz ülkeyi buraya yazın.
    country_found = False
    for li_elem in country_elements:
        country_text = get_country_text(li_elem)
        if desired_country.lower() in country_text.lower():
            li_elem.click()
            country_found = True
            print(f"Ülke olarak '{desired_country}' seçildi (eleman metni: '{country_text}').")
            break
    if not country_found:
        print(f"'{desired_country}' listede bulunamadı.")
        driver.quit()
        exit()

    # Onay butonuna tıklıyoruz.
    try:
        confirm_button_xpath = "/html/body/div[1]/div[1]/div/div[2]/div[3]/div[3]/span"
        confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, confirm_button_xpath)))
    except Exception:
        confirm_button_xpath = "/html/body/div[1]/div[1]/div/div[2]/div[3]/div[3]/span/span/input"
        confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, confirm_button_xpath)))
    confirm_button.click()
    print("Onay butonuna tıklandı.")

    # Yeni açılan sekmeye geçiş.
    time.sleep(2)
    all_windows = driver.window_handles
    if len(all_windows) > 1:
        driver.switch_to.window(all_windows[-1])
        print("Yeni açılan sekmeye geçildi.")
    else:
        print("Yeni sekme açılmadı, mevcut sekme üzerinden devam ediyor.")

    # Ana sayfa (logo) tıklama denemesi.
    try:
        home_logo_xpath = "/html/body/div[1]/div[1]/div/div[1]/a"
        home_logo = wait.until(EC.element_to_be_clickable((By.XPATH, home_logo_xpath)))
        home_logo.click()
        print("Ana sayfa (logo) elementine tıklandı.")
        time.sleep(2)
    except Exception as e:
        print("Ana sayfa (logo) elementine tıklanamadı, adım atlandı.")

    # Çerez/uyarı bildirimlerini kapatma.
    cookie_alert_xpaths = [
        "/html/body/div[1]/header/div/div[3]/div[18]/div/div[3]/span[1]/span",
        "/html/body/div[1]/span/form/div[2]/div/span[1]",
        "/html/body/div[1]/span/form/div[2]/div/span[1]/span"
    ]
    for xp in cookie_alert_xpaths:
        try:
            alert_elem = driver.find_element(By.XPATH, xp)
            if alert_elem.is_displayed():
                alert_elem.click()
                print(f"Uyarı/çerez bildirimi ({xp}) kapatıldı.")
                time.sleep(1)
        except Exception:
            pass

    # (ABD için) Adres ekleme adımı.
    if desired_country.lower() == "united states":
        address_button_xpaths = [
            "//*[@id='glow-ingress-block']",
            "//*[@id='nav-global-location-popover-link']",
            "//*[@id='nav-packard-glow-loc-icon']"
        ]
        address_clicked = False
        for xp in address_button_xpaths:
            try:
                address_btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                address_btn.click()
                print(f"Adres butonuna ({xp}) tıklandı.")
                address_clicked = True
                break
            except Exception as e:
                print(f"Adres butonu için ({xp}) hata: {e}")
        if address_clicked:
            try:
                zip_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='GLUXZipUpdateInput']")))
                zip_input.clear()
                zip_input.send_keys("10001")
                print("Zip kodu girildi: 10001")
                apply_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='GLUXZipUpdate']")))
                apply_btn.click()
                print("Zip kodu onay butonuna tıklandı.")
                time.sleep(2)
                confirm_close_xpaths = [
                    "/html/body/div[5]/div/div/div[2]/span/span/input",
                    "/html/body/div[5]/div/div/div[2]/span/span/span",
                    "/html/body/div[5]/div/div/div[2]/span"
                ]
                confirmation_clicked = False
                for xp in confirm_close_xpaths:
                    try:
                        confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                        confirm_btn.click()
                        print(f"Adres onay penceresi kapatma butonu ({xp}) tıklandı.")
                        confirmation_clicked = True
                        break
                    except Exception as e:
                        print(f"Adres onay kapatma butonu için ({xp}) hatası: {e}")
                if not confirmation_clicked:
                    print("Adres onay penceresi kapatma butonu bulunamadı.")
                time.sleep(2)
            except Exception as e:
                print("Adres ekleme adımında hata:", e)

    # Best Sellers linkini bulup tıklama.
    nav_xpaths = [
        "/html/body/div[1]/header/div/div[4]/div[2]/div[2]/div/a[1]",
        "/html/body/div[1]/header/div/div[4]/div[2]/div[2]/div/a[2]"
    ]
    best_sellers_link = None
    for xp in nav_xpaths:
        try:
            elem = driver.find_element(By.XPATH, xp)
            text = elem.text.strip()
            print(f"Nav elemanı bulunuyor: '{text}'")
            if is_best_sellers_text(text):
                best_sellers_link = elem
                print(f"'{text}' ifadesi Best Sellers linki olarak belirlendi.")
                break
        except Exception as e:
            print(f"Nav elementi için ({xp}) hata: {e}")
            continue
    if best_sellers_link is None:
        try:
            nav_container = driver.find_element(By.XPATH, "//div[contains(@class,'nav')]")
            nav_links = nav_container.find_elements(By.TAG_NAME, "a")
            for link in nav_links:
                text = link.text.strip()
                print(f"Genel nav elemanı: '{text}'")
                if is_best_sellers_text(text):
                    best_sellers_link = link
                    print(f"Genel aramada '{text}' ifadesi Best Sellers linki olarak bulundu.")
                    break
        except Exception as e:
            print("Genel nav araması sırasında hata:", e)
    if best_sellers_link:
        best_sellers_link.click()
        print("Best Sellers sayfasına yönlendirme yapıldı.")
    else:
        print("Best Sellers bağlantısı bulunamadı.")

    ###########################################
    # B. BEST SELLERS SAYFASINDA ALT KATEGORİ İŞLEMLERİ
    ###########################################
    categories_container_xpath = "/html/body/div[1]/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/div/div[2]"
    wait.until(EC.presence_of_element_located((By.XPATH, categories_container_xpath)))
    print("Best Sellers sayfasındaki kategori container'ı bulundu.")

    # Alt kategori elemanlarını alıyoruz.
    category_elements = driver.find_elements(By.XPATH, categories_container_xpath + "/div")
    num_categories = len(category_elements)
    print(f"Toplam {num_categories} alt kategori bulundu.")

    # Her alt kategori için:
    for i in range(num_categories):
        # Kategori elemanını taze olarak almak için birkaç deneme.
        retries = 0
        current_category = None
        while retries < 3:
            try:
                categories_container = wait.until(EC.presence_of_element_located((By.XPATH, categories_container_xpath)))
                category_elements = categories_container.find_elements(By.XPATH, "./div")
                if i < len(category_elements):
                    current_category = category_elements[i]
                    break
                else:
                    break
            except StaleElementReferenceException:
                print("Stale element hatası: kategori container yeniden çekiliyor.")
                time.sleep(2)
                retries += 1
        if current_category is None:
            print("Kategori elemanı alınamadı, sonraki kategoriye geçiliyor.")
            continue

        try:
            a_elem = current_category.find_element(By.TAG_NAME, "a")
            subcat_text = a_elem.text.strip()
            subcat_link = a_elem.get_attribute("href")
            print(f"{i+1}. Alt kategori: '{subcat_text}' - Link: {subcat_link}")
            # Alt kategoriye tıklıyoruz.
            a_elem.click()
        except Exception as e:
            print(f"{i+1}. Alt kategori tıklama hatası: {e}")
            continue

        time.sleep(2)

        # Gidilen alt kategori sayfasında sayfayı aşağı kaydırıp bekleyelim.
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(3)
        print(f"{i+1}. alt kategori sayfası URL: {driver.current_url}")

        # Ürün etkileşimine geçmeden (şimdilik boşveriyoruz) sadece bekleyip geri dönüyoruz.
        driver.back()
        time.sleep(2)

    print("Tüm alt kategoriler için işlem tamamlandı.")
    time.sleep(5)

except Exception as e:
    print("Bir hata oluştu:", e)
finally:
    driver.quit()