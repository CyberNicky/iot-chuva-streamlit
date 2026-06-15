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
ALERT_RAIN_MM = 3
ALERT_WIND_KMH = 45
ATTENTION_HUMIDITY = 80
RAIN_NOW_COLUMN = "Chuva agora (mm)"
FORECAST_1H_COLUMN = "Chuva prevista 1h (mm)"
FORECAST_3H_COLUMN = "Chuva prevista 3h (mm)"
FORECAST_6H_COLUMN = "Chuva prevista 6h (mm)"
RAIN_INTERPRETATION_COLUMN = "Interpretação da chuva"
TABLE_COLUMNS = [
    "Data/Hora",
    "Local",
    RAIN_INTERPRETATION_COLUMN,
    "Temperatura (°C)",
    "Umidade (%)",
    "Pressão (hPa)",
    RAIN_NOW_COLUMN,
    FORECAST_1H_COLUMN,
    FORECAST_3H_COLUMN,
    FORECAST_6H_COLUMN,
    "Vento (km/h)",
    "Dia da semana",
]
LATEST_BY_NEIGHBORHOOD_COLUMNS = [
    "Local",
    "Status",
    RAIN_INTERPRETATION_COLUMN,
    "Data/Hora",
    "Temperatura (°C)",
    "Umidade (%)",
    "Pressão (hPa)",
    RAIN_NOW_COLUMN,
    FORECAST_1H_COLUMN,
    FORECAST_3H_COLUMN,
    FORECAST_6H_COLUMN,
    "Vento (km/h)",
]
ALL_NEIGHBORHOODS_OPTION = "Todos os bairros"

DATA_COLUMNS = {
    "timestamp": "Data/Hora",
    "local": "Local",
    "temp": "Temperatura (°C)",
    "umidade": "Umidade (%)",
    "pressao": "Pressão (hPa)",
    "chuva": RAIN_NOW_COLUMN,
    "previsao_chuva_1h": FORECAST_1H_COLUMN,
    "previsao_chuva_3h": FORECAST_3H_COLUMN,
    "previsao_chuva_6h": FORECAST_6H_COLUMN,
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
        "previsao_chuva_1h": parse_float(data, "previsao_chuva_1h", 0.0),
        "previsao_chuva_3h": parse_float(data, "previsao_chuva_3h", 0.0),
        "previsao_chuva_6h": parse_float(data, "previsao_chuva_6h", 0.0),
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
    dataframe = dataframe.dropna(subset=["Data/Hora"]).sort_values("Data/Hora")
    dataframe[RAIN_INTERPRETATION_COLUMN] = dataframe.apply(describe_rain_condition, axis=1)
    return dataframe


def classify_status(rain: float, wind: float, humidity: float) -> str:
    if rain >= ALERT_RAIN_MM or wind >= ALERT_WIND_KMH:
        return "Alerta"

    if rain > 0 or humidity >= ATTENTION_HUMIDITY:
        return "Atenção"

    return "Normal"


def describe_rain_condition(row: pd.Series) -> str:
    rain_now = float(row[RAIN_NOW_COLUMN])
    forecast_1h = float(row[FORECAST_1H_COLUMN])
    forecast_3h = float(row[FORECAST_3H_COLUMN])

    if rain_now >= ALERT_RAIN_MM:
        return "Chovendo forte agora"

    if rain_now >= 1:
        return "Chovendo agora"

    if rain_now > 0:
        return "Chuva fraca agora"

    if forecast_1h >= ALERT_RAIN_MM:
        return "Chuva forte prevista em 1h"

    if forecast_1h > 0:
        return "Pode chover em breve"

    if forecast_3h > 0:
        return "Pode chover nas próximas 3h"

    return "Sem chuva prevista"


def classify_latest_row(row: pd.Series) -> str:
    rain = max(float(row[RAIN_NOW_COLUMN]), float(row[FORECAST_1H_COLUMN]))
    wind = float(row["Vento (km/h)"])
    humidity = float(row["Umidade (%)"])
    return classify_status(rain, wind, humidity)


def build_latest_by_neighborhood(dataframe: pd.DataFrame) -> pd.DataFrame:
    latest_by_neighborhood = (
        dataframe.sort_values("Data/Hora")
        .drop_duplicates(subset=["Local"], keep="last")
        .sort_values("Local")
        .reset_index(drop=True)
    )
    latest_by_neighborhood["Status"] = latest_by_neighborhood.apply(classify_latest_row, axis=1)
    return latest_by_neighborhood


def render_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    received_neighborhoods = set(dataframe["Local"])
    options = [ALL_NEIGHBORHOODS_OPTION] + sorted(received_neighborhoods)

    selected_neighborhood = st.selectbox(
        "🏙️ Filtrar por bairro",
        options,
        index=0,
        help="Escolha um bairro para ver métricas, gráficos e histórico apenas dele.",
    )

    if selected_neighborhood == ALL_NEIGHBORHOODS_OPTION:
        st.caption(f"Exibindo todos os bairros com dados recebidos ({len(received_neighborhoods)} bairros).")
        return dataframe

    filtered = dataframe[dataframe["Local"] == selected_neighborhood]
    st.caption(f"Exibindo somente leituras de {selected_neighborhood}.")
    return filtered


def classify_conditions(latest: pd.Series, recent: pd.DataFrame) -> Dict[str, str]:
    rain_sum = float(recent[RAIN_NOW_COLUMN].sum())
    forecast_1h = float(latest[FORECAST_1H_COLUMN])
    max_wind = float(recent["Vento (km/h)"].max())
    humidity = float(latest["Umidade (%)"])
    status = classify_status(max(rain_sum, forecast_1h), max_wind, humidity)

    if status == "Alerta":
        return {
            "status": "Alerta",
            "icon": "🚨",
            "message": "Acompanhe os próximos registros com atenção.",
        }

    if status == "Atenção":
        return {
            "status": "Atenção",
            "icon": "⚠️",
            "message": "Há sinal de chuva, previsão de chuva próxima ou umidade elevada.",
        }

    return {
        "status": "Normal",
        "icon": "✅",
        "message": "Sem sinal relevante de chuva no momento.",
    }


def get_attention_neighborhood(recent: pd.DataFrame) -> str:
    grouped = (
        recent.groupby("Local", as_index=False)
        .agg({RAIN_NOW_COLUMN: "sum", "Vento (km/h)": "max"})
        .sort_values([RAIN_NOW_COLUMN, "Vento (km/h)"], ascending=False)
    )
    neighborhood = grouped.iloc[0]
    return f"{neighborhood['Local']} ({neighborhood[RAIN_NOW_COLUMN]:.2f} mm)"


def get_windiest_neighborhood(recent: pd.DataFrame) -> str:
    grouped = (
        recent.groupby("Local", as_index=False)["Vento (km/h)"]
        .max()
        .sort_values("Vento (km/h)", ascending=False)
    )
    neighborhood = grouped.iloc[0]
    return f"{neighborhood['Local']} ({neighborhood['Vento (km/h)']:.1f} km/h)"


def render_conditions(dataframe: pd.DataFrame, latest: pd.Series) -> None:
    recent = dataframe.tail(RECENT_HISTORY_ROWS)
    conditions = classify_conditions(latest, recent)

    st.markdown("---")
    st.subheader("🧭 Situação atual")

    columns = st.columns(4)
    columns[0].metric(
        f"{conditions['icon']} Status",
        conditions["status"],
    )
    columns[1].metric("🌧️ Chuva recente", f"{recent[RAIN_NOW_COLUMN].sum():.2f} mm")
    columns[2].metric("🏙️ Bairro em atenção", get_attention_neighborhood(recent))
    columns[3].metric("💨 Maior vento", get_windiest_neighborhood(recent))

    st.info(conditions["message"])


def render_summary(latest: pd.Series) -> None:
    st.subheader("📍 Resumo atual")
    st.caption(
        f"Última atualização em {latest['Data/Hora'].strftime('%d/%m/%Y às %H:%M:%S')} "
        f"• próximo refresh da tela em {AUTO_REFRESH_SECONDS}s"
    )

    metrics = [
        ("🌡️ Temperatura", f"{latest['Temperatura (°C)']:.1f} °C"),
        ("💧 Umidade", f"{latest['Umidade (%)']:.0f}%"),
        ("🌧️ Chuva agora", f"{latest[RAIN_NOW_COLUMN]:.2f} mm"),
        ("☔ Chuva prev. 3h", f"{latest[FORECAST_3H_COLUMN]:.2f} mm"),
        ("💨 Vento", f"{latest['Vento (km/h)']:.1f} km/h"),
    ]
    for column, (label, value) in zip(st.columns(5), metrics):
        column.metric(label, value)

    details = [
        ("🏙️ Local", latest["Local"]),
        ("🕒 Última leitura", latest["Data/Hora"].strftime("%d/%m %H:%M")),
        ("📅 Dia", latest["Dia da semana"]),
        ("📊 Pressão", f"{latest['Pressão (hPa)']:.1f} hPa"),
    ]
    for column, (label, value) in zip(st.columns(4), details):
        column.metric(label, value)

    st.info(f"🌧️ {latest[RAIN_INTERPRETATION_COLUMN]}")


def render_latest_by_neighborhood(dataframe: pd.DataFrame) -> None:
    latest_by_neighborhood = build_latest_by_neighborhood(dataframe)

    st.markdown("---")
    st.subheader("🏙️ Última leitura por bairro")
    st.caption(
        "Use esta tabela para consultar rapidamente a condição mais recente disponível. "
        "Valores em mm representam milímetros de chuva acumulada; quanto maior o número, "
        "maior o volume de chuva."
    )
    st.dataframe(
        latest_by_neighborhood[LATEST_BY_NEIGHBORHOOD_COLUMNS],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Resumo da condição calculada a partir de chuva, previsão, umidade e vento.",
            ),
            RAIN_INTERPRETATION_COLUMN: st.column_config.TextColumn(
                RAIN_INTERPRETATION_COLUMN,
                help="Explicação simples dos valores de chuva para facilitar a leitura.",
            ),
            RAIN_NOW_COLUMN: st.column_config.NumberColumn(
                RAIN_NOW_COLUMN,
                help="Chuva registrada na hora atual para o bairro, em milímetros.",
                format="%.2f",
            ),
            FORECAST_1H_COLUMN: st.column_config.NumberColumn(
                FORECAST_1H_COLUMN,
                help="Chuva acumulada prevista para a próxima 1 hora, em milímetros.",
                format="%.2f",
            ),
            FORECAST_3H_COLUMN: st.column_config.NumberColumn(
                FORECAST_3H_COLUMN,
                help="Chuva acumulada prevista para as próximas 3 horas, em milímetros.",
                format="%.2f",
            ),
            FORECAST_6H_COLUMN: st.column_config.NumberColumn(
                FORECAST_6H_COLUMN,
                help="Chuva acumulada prevista para as próximas 6 horas, em milímetros.",
                format="%.2f",
            ),
            "Vento (km/h)": st.column_config.NumberColumn(
                "Vento (km/h)",
                help="Velocidade do vento em quilômetros por hora.",
                format="%.1f",
            ),
        },
    )


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
        st.line_chart(history[[RAIN_NOW_COLUMN, FORECAST_3H_COLUMN, "Vento (km/h)"]])


def render_history(dataframe: pd.DataFrame, latest: pd.Series) -> None:
    st.markdown("---")
    st.subheader("🧾 Histórico recente")
    table = dataframe.tail(20).reset_index(drop=True)
    st.dataframe(
        table[TABLE_COLUMNS],
        use_container_width=True,
        hide_index=True,
        column_config={
            RAIN_INTERPRETATION_COLUMN: st.column_config.TextColumn(
                RAIN_INTERPRETATION_COLUMN,
                help="Explicação simples dos valores de chuva para facilitar a leitura.",
            ),
            RAIN_NOW_COLUMN: st.column_config.NumberColumn(
                RAIN_NOW_COLUMN,
                help="Chuva registrada na hora atual para o bairro, em milímetros.",
                format="%.2f",
            ),
            FORECAST_1H_COLUMN: st.column_config.NumberColumn(
                FORECAST_1H_COLUMN,
                help="Chuva acumulada prevista para a próxima 1 hora, em milímetros.",
                format="%.2f",
            ),
            FORECAST_3H_COLUMN: st.column_config.NumberColumn(
                FORECAST_3H_COLUMN,
                help="Chuva acumulada prevista para as próximas 3 horas, em milímetros.",
                format="%.2f",
            ),
            FORECAST_6H_COLUMN: st.column_config.NumberColumn(
                FORECAST_6H_COLUMN,
                help="Chuva acumulada prevista para as próximas 6 horas, em milímetros.",
                format="%.2f",
            ),
        },
    )

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

    render_latest_by_neighborhood(dataframe)

    dataframe = render_filters(dataframe)
    if dataframe.empty:
        st.info("Ainda não há leituras para o bairro selecionado.")
        return

    latest = dataframe.iloc[-1]
    render_summary(latest)
    render_conditions(dataframe, latest)
    render_charts(dataframe)
    render_history(dataframe, latest)


def main() -> None:
    configure_page()
    mqtt_runtime = get_mqtt_runtime()
    render_dashboard(mqtt_runtime)

    sleep(AUTO_REFRESH_SECONDS)
    st.rerun()


main()
