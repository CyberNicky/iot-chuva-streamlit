import paho.mqtt.client as mqtt
import time
import json
import requests
import random
from datetime import datetime
import os

# ----------------------------
# CONFIG
# ----------------------------
BROKER = os.getenv("MQTT_BROKER", "mosquitto")
PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC = "iot/chuva"

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "America/Sao_Paulo"

INTERVALO_API = 60  # 🔥 agora controla tudo

# 📍 Bairros
BAIRROS_COORDS = {
    "Ponta Verde": (-9.6616, -35.7052),
    "Pajuçara": (-9.6682, -35.7141),
    "Jatiúca": (-9.6545, -35.7040),
    "Farol": (-9.6480, -35.7350),
    "Centro": (-9.6658, -35.7353),
    "Mangabeiras": (-9.6485, -35.6905),
    "Cruz das Almas": (-9.6335, -35.6880),
    "Jacintinho": (-9.6280, -35.7355),
    "Serraria": (-9.5950, -35.7400),
    "Tabuleiro do Martins": (-9.5650, -35.7800),
    "Benedito Bentes": (-9.5900, -35.7500),
    "Gruta de Lourdes": (-9.6200, -35.7300),
    "Feitosa": (-9.6205, -35.7450),
    "Jaraguá": (-9.6685, -35.7350),
    "Poço": (-9.6600, -35.7300),
}

# ----------------------------
# MQTT
# ----------------------------
client = mqtt.Client()

for i in range(10):
    try:
        print(f"🔄 Conectando MQTT {i+1}")
        client.connect(BROKER, PORT)
        print("✅ MQTT conectado")
        break
    except Exception as e:
        print("Erro MQTT:", e)
        time.sleep(2)
else:
    raise Exception("❌ MQTT não conectou")

# ----------------------------
# API
# ----------------------------
def obter_dados():
    try:
        bairro = random.choice(list(BAIRROS_COORDS.keys()))
        lat, lon = BAIRROS_COORDS[bairro]

        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "hourly": "temperature_2m,relativehumidity_2m,pressure_msl,precipitation,windspeed_10m",
            "timezone": TIMEZONE
        }

        r = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        r.raise_for_status()

        dados_api = r.json()
        current = dados_api.get("current_weather", {})
        hourly = dados_api.get("hourly", {})

        idx = 0
        tempos = hourly.get("time", [])

        for i, t in enumerate(tempos):
            if current.get("time") and t.startswith(current["time"][:13]):
                idx = i
                break

        return {
            "temperatura": float(hourly["temperature_2m"][idx]),
            "umidade": float(hourly["relativehumidity_2m"][idx]),
            "pressao": float(hourly["pressure_msl"][idx]),
            "vento_velocidade": float(hourly["windspeed_10m"][idx]),
            "chuva": float(hourly["precipitation"][idx]),
            "local": bairro,
            "dia_semana": datetime.now().strftime("%A"),
            "hora": datetime.now().hour
        }

    except Exception as e:
        print("❌ API falhou:", e)
        return None

# ----------------------------
# LOOP REAL
# ----------------------------
while True:
    dados = obter_dados()

    if dados:
        client.publish(TOPIC, json.dumps(dados))
        print("[SENSOR]", dados)

    time.sleep(INTERVALO_API)  # 🔥 envia só quando atualiza