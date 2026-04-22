import paho.mqtt.client as mqtt
import time
import json
import requests
import random
from datetime import datetime
import os

# ----------------------------
# CONFIGURAÇÃO
# ----------------------------
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC = "iot/chuva"

URL_APAC = "http://dados.apac.pe.gov.br:41120/cemaden/last"

# bairros simulados (dashboard)
LOCAIS = [
    "Boa Viagem",
    "Casa Amarela",
    "Várzea",
    "Ibura",
    "Afogados",
    "Centro"
]

# ----------------------------
# CONEXÃO MQTT
# ----------------------------
client = mqtt.Client()
client.connect(BROKER, PORT)

# ----------------------------
# FUNÇÃO PARA PEGAR DADOS REAIS
# ----------------------------
def obter_dados_reais():
    try:
        resposta = requests.get(URL_APAC, timeout=5)

        if resposta.status_code != 200 or not resposta.text.strip():
            raise Exception("Resposta vazia da API")

        dados_api = resposta.json()

        if not isinstance(dados_api, list) or len(dados_api) == 0:
            raise Exception("Formato inválido")

        estacao = random.choice(dados_api)

        chuva = estacao.get("chuva", 0)
        umidade = random.randint(60, 100)
        local = random.choice(LOCAIS)

        dia = datetime.now().strftime("%A")  # 👈 AQUI

        print("✔️ Dados reais da APAC")

        return {
            "chuva": chuva,
            "umidade": umidade,
            "local": local,
            "dia_semana": dia   # 👈 AQUI
        }

    except Exception as e:
        print("⚠️ APAC falhou, usando simulação:", e)

        dia = datetime.now().strftime("%A")  # 👈 AQUI TAMBÉM

        return {
            "chuva": random.randint(0, 100),
            "umidade": random.randint(50, 100),
            "local": random.choice(LOCAIS),
            "dia_semana": dia   # 👈 AQUI TAMBÉM
        }

# ----------------------------
# LOOP PRINCIPAL
# ----------------------------
while True:
    dados = obter_dados_reais()

    client.publish(TOPIC, json.dumps(dados))
    print(f"[SENSOR APAC] {dados}")

    time.sleep(5)
