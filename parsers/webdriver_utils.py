import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from config import CHROMEDRIVER_PATH

logger = logging.getLogger(__name__)


def start_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def restart_webdriver(driver):
    try:
        driver.quit()
    except Exception as e:
        logger.error(f"Error while quitting WebDriver: {e}")

    return start_webdriver()
