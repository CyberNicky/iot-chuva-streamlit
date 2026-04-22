import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
from ia_model import prever
import time
import os

# ----------------------------
# CONFIGURAÇÃO
# ----------------------------
st.set_page_config(layout="wide")
st.title("🌧️ Dashboard Inteligente de Chuva - Recife")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

data = []

# ----------------------------
# MQTT
# ----------------------------
def on_message(client, userdata, msg):
    global data
    
    dados = json.loads(msg.payload.decode())
    
    chuva = dados["chuva"]
    umidade = dados["umidade"]
    local = dados["local"]
    dia = dados.get("dia_semana", "N/A")

    risco = prever(chuva, umidade, local, dia)

    novo = {
        "Local": local,
        "Chuva": chuva,
        "Umidade": umidade,
        "Dia": dia,
        "Risco": risco
    }

    data.append(novo)
    print("Recebi MQTT:", novo)

# Função para conectar ao MQTT com retry
def conectar_mqtt():
    client = mqtt.Client()
    client.on_message = on_message
    
    max_tentativas = 10
    tentativa = 0
    
    while tentativa < max_tentativas:
        try:
            print(f"Tentativa {tentativa + 1}/{max_tentativas} - Conectando ao MQTT {MQTT_BROKER}:{MQTT_PORT}")
            client.connect(MQTT_BROKER, MQTT_PORT)
            client.subscribe("iot/chuva")
            print("✅ Conectado ao MQTT com sucesso!")
            return client
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa + 1}: {e}")
            tentativa += 1
            if tentativa < max_tentativas:
                print("⏳ Aguardando 5 segundos antes de tentar novamente...")
                time.sleep(5)
    
    raise Exception(f"❌ Falhou ao conectar ao MQTT após {max_tentativas} tentativas")

# Conectar ao MQTT
client = conectar_mqtt()
client.loop_start()

# ----------------------------
# DASHBOARD
# ----------------------------
placeholder = st.empty()

while True:
    with placeholder.container():

        if len(data) > 0:
            df = pd.DataFrame(data)

            col1, col2, col3 = st.columns(3)

            # 📊 Métricas rápidas
            with col1:
                st.metric("🌧️ Última Chuva", df.iloc[-1]["Chuva"])
            with col2:
                st.metric("💧 Umidade", f"{df.iloc[-1]['Umidade']}%")
            with col3:
                st.metric("📅 Dia", df.iloc[-1]["Dia"])

            # 📊 Tabela
            st.subheader("📊 Dados em Tempo Real")
            st.dataframe(df.tail(10))

            # 📈 Gráfico
            st.subheader("📈 Gráfico de Chuva")
            st.line_chart(df["Chuva"])

            # 🗺️ Situação por região
            st.subheader("🗺️ Situação por Região")

            for loc in df["Local"].unique():
                ultimo = df[df["Local"] == loc].iloc[-1]

                if ultimo["Risco"] == "ALTO":
                    st.error(f"📍 {loc} → Risco ALTO 🚨")
                elif ultimo["Risco"] == "MÉDIO":
                    st.warning(f"📍 {loc} → Risco MÉDIO ⚠️")
                else:
                    st.success(f"📍 {loc} → Risco BAIXO ✅")

            # 🚨 ALERTA GERAL
            if df["Risco"].value_counts().get("ALTO", 0) >= 3:
                st.error("🚨 ALERTA GERAL: Múltiplas regiões com risco alto!")

            # 📌 Região mais crítica
            st.subheader("📌 Região mais crítica")

            critico = df[df["Risco"] == "ALTO"]

            if not critico.empty:
                regiao = critico.iloc[-1]["Local"]
                st.error(f"🚨 Maior risco atual em: {regiao}")
            else:
                st.success("Sem regiões com risco alto no momento ✅")

            # 🏆 Ranking
            st.subheader("🏆 Ranking de risco")

            ranking = df.groupby("Local")["Risco"].apply(lambda x: (x == "ALTO").sum())
            st.bar_chart(ranking)

            # 📈 Tendência
            st.subheader("📈 Tendência de Chuva")

            if len(df) > 5:
                tendencia = df["Chuva"].tail(5).mean()

                if tendencia > 60:
                    st.warning("📈 Tendência de aumento de chuva!")
                else:
                    st.success("📉 Tendência estável")

        else:
            st.write("Aguardando dados do sensor...")

    time.sleep(1)
