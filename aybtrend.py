from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys  # Keys sınıfını içe aktarın
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time




def search_trendyol(driver, query):
    try:
        # BEST_SELLER parametresi dahil edilerek URL oluştur
        url = f"https://www.trendyol.com/sr?q={query}&qt={query}&st={query}&os=1&sst=BEST_SELLER"
        driver.get(url)
        print(f"'{query}' BEST_SELLER araması için sayfa açıldı.")
    except Exception as e:
        print(f"Bir hata oluştu: {e}")
