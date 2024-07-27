import requests
from bs4 import BeautifulSoup
from googletrans import Translator
from models import EventType, Language
from config import ELECTRICITY_OUTAGE_URL, WATER_OUTAGE_URL


def fetch_electricity_outages(language):
    url = ELECTRICITY_OUTAGE_URL.format(lang=language.value)
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "lxml")
    events = []

    for item in soup.find_all("div", class_="some-class"):
        event = {
            "event_type": EventType.ELECTRICITY.value,
            "area": item.find("span", class_="area").text,
            "city": item.find("span", class_="city").text,
            "street": item.find("span", class_="street").text,
            "house_numbers": item.find("span", class_="house_numbers").text,
            "start_time": item.find("span", class_="start_time").text,
            "end_time": item.find("span", class_="end_time").text,
            "language": Language.AM.value,
        }
        events.append(event)
    return events


def fetch_water_outages():
    url = WATER_OUTAGE_URL
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "lxml")
    events = []

    for item in soup.find_all("div", class_="some-class"):
        event = {
            "event_type": EventType.WATER.value,
            "area": item.find("span", class_="area").text,
            "city": item.find("span", class_="city").text,
            "street": item.find("span", class_="street").text,
            "house_numbers": item.find("span", class_="house_numbers").text,
            "start_time": item.find("span", class_="start_time").text,
            "end_time": item.find("span", class_="end_time").text,
            "language": Language.AM.value,
        }
        events.append(event)
    return events


def translate_event(event, target_lang):
    translator = Translator()
    translated_event = {}
    for key, value in event.items():
        translated_event[key] = translator.translate(value, dest=target_lang.value).text
    return translated_event
