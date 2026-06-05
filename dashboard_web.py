from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from time import sleep
from typing import Any, Deque, Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st


MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot/chuva")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Maceio")
APP_TZ = ZoneInfo(APP_TIMEZONE)
MAX_HISTORY_ROWS = 500
RECENT_HISTORY_ROWS = 24
AUTO_REFRESH_SECONDS = 2
MQTT_RETRIES = 10
MQTT_RETRY_DELAY_SECONDS = 2
TABLE_COLUMNS = [
    "Data/Hora",
    "Local",
    "Temperatura (°C)",
    "Umidade (%)",
    "Pressão (hPa)",
    "Chuva (mm)",
    "Vento (km/h)",
    "Dia da semana",
]

DATA_COLUMNS = {
    "timestamp": "Data/Hora",
    "local": "Local",
    "temp": "Temperatura (°C)",
    "umidade": "Umidade (%)",
    "pressao": "Pressão (hPa)",
    "chuva": "Chuva (mm)",
    "vento": "Vento (km/h)",
    "dia_semana": "Dia da semana",
    "raw": "Dados brutos",
}

WEEKDAYS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


@dataclass
class MqttRuntime:
    client: mqtt.Client
    history: Deque[Dict[str, Any]]
    lock: Lock


def configure_page() -> None:
    st.set_page_config(page_title="Dashboard Inteligente de Chuva", page_icon="🌧️", layout="wide")
    st.title("🌧️ Dashboard Inteligente de Chuva - Maceió/AL")
    st.markdown(
        "Acompanhe leituras em tempo real do sensor MQTT com indicadores de clima, "
        "histórico recente e tendências por bairro."
    )


def parse_float(data: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(data.get(key, default))
    except (TypeError, ValueError):
        return default


def parse_message(payload: bytes) -> Dict[str, Any]:
    data = json.loads(payload.decode())
    now = datetime.now(APP_TZ)

    return {
        "local": data.get("local", "Não informado"),
        "chuva": parse_float(data, "chuva", 0.0),
        "umidade": parse_float(data, "umidade", 0.0),
        "temp": parse_float(data, "temperatura", 25.0),
        "pressao": parse_float(data, "pressao", 1013.0),
        "vento": parse_float(data, "vento_velocidade", 0.0),
        "hora": int(data.get("hora", now.hour)),
        "dia_semana": data.get("dia_semana", WEEKDAYS_PT[now.weekday()]),
        "timestamp": data.get("timestamp") or now.strftime("%Y-%m-%d %H:%M:%S"),
        "raw": data,
    }


def on_message(client: mqtt.Client, runtime: MqttRuntime, message: mqtt.MQTTMessage) -> None:
    try:
        parsed_message = parse_message(message.payload)
        with runtime.lock:
            runtime.history.append(parsed_message)
        print(f"Mensagem MQTT recebida: {parsed_message}")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as error:
        print(f"Erro ao processar mensagem MQTT: {error}")


@st.cache_resource
def get_mqtt_runtime() -> MqttRuntime:
    client = mqtt.Client()
    runtime = MqttRuntime(
        client=client,
        history=deque(maxlen=MAX_HISTORY_ROWS),
        lock=Lock(),
    )
    client.user_data_set(runtime)
    client.on_message = on_message

    for attempt in range(1, MQTT_RETRIES + 1):
        try:
            print(f"Conectando ao MQTT ({attempt}/{MQTT_RETRIES})...")
            client.connect(MQTT_BROKER, MQTT_PORT)
            client.subscribe(MQTT_TOPIC)
            client.loop_start()
            print("MQTT conectado.")
            return runtime
        except Exception as error:
            print(f"Falha ao conectar no MQTT: {error}")
            sleep(MQTT_RETRY_DELAY_SECONDS)

    raise RuntimeError("Não foi possível conectar ao broker MQTT.")


def get_history_rows(runtime: MqttRuntime) -> List[Dict[str, Any]]:
    with runtime.lock:
        messages = list(runtime.history)

    return [
        {column: message[key] for key, column in DATA_COLUMNS.items()}
        for message in messages
    ]


def build_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows)
    dataframe["Data/Hora"] = pd.to_datetime(dataframe["Data/Hora"], errors="coerce")
    return dataframe.dropna(subset=["Data/Hora"]).sort_values("Data/Hora")


def render_summary(latest: pd.Series) -> None:
    st.subheader("📍 Resumo atual")
    st.caption(
        f"Última atualização em {latest['Data/Hora'].strftime('%d/%m/%Y às %H:%M:%S')} "
        f"• próximo refresh da tela em {AUTO_REFRESH_SECONDS}s"
    )

    metrics = [
        ("🌡️ Temperatura", f"{latest['Temperatura (°C)']:.1f} °C"),
        ("💧 Umidade", f"{latest['Umidade (%)']:.0f}%"),
        ("🌧️ Precipitação", f"{latest['Chuva (mm)']:.2f} mm"),
        ("💨 Vento", f"{latest['Vento (km/h)']:.1f} km/h"),
    ]
    for column, (label, value) in zip(st.columns(4), metrics):
        column.metric(label, value)

    details = [
        ("🏙️ Local", latest["Local"]),
        ("🕒 Última leitura", latest["Data/Hora"].strftime("%d/%m %H:%M")),
        ("📅 Dia", latest["Dia da semana"]),
        ("📊 Pressão", f"{latest['Pressão (hPa)']:.1f} hPa"),
    ]
    for column, (label, value) in zip(st.columns(4), details):
        column.metric(label, value)


def render_charts(dataframe: pd.DataFrame) -> None:
    history = dataframe.tail(RECENT_HISTORY_ROWS).set_index("Data/Hora")

    st.markdown("---")
    st.subheader("📈 Tendências recentes")
    left, right = st.columns(2)

    with left:
        st.markdown("**🌡️ Temperatura e 💧 Umidade**")
        st.line_chart(history[["Temperatura (°C)", "Umidade (%)"]])

    with right:
        st.markdown("**🌧️ Precipitação e 💨 Vento**")
        st.line_chart(history[["Chuva (mm)", "Vento (km/h)"]])


def render_history(dataframe: pd.DataFrame, latest: pd.Series) -> None:
    st.markdown("---")
    st.subheader("🧾 Histórico recente")
    table = dataframe.tail(20).reset_index(drop=True)
    st.dataframe(table[TABLE_COLUMNS], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📦 Último pacote MQTT recebido")
    with st.expander("Ver JSON completo"):
        st.json(latest["Dados brutos"])


def render_dashboard(runtime: MqttRuntime) -> None:
    rows = get_history_rows(runtime)
    if not rows:
        st.warning("⏳ Nenhum dado ainda chegando. Aguarde o primeiro pacote MQTT do sensor.")
        return

    dataframe = build_dataframe(rows)
    if dataframe.empty:
        st.warning("⚠️ Dados recebidos, mas sem timestamp válido para exibição.")
        return

    latest = dataframe.iloc[-1]
    render_summary(latest)
    render_charts(dataframe)
    render_history(dataframe, latest)


def main() -> None:
    configure_page()
    mqtt_runtime = get_mqtt_runtime()
    render_dashboard(mqtt_runtime)

    sleep(AUTO_REFRESH_SECONDS)
    st.rerun()


main()
