import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Union
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import requests

from neighborhoods import Bairros, formatar_bairros, carregar_bairros


BROKER_MQTT = os.getenv("MQTT_BROKER", "mosquitto")
PORTA_MQTT = int(os.getenv("MQTT_PORT", "1883"))
TOPICO_MQTT = os.getenv("MQTT_TOPIC", "iot/chuva")
RETER_MQTT = os.getenv("MQTT_RETAIN", "true").lower() == "true"
FUSO_HORARIO_APP = os.getenv("APP_TIMEZONE", "America/Maceio")
FUSO_APP = ZoneInfo(FUSO_HORARIO_APP)

URL_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
FUSO_HORARIO_OPEN_METEO = FUSO_HORARIO_APP
SEGUNDOS_TIMEOUT_OPEN_METEO = int(os.getenv("OPEN_METEO_TIMEOUT_SECONDS", "5"))
SEGUNDOS_INTERVALO_PUBLICACAO = int(os.getenv("PUBLISH_INTERVAL_SECONDS", "60"))
SEGUNDOS_INTERVALO_PUBLICACAO_INICIAL = int(os.getenv("INITIAL_PUBLISH_INTERVAL_SECONDS", "0"))
MAXIMO_TENTATIVAS_MQTT = 10
SEGUNDOS_ESPERA_TENTATIVA_MQTT = 2
MAXIMO_TENTATIVAS_BAIRROS = 10
SEGUNDOS_ESPERA_TENTATIVA_BAIRROS = 5

PacoteClima = Dict[str, Union[float, int, str]]
CAMPOS_HORARIOS_OPEN_METEO = ",".join(
    [
        "temperature_2m",
        "relativehumidity_2m",
        "pressure_msl",
        "precipitation",
        "windspeed_10m",
    ]
)

DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}

def conectar_mqtt() -> mqtt.Client:
    cliente = mqtt.Client()

    for tentativa in range(1, MAXIMO_TENTATIVAS_MQTT + 1):
        try:
            print(f"Conectando ao MQTT ({tentativa}/{MAXIMO_TENTATIVAS_MQTT})...")
            cliente.connect(BROKER_MQTT, PORTA_MQTT)
            print("MQTT conectado.")
            return cliente
        except Exception as erro:
            print(f"Falha ao conectar no MQTT: {erro}")
            time.sleep(SEGUNDOS_ESPERA_TENTATIVA_MQTT)

    raise RuntimeError("Não foi possível conectar ao broker MQTT.")


def carregar_bairros_dinamicos() -> Bairros:
    for tentativa in range(1, MAXIMO_TENTATIVAS_BAIRROS + 1):
        try:
            print(f"Buscando bairros dinamicamente ({tentativa}/{MAXIMO_TENTATIVAS_BAIRROS})...")
            bairros = carregar_bairros()
            if not bairros:
                raise RuntimeError("A consulta não retornou bairros.")

            print(f"{len(bairros)} bairros disponíveis para monitoramento:")
            for bairro in formatar_bairros(bairros):
                print(f"- {bairro}")
            return bairros
        except requests.RequestException as erro:
            print(f"Falha ao buscar bairros no OpenStreetMap/Overpass: {erro}")
        except RuntimeError as erro:
            print(f"Falha ao carregar bairros: {erro}")

        time.sleep(SEGUNDOS_ESPERA_TENTATIVA_BAIRROS)

    raise RuntimeError("Não foi possível carregar bairros dinamicamente.")


def montar_parametros_open_meteo(latitude: float, longitude: float) -> Dict[str, Union[str, float, bool]]:
    return {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": CAMPOS_HORARIOS_OPEN_METEO,
        "timezone": FUSO_HORARIO_OPEN_METEO,
    }


def encontrar_indice_hora_atual(dados_horarios: Dict[str, list], hora_atual: Optional[str]) -> int:
    if not hora_atual:
        return 0

    hora_corrente = hora_atual[:13]
    for indice, marcador_tempo in enumerate(dados_horarios.get("time", [])):
        if marcador_tempo.startswith(hora_corrente):
            return indice

    return 0


def somar_precipitacao(dados_horarios: Dict[str, list], indice_inicial: int, horas: int) -> float:
    precipitacao = dados_horarios.get("precipitation", [])
    valores = precipitacao[indice_inicial + 1 : indice_inicial + 1 + horas]
    return round(sum(float(valor) for valor in valores), 2)


def buscar_clima(bairro: str, latitude: float, longitude: float) -> Optional[PacoteClima]:
    try:
        resposta = requests.get(
            URL_OPEN_METEO,
            params=montar_parametros_open_meteo(latitude, longitude),
            timeout=SEGUNDOS_TIMEOUT_OPEN_METEO,
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.RequestException as erro:
        print(f"Falha ao consultar Open-Meteo: {erro}")
        return None

    clima_atual = dados.get("current_weather", {})
    dados_horarios = dados.get("hourly", {})
    indice = encontrar_indice_hora_atual(dados_horarios, clima_atual.get("time"))
    agora = datetime.now(FUSO_APP)

    try:
        return {
            "temperatura": float(dados_horarios["temperature_2m"][indice]),
            "umidade": float(dados_horarios["relativehumidity_2m"][indice]),
            "pressao": float(dados_horarios["pressure_msl"][indice]),
            "vento_velocidade": float(dados_horarios["windspeed_10m"][indice]),
            "chuva": float(dados_horarios["precipitation"][indice]),
            "previsao_chuva_1h": somar_precipitacao(dados_horarios, indice, 1),
            "previsao_chuva_3h": somar_precipitacao(dados_horarios, indice, 3),
            "previsao_chuva_6h": somar_precipitacao(dados_horarios, indice, 6),
            "local": bairro,
            "latitude": latitude,
            "longitude": longitude,
            "fonte_localizacao": "OpenStreetMap/Overpass",
            "fonte_clima": "Open-Meteo",
            "dia_semana": DIAS_SEMANA_PT[agora.weekday()],
            "hora": agora.hour,
            "timestamp": agora.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (KeyError, IndexError, TypeError, ValueError) as erro:
        print(f"Resposta inesperada da Open-Meteo: {erro}")
        return None


def publicar_clima(cliente: mqtt.Client, pacote: PacoteClima) -> bool:
    mensagem = json.dumps(pacote)
    resultado = cliente.publish(TOPICO_MQTT, mensagem, retain=RETER_MQTT)
    if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Falha ao publicar no MQTT. Código: {resultado.rc}")
        return False

    print(f"[SENSOR] {mensagem}")
    return True


def executar() -> None:
    bairros = carregar_bairros_dinamicos()
    cliente = conectar_mqtt()
    intervalo_publicacao = SEGUNDOS_INTERVALO_PUBLICACAO_INICIAL

    while True:
        for bairro, (latitude, longitude) in bairros.items():
            clima = buscar_clima(bairro, latitude, longitude)
            if clima:
                publicar_clima(cliente, clima)

            if intervalo_publicacao > 0:
                time.sleep(intervalo_publicacao)

        intervalo_publicacao = SEGUNDOS_INTERVALO_PUBLICACAO


if __name__ == "__main__":
    executar()
