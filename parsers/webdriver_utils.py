import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from config import CHROME_BINARY_PATH, CHROMEDRIVER_PATH

logger = logging.getLogger(__name__)


async def start_webdriver_async():
    """
    Asynchronously start the WebDriver with headless mode enforced.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.binary_location = CHROME_BINARY_PATH

    service = Service(CHROMEDRIVER_PATH)
    logger.info("Starting WebDriver on {}".format(CHROMEDRIVER_PATH))

    # Use asyncio.to_thread to run blocking code in a thread
    driver = await asyncio.to_thread(webdriver.Chrome, service=service, options=options)
    return driver


async def restart_webdriver_async(driver):
    """
    Asynchronously restart the WebDriver with headless mode enforced.
    """
    try:
        # Quit the WebDriver asynchronously
        await asyncio.to_thread(driver.quit)
    except Exception as e:
        logger.error(f"Error while quitting WebDriver: {e}")

    # Start a new WebDriver asynchronously with enforced headless mode
    return await start_webdriver_async()
