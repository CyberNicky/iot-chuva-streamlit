import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Union
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import requests

from neighborhoods import Neighborhoods, format_neighborhoods, load_neighborhoods


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
MAX_NEIGHBORHOOD_RETRIES = 10
NEIGHBORHOOD_RETRY_DELAY_SECONDS = 5

WeatherPayload = Dict[str, Union[float, int, str]]
OPEN_METEO_HOURLY_FIELDS = ",".join(
    [
        "temperature_2m",
        "relativehumidity_2m",
        "pressure_msl",
        "precipitation",
        "windspeed_10m",
    ]
)

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


def load_dynamic_neighborhoods() -> Neighborhoods:
    for attempt in range(1, MAX_NEIGHBORHOOD_RETRIES + 1):
        try:
            print(f"Buscando bairros dinamicamente ({attempt}/{MAX_NEIGHBORHOOD_RETRIES})...")
            neighborhoods = load_neighborhoods()
            if not neighborhoods:
                raise RuntimeError("A consulta não retornou bairros.")

            print(f"{len(neighborhoods)} bairros carregados via OpenStreetMap/Overpass:")
            for neighborhood in format_neighborhoods(neighborhoods):
                print(f"- {neighborhood}")
            return neighborhoods
        except requests.RequestException as error:
            print(f"Falha ao buscar bairros no OpenStreetMap/Overpass: {error}")
        except RuntimeError as error:
            print(f"Falha ao carregar bairros: {error}")

        time.sleep(NEIGHBORHOOD_RETRY_DELAY_SECONDS)

    raise RuntimeError("Não foi possível carregar bairros dinamicamente.")


def build_open_meteo_params(latitude: float, longitude: float) -> Dict[str, Union[str, float, bool]]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": OPEN_METEO_HOURLY_FIELDS,
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


def sum_precipitation(hourly: Dict[str, list], start_index: int, hours: int) -> float:
    precipitation = hourly.get("precipitation", [])
    values = precipitation[start_index + 1 : start_index + 1 + hours]
    return round(sum(float(value) for value in values), 2)


def fetch_weather(neighborhood: str, latitude: float, longitude: float) -> Optional[WeatherPayload]:
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
            "previsao_chuva_1h": sum_precipitation(hourly, index, 1),
            "previsao_chuva_3h": sum_precipitation(hourly, index, 3),
            "previsao_chuva_6h": sum_precipitation(hourly, index, 6),
            "local": neighborhood,
            "latitude": latitude,
            "longitude": longitude,
            "fonte_localizacao": "OpenStreetMap/Overpass",
            "fonte_clima": "Open-Meteo",
            "dia_semana": WEEKDAYS_PT[now.weekday()],
            "hora": now.hour,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (KeyError, IndexError, TypeError, ValueError) as error:
        print(f"Resposta inesperada da Open-Meteo: {error}")
        return None


def publish_weather(client: mqtt.Client, payload: WeatherPayload) -> bool:
    message = json.dumps(payload)
    result = client.publish(MQTT_TOPIC, message, retain=MQTT_RETAIN)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Falha ao publicar no MQTT. Código: {result.rc}")
        return False

    print(f"[SENSOR] {message}")
    return True


def run() -> None:
    neighborhoods = load_dynamic_neighborhoods()
    client = connect_mqtt()

    while True:
        for neighborhood, (latitude, longitude) in neighborhoods.items():
            weather = fetch_weather(neighborhood, latitude, longitude)
            if weather:
                publish_weather(client, weather)

            time.sleep(PUBLISH_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
