import json
import os
import random
import time
from datetime import datetime
from typing import Dict, Optional, Union
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import requests

from neighborhoods import NEIGHBORHOODS


MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot/chuva")
MQTT_RETAIN = os.getenv("MQTT_RETAIN", "true").lower() == "true"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Maceio")
APP_TZ = ZoneInfo(APP_TIMEZONE)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEZONE = APP_TIMEZONE
PUBLISH_INTERVAL_SECONDS = int(os.getenv("PUBLISH_INTERVAL_SECONDS", "60"))
MAX_MQTT_RETRIES = 10
MQTT_RETRY_DELAY_SECONDS = 2

WeatherPayload = Dict[str, Union[float, int, str]]

WEEKDAYS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}

def connect_mqtt() -> mqtt.Client:
    client = mqtt.Client()

    for attempt in range(1, MAX_MQTT_RETRIES + 1):
        try:
            print(f"Conectando ao MQTT ({attempt}/{MAX_MQTT_RETRIES})...")
            client.connect(MQTT_BROKER, MQTT_PORT)
            print("MQTT conectado.")
            return client
        except Exception as error:
            print(f"Falha ao conectar no MQTT: {error}")
            time.sleep(MQTT_RETRY_DELAY_SECONDS)

    raise RuntimeError("Não foi possível conectar ao broker MQTT.")


def build_open_meteo_params(latitude: float, longitude: float) -> Dict[str, Union[str, float, bool]]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": "temperature_2m,relativehumidity_2m,pressure_msl,precipitation,windspeed_10m",
        "timezone": OPEN_METEO_TIMEZONE,
    }


def find_current_hour_index(hourly: Dict[str, list], current_time: Optional[str]) -> int:
    if not current_time:
        return 0

    current_hour = current_time[:13]
    for index, timestamp in enumerate(hourly.get("time", [])):
        if timestamp.startswith(current_hour):
            return index

    return 0


def fetch_weather() -> Optional[WeatherPayload]:
    neighborhood = random.choice(list(NEIGHBORHOODS))
    latitude, longitude = NEIGHBORHOODS[neighborhood]

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params=build_open_meteo_params(latitude, longitude),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        print(f"Falha ao consultar Open-Meteo: {error}")
        return None

    current_weather = data.get("current_weather", {})
    hourly = data.get("hourly", {})
    index = find_current_hour_index(hourly, current_weather.get("time"))
    now = datetime.now(APP_TZ)

    try:
        return {
            "temperatura": float(hourly["temperature_2m"][index]),
            "umidade": float(hourly["relativehumidity_2m"][index]),
            "pressao": float(hourly["pressure_msl"][index]),
            "vento_velocidade": float(hourly["windspeed_10m"][index]),
            "chuva": float(hourly["precipitation"][index]),
            "local": neighborhood,
            "dia_semana": WEEKDAYS_PT[now.weekday()],
            "hora": now.hour,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (KeyError, IndexError, TypeError, ValueError) as error:
        print(f"Resposta inesperada da Open-Meteo: {error}")
        return None


def publish_weather(client: mqtt.Client, payload: WeatherPayload) -> None:
    message = json.dumps(payload)
    client.publish(MQTT_TOPIC, message, retain=MQTT_RETAIN)
    print(f"[SENSOR] {message}")


def run() -> None:
    client = connect_mqtt()

    while True:
        weather = fetch_weather()
        if weather:
            publish_weather(client, weather)

        time.sleep(PUBLISH_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
