import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_URI = os.getenv("DATABASE_URL", "sqlite:///events.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHROMEDRIVER_PATH = os.getenv(
    "CHROMEDRIVER_PATH",
    os.path.expanduser("~/chromedriver/chromedriver-linux64/chromedriver"),
)
CHANNEL_ID_AM = os.getenv("CHANNEL_ID_AM")
CHANNEL_ID_RU = os.getenv("CHANNEL_ID_RU")
CHANNEL_ID_EN = os.getenv("CHANNEL_ID_EN")


# URLs for parsing
POWER_OUTAGE_URL = "https://www.ena.am/Info.aspx?id=5&lang={lang}"
WATER_OUTAGE_URL = "https://interactive.vjur.am/"
