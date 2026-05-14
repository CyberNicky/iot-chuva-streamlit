from time import sleep
import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
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
if message_buffer:
    for d in list(message_buffer):
        st.session_state.data.append({
            "Data/Hora": d["timestamp"],
            "Local": d["local"],
            "Temperatura (°C)": d["temp"],
            "Umidade (%)": d["umidade"],
            "Pressão (hPa)": d["pressao"],
            "Chuva (mm)": d["chuva"],
            "Vento (km/h)": d["vento"],
            "Dia da semana": d["dia_semana"],
            "Dados brutos": d["raw"],
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
    cols2[0].metric("📍 Local", latest["Local"])
    cols2[1].metric("🕒 Última leitura", latest["Data/Hora"].strftime("%d/%m %H:%M"))
    cols2[2].metric("📅 Dia", latest["Dia da semana"])
    cols2[3].metric("📊 Pressão", f"{latest['Pressão (hPa)']:.1f} hPa")
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
st.rerun()