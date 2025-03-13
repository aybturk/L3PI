from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from selenium.webdriver.chrome.service import Service


class EBayCategoryExplorer:
    def __init__(self):
        service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
        self.driver = webdriver.Chrome(service=service)
        self.wait = WebDriverWait(self.driver, 15)
        self.base_url = "https://www.ebay.com/"
        self.category_data = {}

    def navigate_categories(self):
        self.driver.get(self.base_url)
        
        # Ana kategori menüsünü bul (vl-flyout-nav)
        main_menu = self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="vl-flyout-nav"]/ul'))
        )
        
        # Tüm ana kategori li elementlerini al (3'ten başlayarak)
        main_categories = main_menu.find_elements(By.XPATH, './li[position()>=3]')
        
        for index, category in enumerate(main_categories, start=3):
            try:
                # Kategoriye hover et ve alt menüyü aç
                webdriver.ActionChains(self.driver).move_to_element(category).perform()
                time.sleep(1)  # Animasyon için bekle
                
                # Alt kategorilerin container'ını bul
                submenu_xpath = f'/html/body/div[2]/div[2]/section[2]/section[1]/div/ul/li[{index}]/section/div/ul'
                submenu = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, submenu_xpath))
                )
                
                # Her alt kategoriyi işle
                subcategories = submenu.find_elements(By.XPATH, './li')
                for sub_idx in range(1, len(subcategories)+1):
                    sub_xpath = f'{submenu_xpath}/li[{sub_idx}]/a'
                    sub_category = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, sub_xpath))
                    )
                    category_name = sub_category.text
                    sub_category.click()
                    
                    # Ürün sayısını al
                    try:
                        count_element = self.wait.until(
                            EC.presence_of_element_located((By.XPATH, '//*[@class="srp-controls__count-heading"]'))
                        )
                        product_count = count_element.text.split()[0]
                    except TimeoutException:
                        product_count = "N/A"
                    
                    self.category_data[category_name] = product_count
                    self.driver.back()
                    time.sleep(2)
                    
            except Exception as e:
                print(f"Hata oluştu: {str(e)}")
                continue

    def export_data(self):
        with open('ebay_categories.csv', 'w') as f:
            f.write("Category,ProductCount\n")
            for cat, count in self.category_data.items():
                f.write(f"{cat},{count}\n")

# Kullanım
if __name__ == "__main__":
    explorer = EBayCategoryExplorer()
    explorer.navigate_categories()
    explorer.export_data()