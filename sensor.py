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

INTERVALO_API = 60  # 🔥 1 minuto (evita bloqueio)
INTERVALO_ENVIO = 10  # envia pro MQTT mais rápido

ultimo_dado = None
ultimo_request = 0

# 📍 Bairros
BAIRROS_COORDS = {
    "Ponta Verde": (-9.659, -35.700),
    "Pajuçara": (-9.665, -35.715),
    "Jatiúca": (-9.655, -35.705),
    "Farol": (-9.655, -35.735),
    "Benedito Bentes": (-9.590, -35.750),
    "Centro": (-9.6658, -35.7353),
    
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
    global ultimo_dado, ultimo_request

    agora = time.time()

    # 🔥 usa cache se ainda não deu tempo
    if ultimo_dado and (agora - ultimo_request < INTERVALO_API):
        print("♻️ Usando cache da API")
        return ultimo_dado

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

        dado = {
            "temperatura": float(hourly["temperature_2m"][idx]),
            "umidade": float(hourly["relativehumidity_2m"][idx]),
            "pressao": float(hourly["pressure_msl"][idx]),
            "vento_velocidade": float(hourly["windspeed_10m"][idx]),
            "chuva": float(hourly["precipitation"][idx]),
            "local": bairro,
            "dia_semana": datetime.now().strftime("%A"),
            "hora": datetime.now().hour
        }

        print("🌤️ API OK")

        ultimo_dado = dado
        ultimo_request = agora

        return dado

    except Exception as e:
        print("❌ API falhou:", e)

        # fallback simples
        if ultimo_dado:
            print("♻️ Usando último dado válido")
            return ultimo_dado

        return {
            "temperatura": random.uniform(20, 35),
            "umidade": random.randint(50, 100),
            "pressao": random.uniform(1000, 1020),
            "vento_velocidade": random.uniform(0, 20),
            "chuva": random.uniform(0, 100),
            "local": "Simulado",
            "dia_semana": datetime.now().strftime("%A"),
            "hora": datetime.now().hour
        }

# ----------------------------
# LOOP
# ----------------------------
while True:
    dados = obter_dados()

    client.publish(TOPIC, json.dumps(dados))
    print("[SENSOR]", dados)

    time.sleep(INTERVALO_ENVIO)