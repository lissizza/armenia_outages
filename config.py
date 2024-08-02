import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_URI = os.getenv("DATABASE_URL", "sqlite:///events.db")
CHROMEDRIVER_PATH = os.getenv(
    "CHROMEDRIVER_PATH",
    os.path.expanduser("~/chromedriver/chromedriver-linux64/chromedriver"),
)

# URLs for parsing
ELECTRICITY_OUTAGE_URL = "https://www.ena.am/Info.aspx?id=5&lang={lang}"
WATER_OUTAGE_URL = "https://interactive.vjur.am/"
