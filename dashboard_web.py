from time import sleep
import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Dashboard Inteligente de Chuva", layout="wide")
st.title("🌧️ Dashboard Inteligente de Chuva - Maceió/AL")
st.markdown(
    "Monitore as leituras em tempo real do sensor MQTT com métricas claras, histórico e tendências. "
    "Dados com unidades padrão: temperatura (°C), umidade (%), pressão (hPa), precipitação (mm) e vento (km/h)."
)

MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# 🔥 BUFFER GLOBAL (ESSA É A CHAVE)
@st.cache_resource
def get_message_buffer():
    return []

message_buffer = get_message_buffer()

if "data" not in st.session_state:
    st.session_state.data = []

# ----------------------------
# CALLBACK MQTT
# ----------------------------
def on_message(client, userdata, msg):
    try:
        dados = json.loads(msg.payload.decode())
        print("📩 RECEBIDO:", dados)

        mensagem = {
            "local": dados.get("local"),
            "chuva": float(dados.get("chuva", 0.0)),
            "umidade": float(dados.get("umidade", 0.0)),
            "temp": float(dados.get("temperatura", 25.0)),
            "pressao": float(dados.get("pressao", 1013.0)),
            "vento": float(dados.get("vento_velocidade", 10.0)),
            "hora": int(dados.get("hora", datetime.now().hour)),
            "dia_semana": dados.get("dia_semana", datetime.now().strftime("%A")),
            "timestamp": dados.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "raw": dados,
        }

        message_buffer.append(mensagem)

    except Exception as e:
        print("Erro no callback MQTT:", e)

# ----------------------------
# MODELO DE IA
# ----------------------------

def carregar_modelo():
    try:
        return joblib.load("modelo_chuva.pkl")
    except Exception as e:
        print("⚠️ Não foi possível carregar o modelo:", e)
        return None


def mapear_dia_semana(dia):
    mapa = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }
    return mapa.get(str(dia).strip().capitalize(), 0)


def calcular_features_registro(registro, historico):
    ultima_pressao = historico[-1]["Pressao"] if historico else registro["pressao"]
    ultima_chuva = historico[-1]["Chuva"] if historico else registro["chuva"]
    umidades = [item["Umidade"] for item in historico[-2:]] if historico else []
    umidades.append(registro["umidade"])

    chuva_ultimas_3h = sum([item["Chuva"] for item in historico[-2:]]) + registro["chuva"] if historico else registro["chuva"]
    media_umidade_3h = sum(umidades) / max(1, len(umidades))

    hora = registro["hora"]
    return {
        "temperatura": registro["temp"],
        "umidade": registro["umidade"],
        "pressao": registro["pressao"],
        "vento_velocidade": registro["vento"],
        "hora": hora,
        "dia_semana": mapear_dia_semana(registro["dia_semana"]),
        "delta_pressao": registro["pressao"] - ultima_pressao,
        "media_umidade_3h": media_umidade_3h,
        "chuva_ultimas_3h": chuva_ultimas_3h,
        "hora_sin": np.sin(2 * np.pi * hora / 24),
        "hora_cos": np.cos(2 * np.pi * hora / 24),
        "tendencia_chuva": registro["chuva"] - ultima_chuva,
    }


def prever_probabilidade(registro, historico, modelo):
    if not modelo:
        return 0.0

    features = calcular_features_registro(registro, historico)
    X = pd.DataFrame([features])
    try:
        prob = modelo.predict_proba(X)[0][1] * 100
        return round(prob, 1)
    except Exception as e:
        print("Erro ao prever probabilidade:", e)
        return 0.0

# ----------------------------
# MQTT (UMA VEZ)
# ----------------------------
@st.cache_resource
def conectar():
    client = mqtt.Client()
    client.on_message = on_message

    for i in range(10):
        try:
            print(f"🔄 MQTT tentativa {i+1}")
            client.connect(MQTT_BROKER, MQTT_PORT)
            client.subscribe("iot/chuva")
            client.loop_start()
            print("✅ MQTT conectado")
            return client
        except:
            sleep(2)

    raise Exception("MQTT não conectou")

conectar()

# ----------------------------
# PROCESSAR BUFFER
# ----------------------------
modelo_data = carregar_modelo()
modelo = modelo_data["modelo"] if modelo_data else None

if message_buffer:
    for d in list(message_buffer):
        registro = {
            "local": d["local"],
            "chuva": d["chuva"],
            "umidade": d["umidade"],
            "temp": d["temp"],
            "pressao": d["pressao"],
            "vento": d["vento"],
            "hora": d["hora"],
            "dia_semana": d.get("dia_semana", "Monday"),
            "timestamp": d["timestamp"],
            "raw": d["raw"],
        }
        prob = prever_probabilidade(registro, st.session_state.data, modelo)

        st.session_state.data.append({
            "Data/Hora": registro["timestamp"],
            "Local": registro["local"],
            "Chuva": registro["chuva"],
            "Umidade": registro["umidade"],
            "Pressao": registro["pressao"],
            "Temperatura": registro["temp"],
            "Chuva (mm)": registro["chuva"],
            "Umidade (%)": registro["umidade"],
            "Temperatura (°C)": registro["temp"],
            "Pressão (hPa)": registro["pressao"],
            "Vento (km/h)": registro["vento"],
            "Probabilidade de chuva (%)": prob,
            "Dia da semana": registro["dia_semana"],
            "Dados brutos": registro["raw"],
        })

    if len(st.session_state.data) > 500:
        st.session_state.data = st.session_state.data[-500:]

    message_buffer.clear()

# ----------------------------
# UI
# ----------------------------
if len(st.session_state.data) > 0:
    df = pd.DataFrame(st.session_state.data)
    df["Data/Hora"] = pd.to_datetime(df["Data/Hora"])
    df = df.sort_values("Data/Hora")
    latest = df.iloc[-1]
    history = df.tail(24)

    st.subheader("Resumo atual")
    cols = st.columns(4)
    cols[0].metric("🌡 Temperatura", f"{latest['Temperatura (°C)']:.1f}°C")
    cols[1].metric("💧 Umidade", f"{latest['Umidade (%)']:.0f}%")
    cols[2].metric("🌧 Precipitação", f"{latest['Chuva (mm)']:.2f} mm")
    cols[3].metric("💨 Vento", f"{latest['Vento (km/h)']:.1f} km/h")

    cols2 = st.columns(4)
    cols2[0].metric("📈 Prob. chuva", f"{latest['Probabilidade de chuva (%)']:.1f}%")
    cols2[1].metric("📍 Local", latest["Local"])
    cols2[2].metric("🕒 Última leitura", latest["Data/Hora"].strftime("%d/%m %H:%M"))
    cols2[3].metric("📅 Dia", latest["Dia da semana"])

    st.markdown("---")
    st.subheader("Tendências recentes")
    trend_left, trend_right = st.columns(2)

    with trend_left:
        st.markdown("**Temperatura e Umidade**")
        st.line_chart(history.set_index("Data/Hora")[['Temperatura (°C)', 'Umidade (%)']])

    with trend_right:
        st.markdown("**Precipitação e Vento**")
        st.line_chart(history.set_index("Data/Hora")[['Chuva (mm)', 'Vento (km/h)']])

    st.markdown("---")
    st.subheader("Histórico recente")
    st.dataframe(df.tail(20).reset_index(drop=True), use_container_width=True)

    st.markdown("---")
    st.subheader("Último pacote MQTT recebido")
    with st.expander("Ver JSON completo"):
        st.json(latest["Dados brutos"])

else:
    st.warning("⚠️ Nenhum dado ainda chegando. Aguarde o primeiro pacote MQTT do sensor.")

# ----------------------------
# AUTO REFRESH
# ----------------------------
sleep(2)
st.experimental_rerun()