import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import requests
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

OPEN_WEATHER_MAP_API_KEY = os.getenv("OPEN_WEATHER_MAP_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

RECIPIENT_NUMBER = os.getenv("RECIPIENT_NUMBER")
CITY = os.getenv("CITY")

ALERT_CONDITIONS = {
    "Thunderstorm": "Thunderstorms expected. Stay indoors if possible.",
    "Tornado": "Tornado warning. Seek shelter immediately.",
    "Squall": "Squalls expected. Avoid outdoor activity.",
    "Rain": "Rain expected. Bring an umbrella.",
    "Drizzle": "Drizzle expected. Light jacket recommended.",
    "Snow": "Snow expected. Dress warmly and drive carefully.",
    "Fog": "Foggy conditions expected. Drive with caution.",
    "Mist": "Misty conditions expected. Reduced visibility.",
    "Haze": "Hazy conditions expected. Reduced visibility.",
    "Smoke": "Smoky conditions expected. Limit outdoor exposure.",
    "Dust": "Dusty conditions expected. Limit outdoor exposure.",
    "Sand": "Sandstorm conditions expected. Stay indoors.",
    "Ash": "Volcanic ash detected. Stay indoors and cover airways.",
}

ALERT_PRIORITY = [
    "Tornado",
    "Thunderstorm",
    "Squall",
    "Ash",
    "Sand",
    "Snow",
    "Rain",
    "Smoke",
    "Dust",
    "Fog",
    "Haze",
    "Mist",
    "Drizzle",
]

TEMP_CHANGE_THRESHOLD = 3 # °C

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

_REQUIRED_ENV_VARS = [
    "OPEN_WEATHER_MAP_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_MESSAGING_SERVICE_SID",
    "RECIPIENT_NUMBER",
    "CITY",
]

missing = [var for var in _REQUIRED_ENV_VARS if not os.getenv(var)]
if missing:
    raise EnvironmentError(f"Missing required environment variables: {", ".join(missing)}")


def fetch_coords(city: str) -> tuple[float, float]:
    """
    Fetch coordinates for a given city.
    :param city: Name of city
    :return: Tuple of (latitude, longitude)
    """
    params = {
        "q": city,
        "appid": OPEN_WEATHER_MAP_API_KEY,
        "limit": 1
    }
    response = requests.get("https://api.openweathermap.org/geo/1.0/direct", params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if not data:
        raise ValueError(f"City not found: {city}")

    return data[0]["lat"], data[0]["lon"]


def _fetch_openweather(
        endpoint: str,
        coords: tuple[float, float],
        units: str = "metric",
        **kwargs: Any
) -> dict[str, Any]:
    """
    Base fetch function for OpenWeatherMap API.
    :param endpoint: API endpoint (e.g. 'weather', 'forecast')
    :param coords: Tuple of (latitude, longitude)
    :param units: Units of measurement ('metric', 'imperial', 'standard')
    :param kwargs: Additional endpoint-specific query parameters
    :return: Dict with response data
    """
    params = {
        "lat": coords[0],
        "lon": coords[1],
        "appid": OPEN_WEATHER_MAP_API_KEY,
        "units": units,
        **kwargs
    }
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_weather(coords: tuple[float, float], units: str = "metric") -> dict[str, Any]:
    """
    Fetch current weather for given coordinates.
    :param coords: Tuple of (latitude, longitude)
    :param units: Units of measurement ('metric', 'imperial', 'standard')
    :return: Dict with current weather data
    """
    return _fetch_openweather(endpoint="weather", coords=coords, units=units)


def fetch_5_day_forecast(coords: tuple[float, float], units: str = "metric", cnt: int = 8) -> dict[str, Any]:
    """
    Fetch 5-day forecast with 3-hour step for given coordinates.
    :param coords: Tuple of (latitude, longitude)
    :param units: Units of measurement ('metric', 'imperial', 'standard')
    :param cnt: Number of 3-hour steps to fetch (default 8 = 24 hours)
    :return: Dict with forecast data
    """
    return _fetch_openweather(endpoint="forecast", coords=coords, units=units, cnt=cnt)


def build_forecast_message(forecast_data: dict[str, Any]) -> str:
    """
    Build a concise forecast SMS from OpenWeatherMap forecast response.
    Only includes steps where conditions change or temperature shifts meaningfully.
    Appends highest-priority alert if severe weather detected.
    :param forecast_data: OpenWeatherMap forecast API response
    :return: Formatted forecast string
    """
    utc_offset = forecast_data["city"]["timezone"]
    local_tz = timezone(timedelta(seconds=utc_offset))
    city_name = forecast_data["city"]["name"]

    steps = forecast_data["list"]

    temps = [step["main"]["temp"] for step in steps]
    daily_high = round(max(temps))
    daily_low = round(min(temps))

    date_str = datetime.fromtimestamp(steps[0]["dt"], tz=local_tz).strftime("%b %d")
    lines = [f"{city_name} - {date_str}", f"High: {daily_high}°C  Low: {daily_low}°C"]

    prev_conditions = None
    prev_temp = None
    condition_lines = []

    for step in steps:
        conditions_main = {w["main"] for w in step["weather"]}
        conditions_display = ", ".join(w["description"] for w in step["weather"]).capitalize()
        temp = round(step["main"]["temp"])
        time_str = datetime.fromtimestamp(step["dt"], tz=local_tz).strftime("%#I%p").lower() # '%-I' for linux and macOS, '%#I' for windows

        temp_shifted = prev_temp is not None and abs(temp - prev_temp) >= TEMP_CHANGE_THRESHOLD

        if conditions_main != prev_conditions or temp_shifted:
            condition_lines.append(f"{time_str}: {conditions_display} {temp}°C")
            prev_conditions = conditions_main
            prev_temp = temp

    if len(condition_lines) == 1:
        lines.append(condition_lines[0].split(": ", 1)[1])
    else:
        lines.extend(condition_lines)

    triggered_alerts = {
        w["main"]
        for step in steps
        for w in step["weather"]
        if w["main"] in ALERT_CONDITIONS
    }

    if triggered_alerts:
        dominant = next(a for a in ALERT_PRIORITY if a in triggered_alerts)
        lines.append(ALERT_CONDITIONS[dominant])

    return "\n".join(lines)


def split_message(msg: str, limit: int = 70) -> list[str]:
    """
    Split a message into segments not exceeding a limit of characters, without cutting words.
    :param msg: Full message as string
    :param limit: Max characters per segment
    :return: List of message segments
    """
    lines = msg.split("\n")
    segments = []
    current = ""

    for line in lines:
        if not current:
            current = line
        elif len(current) + 1 + len(line) <= limit:
            current += "\n" + line
        else:
            segments.append(current)
            current = line

    if current:
        segments.append(current)

    return segments


def send_sms(msg: str) -> None:
    """
    Send an SMS message via Twilio, splitting into segments if necessary.
    :param msg: Message body to send
    """
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    segments = split_message(msg)

    for segment in segments:
        message = client.messages.create(
            messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
            body=segment,
            to=RECIPIENT_NUMBER
        )
        logging.info(f"SMS sent. SID: {message.sid}")


def daily_forecast() -> None:
    """Fetch 24-hour forecast and send daily SMS summary."""
    try:
        coords = fetch_coords(CITY)
        forecast = fetch_5_day_forecast(coords)
        message = build_forecast_message(forecast)
        send_sms(message)
        logging.info("Daily forecast SMS sent.")
    except Exception as e:
        logging.error(f"daily_forecast failed: {e}")
        raise


if __name__ == "__main__":
    daily_forecast()
