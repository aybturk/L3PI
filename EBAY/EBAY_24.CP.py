import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class ProductCollectorAI:
    def __init__(self, driver_path):
        service = Service(driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(service=service, options=options)

        self.base_dir = "ebay_data"
        os.makedirs(self.base_dir, exist_ok=True)

    def go_to_ebay(self):
        self.driver.get("https://www.ebay.com/")
        time.sleep(2)

    def explore_main_categories(self):
        """
        Ana sayfadaki sol menüdeki li[3]-li[11] arasındaki ana kategorilere tıklar.
        Her kategoriye girdikten sonra sayfa ürün içeriyorsa ürünleri toplar,
        yoksa alt kategori butonlarına tıklayarak derinlemesine gezinmeye çalışır.
        """
        main_categories = list(range(3, 12))  # li[3] - li[11]
        for i in main_categories:
            xpath = f'//*[@id="vl-flyout-nav"]/ul/li[{i}]'
            try:
                category_element = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                category_name = category_element.text.strip().replace("/", "-")
                if not category_name:
                    continue
                print(f"\n[ANA KATEGORI] {category_name}")
                category_element.click()
                time.sleep(2)
                
                # Kategori için klasör oluştur
                category_dir = os.path.join(self.base_dir, category_name)
                os.makedirs(category_dir, exist_ok=True)
                
                # Mevcut kategori sayfasını işle
                self.process_current_category(category_path=[category_name])
                
                self.driver.back()
                time.sleep(2)
            except Exception as e:
                print(f"Ana kategori hatası ({xpath}): {e}")
                continue

    def process_current_category(self, category_path):
        """
        Mevcut kategori sayfasında önce ürün var mı diye kontrol eder.
        Eğer ürün varsa scrape_products() çağrılır.
        Ürün yoksa alt kategori navigasyonlarının (primary/secondary) 
        yapısını deneyerek daha derin alt kategorilere geçmeye çalışır.
        """
        self.scroll_down()  # sayfa biraz aşağı kaydırarak lazy load’u tetikle
        time.sleep(1)
        product_count = self.get_product_count()
        if product_count > 0:
            print(f"  !! Ürün bulundu ({product_count} adet), veri toplanıyor...")
            self.scrape_products(category_path)
        else:
            print("  Ürün bulunamadı, alt kategoriler deneniyor...")
            # Önce primary navigasyonu dene:
            if not self.process_subcategories(category_path, primary=True):
                # Primary de sonuç yoksa secondary navigasyonu dene:
                if not self.process_subcategories(category_path, primary=False):
                    print("  Alt kategorilerde de ürün bulunamadı.")

    def process_subcategories(self, parent_category_path, primary=True):
        """
        primary=True ise:
          - Ana kategori butonları: /html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li
          - İçlerinde final kategori butonu: .//section/div/section/div/ul/li[1]
        primary=False ise:
          - İkinci yapı: /html/body/div[2]/div[2]/section[2]/section/div/ul/li
          - Final kategori butonları olarak: .//section/div/ul/li[2] ve .//section/div/ul/li[3]
        Her final kategoriye tıklayıp ürün olup olmadığını kontrol eder.
        """
        subcat_found = False
        container_xpath = (
            '/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li'
            if primary
            else '/html/body/div[2]/div[2]/section[2]/section/div/ul/li'
        )
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, container_xpath))
            )
            subcategories = self.driver.find_elements(By.XPATH, container_xpath)
            print(f"  {primary and 'Primary' or 'Secondary'} navigasyonda {len(subcategories)} alt kategori bulundu.")
        except TimeoutException:
            print(f"  {primary and 'Primary' or 'Secondary'} navigasyon container bulunamadı.")
            return False

        for idx, subcat in enumerate(subcategories, start=1):
            try:
                # Alt kategori ismini al (boşsa index kullanılacak)
                subcat_name = subcat.text.strip() or f"subcat_{idx}"
                print(f"    [ALT KATEGORI] {subcat_name}")
                self.scroll_to_element(subcat)
                try:
                    subcat.click()
                except (StaleElementReferenceException, ElementClickInterceptedException):
                    time.sleep(1)
                    subcat.click()
                time.sleep(1)

                final_buttons = []
                if primary:
                    try:
                        # Primary navigasyonda final kategori butonu:
                        final_btn = subcat.find_element(By.XPATH, ".//section/div/section/div/ul/li[1]")
                        final_buttons.append(final_btn)
                    except NoSuchElementException:
                        print("      Final kategori butonu bulunamadı (primary).")
                else:
                    # Secondary: li[2] ve li[3] deneniyor
                    for pos in [2, 3]:
                        try:
                            btn = subcat.find_element(By.XPATH, f".//section/div/ul/li[{pos}]")
                            final_buttons.append(btn)
                        except NoSuchElementException:
                            continue

                if not final_buttons:
                    print("      Hiçbir final kategori butonu bulunamadı, geri dönülüyor...")
                    self.driver.back()  # alt kategori açılımından çık
                    time.sleep(1)
                    continue

                for btn in final_buttons:
                    try:
                        self.scroll_to_element(btn)
                        btn.click()
                        time.sleep(2)
                        self.scroll_down()
                        time.sleep(1)
                        prod_count = self.get_product_count()
                        if prod_count > 0:
                            print(f"      Alt kategoride ürün bulundu ({prod_count} adet).")
                            # Alt kategori klasör adı olarak alt kategori ismini kullan
                            new_category_path = parent_category_path + [self.sanitize_filename(subcat_name)]
                            self.scrape_products(new_category_path)
                            subcat_found = True
                        else:
                            print("      Final kategori butonunda ürün bulunamadı.")
                        self.driver.back()  # final kategori sayfasından geri
                        time.sleep(2)
                    except Exception as e:
                        print(f"      Final kategori butonuna tıklarken hata: {e}")
                        continue

                self.driver.back()  # alt kategori ana listesine geri dön
                time.sleep(1)
            except Exception as e:
                print(f"    Alt kategori işleme hatası: {e}")
                continue

        return subcat_found

    def get_product_count(self):
        """
        Ürünlerin her iki tipini de sayar:
          - Liste görünüm: li.brwrvr__item-card.brwrvr__item-card--list
          - Gallery görünüm: li.brwrvr__item-card.brwrvr__item-card--gallery
        """
        try:
            products_list = self.driver.find_elements(
                By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--list"
            )
            products_gallery = self.driver.find_elements(
                By.CSS_SELECTOR, "li.brwrvr__item-card.brwrvr__item-card--gallery"
            )
            return len(products_list) + len(products_gallery)
        except Exception:
            return 0

    def scrape_products(self, category_path):
        """
        Mevcut kategori sayfasında bulunan her iki tip ürün listesini de işler.
        Ürün tanımında “sold” kelimesi geçiyorsa ürünü kaydeder.
        Ürün ekran görüntüsü alınırken, ürünün ismine göre (dosya adlarına uygun şekilde)
        klasör ve dosya isimlendirmesi yapılır.
        Ayrıca "Load More" butonu varsa tıklanarak ek ürünler de işlenir.
        """
        try:
            products = self.driver.find_elements(
                By.CSS_SELECTOR,
                "li.brwrvr__item-card.brwrvr__item-card--list, li.brwrvr__item-card.brwrvr__item-card--gallery"
            )
        except Exception as e:
            print(f"Ürünler bulunamadı: {e}")
            return

        products_data = []
        for idx, product in enumerate(products, start=1):
            try:
                self.scroll_to_element(product)
                # Ürünün detay metnini al (örneğin: title veya açıklama kısmı)
                try:
                    container = product.find_element(By.XPATH, "./div/div/div[2]")
                    text = container.text.strip()
                except Exception:
                    text = product.text.strip()

                # Örneğin; sadece "sold" içerenleri kaydedelim (istenirse kaldırılabilir)
                if "sold" not in text.lower():
                    continue

                # İlk satırı ürün ismi olarak alıp, dosya isimlendirmeye uygun hale getir
                product_name = text.splitlines()[0] if text else f"product_{idx}"
                product_name_safe = self.sanitize_filename(product_name)

                screenshot_dir = os.path.join(self.base_dir, *category_path, product_name_safe)
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, "screenshot.png")
                product.screenshot(screenshot_path)

                products_data.append({
                    "name": product_name,
                    "text": text,
                    "screenshot": screenshot_path
                })
                print(f"    Ürün kaydedildi: {product_name_safe}")
            except Exception as e:
                print(f"    Ürün kaydetme hatası: {e}")
                continue

        if products_data:
            json_path = os.path.join(self.base_dir, *category_path, "products.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(products_data, f, indent=2, ensure_ascii=False)
            print(f"    Toplam {len(products_data)} ürün {os.path.join(*category_path)} klasörüne kaydedildi.")

        # "Load More" butonu varsa ek ürünleri yükle ve işle
        self.check_and_click_more_button(category_path)

    def check_and_click_more_button(self, category_path):
        """
        Sayfada “Load More” butonunu kontrol eder, varsa tıklar ve yeni yüklenen
        ürünleri scrape_products() ile işlemi devam ettirir.
        """
        try:
            button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//button[contains(translate(., "LESS", "less"), "more")]')
                )
            )
            if "more" in button.text.lower():
                self.scroll_to_element(button)
                button.click()
                print("    Load More tıklandı.")
                time.sleep(2)
                self.scrape_products(category_path)
        except (TimeoutException, Exception):
            pass

    def scroll_to_element(self, element):
        """Verilen elemente doğru sayfayı yumuşak bir şekilde kaydırır."""
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element,
            )
        except Exception:
            pass
        time.sleep(0.5)

    def scroll_down(self):
        """Sayfayı 300 piksel aşağı kaydırarak lazy-load öğelerin yüklenmesini tetikler."""
        self.driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(1)

    def sanitize_filename(self, name):
        """Dosya adı olarak kullanıma uygun hale getirmek için karakterleri filtreler."""
        # Sadece alfanümerik, boşluk, alt tire ve tire izin ver
        return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    driver_path = "/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver"
    collector = ProductCollectorAI(driver_path)
    try:
        collector.go_to_ebay()
        collector.explore_main_categories()
    finally:
        collector.close()