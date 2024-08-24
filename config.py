import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_URI = os.getenv("DATABASE_URL", "sqlite:///events.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHROMEDRIVER_PATH = os.getenv(
    "CHROMEDRIVER_PATH",
    os.path.expanduser("~/chromedriver/chromedriver-linux64/chromedriver"),
)
CHANNEL_ID_HY = os.getenv("CHANNEL_ID_HY")
CHANNEL_ID_RU = os.getenv("CHANNEL_ID_RU")
CHANNEL_ID_EN = os.getenv("CHANNEL_ID_EN")

# URLs for parsing
POWER_OUTAGE_URL = "https://www.ena.am/Info.aspx?id=5&lang={lang}"
WATER_OUTAGE_URL = "https://interactive.vjur.am/"

# Scheduling intervals and first run times
CHECK_FOR_UPDATES_INTERVAL = int(os.getenv("CHECK_FOR_UPDATES_INTERVAL", 1800))
POST_UPDATES_INTERVAL = int(os.getenv("POST_UPDATES_INTERVAL", 600))
