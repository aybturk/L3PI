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




# ChromeDriver ayarları
options = webdriver.ChromeOptions()
options.add_argument("--disable-notifications")
service = Service("/Users/ayberkturk/Desktop/chromedriver-mac-arm64-2/chromedriver")
driver = webdriver.Chrome(service=service, options=options)



driver.get('www.aliexpress.com')


                          

