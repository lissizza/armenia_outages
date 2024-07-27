import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_URI = "sqlite:///events.db"

# URLs for parsing
ELECTRICITY_OUTAGE_URL = "https://www.ena.am/Info.aspx?id=5&lang={lang}"
WATER_OUTAGE_URL = "https://interactive.vjur.am/"
