import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_AI_KEY = os.getenv("OPENAI_AI_KEY")
DB_URI = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@armenia-db:5432/armenia_outages"
CHROMEDRIVER_PATH = os.getenv(
    "CHROMEDRIVER_PATH",
    # os.path.expanduser("~/chromedriver/chromedriver-linux64/chromedriver"),
    "/usr/bin/chromedriver",  # for docker
)
CHROME_BINARY_PATH = os.getenv(
    "CHROME_BINARY_PATH",
    "/usr/bin/google-chrome",
)
CHANNEL_ID_HY = os.getenv("CHANNEL_ID_HY")
CHANNEL_ID_RU = os.getenv("CHANNEL_ID_RU")
CHANNEL_ID_EN = os.getenv("CHANNEL_ID_EN")

# URLs for parsing
POWER_OUTAGE_URL = "https://www.ena.am/Info.aspx?id=5&lang={lang}"
WATER_OUTAGE_URL = "https://interactive.vjur.am/"

# Scheduling intervals and first run times
CHECK_FOR_POWER_UPDATES_INTERVAL = int(
    os.getenv("CHECK_FOR_POWER_UPDATES_INTERVAL", 360)
)
CHECK_FOR_WATER_UPDATES_INTERVAL = int(
    os.getenv("CHECK_FOR_WATER_UPDATES_INTERVAL", 3600)
)
POST_UPDATES_INTERVAL = int(os.getenv("POST_UPDATES_INTERVAL", 180))
