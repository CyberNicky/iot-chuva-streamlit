from __future__ import annotations

import json
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from html import escape
from threading import Lock
from time import sleep
from typing import Any, Deque, Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st
import streamlit.components.v1 as components


BROKER_MQTT = os.getenv("MQTT_BROKER", "mqtt-broker")
PORTA_MQTT = int(os.getenv("MQTT_PORT", "1883"))
TOPICO_MQTT = os.getenv("MQTT_TOPIC", "iot/chuva")
FUSO_HORARIO_APP = os.getenv("APP_TIMEZONE", "America/Maceio")
FUSO_APP = ZoneInfo(FUSO_HORARIO_APP)
MAXIMO_LINHAS_HISTORICO = 500
LINHAS_HISTORICO_RECENTE = 24
SEGUNDOS_ATUALIZACAO_AUTOMATICA = 2
TENTATIVAS_MQTT = 10
SEGUNDOS_ESPERA_TENTATIVA_MQTT = 2
LIMITE_ALERTA_CHUVA_MM = 3
LIMITE_ALERTA_VENTO_KMH = 45
LIMITE_ATENCAO_UMIDADE = 80
COLUNA_CHUVA_AGORA = "Chuva agora (mm)"
COLUNA_PREVISAO_1H = "Chuva prevista 1h (mm)"
COLUNA_PREVISAO_3H = "Chuva prevista 3h (mm)"
COLUNA_PREVISAO_6H = "Chuva prevista 6h (mm)"
COLUNA_INTERPRETACAO_CHUVA = "Interpretação da chuva"
COLUNAS_TABELA = [
    "Data/Hora",
    "Local",
    COLUNA_INTERPRETACAO_CHUVA,
    "Temperatura (°C)",
    "Umidade (%)",
    "Pressão (hPa)",
    COLUNA_CHUVA_AGORA,
    COLUNA_PREVISAO_1H,
    COLUNA_PREVISAO_3H,
    COLUNA_PREVISAO_6H,
    "Vento (km/h)",
    "Dia da semana",
]
COLUNAS_ULTIMAS_POR_BAIRRO = [
    "Local",
    "Status",
    COLUNA_INTERPRETACAO_CHUVA,
    "Data/Hora",
    "Temperatura (°C)",
    "Umidade (%)",
    "Pressão (hPa)",
    COLUNA_CHUVA_AGORA,
    COLUNA_PREVISAO_1H,
    COLUNA_PREVISAO_3H,
    COLUNA_PREVISAO_6H,
    "Vento (km/h)",
]
OPCAO_TODOS_BAIRROS = "Todos os bairros"

COLUNAS_DADOS = {
    "timestamp": "Data/Hora",
    "local": "Local",
    "temp": "Temperatura (°C)",
    "umidade": "Umidade (%)",
    "pressao": "Pressão (hPa)",
    "chuva": COLUNA_CHUVA_AGORA,
    "previsao_chuva_1h": COLUNA_PREVISAO_1H,
    "previsao_chuva_3h": COLUNA_PREVISAO_3H,
    "previsao_chuva_6h": COLUNA_PREVISAO_6H,
    "vento": "Vento (km/h)",
    "dia_semana": "Dia da semana",
    "raw": "Dados brutos",
}

DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


@dataclass
class RuntimeMqtt:
    cliente: mqtt.Client
    historico: Deque[Dict[str, Any]]
    trava: Lock


def configurar_pagina() -> None:
    st.set_page_config(page_title="Monitor de Chuva - Maceió", page_icon="🌧️", layout="wide")
    st.markdown(
        """
        <style>
            :root {
                --app-bg: #0f0b2d;
                --app-panel: #252852;
                --app-panel-strong: #322643;
                --app-panel-soft: #1e2148;
                --app-ink: #f7f7ff;
                --app-muted: #c8cce4;
                --app-dim: #969cc1;
                --app-border: rgba(255, 255, 255, 0.105);
                --app-primary: #48c7ff;
                --app-primary-soft: rgba(72, 199, 255, 0.16);
                --app-success: #58db6b;
                --app-warning: #f2c94c;
                --app-danger: #ff6b75;
                --app-rain: #48c7ff;
                --app-wind: #72e0a5;
            }

            .stApp {
                background:
                    radial-gradient(circle at 18% 0%, rgba(72, 199, 255, 0.12), transparent 24%),
                    radial-gradient(circle at 82% 12%, rgba(255, 107, 117, 0.10), transparent 22%),
                    linear-gradient(180deg, #181349 0%, var(--app-bg) 100%);
                color: var(--app-ink);
            }

            .block-container {
                max-width: none;
                padding: 0.65rem 0.85rem 1.2rem 0.85rem;
                width: 100%;
            }

            [data-testid="stSidebar"] {
                background: #171342;
                border-right: 1px solid var(--app-border);
            }

            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3,
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
            [data-testid="stSidebar"] label {
                color: var(--app-muted);
            }

            [data-testid="stSidebar"] [data-baseweb="select"] > div {
                background: var(--app-panel);
                border-color: var(--app-border);
                color: var(--app-ink);
            }

            h1, h2, h3 {
                color: var(--app-ink);
                letter-spacing: 0;
            }

            p, li, span, label, div {
                letter-spacing: 0;
            }

            .ihc-hero {
                align-items: flex-end;
                background:
                    linear-gradient(135deg, rgba(41, 43, 87, 0.96), rgba(53, 39, 73, 0.96)),
                    linear-gradient(90deg, rgba(72, 199, 255, 0.18), transparent);
                border: 1px solid var(--app-border);
                border-radius: 8px;
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 1.25rem;
                padding: 1.1rem 1.25rem;
                box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
            }

            .ihc-hero h1 {
                font-size: clamp(1.35rem, 2.25vw, 2.15rem);
                line-height: 1.08;
                margin: 0 0 0.25rem 0;
            }

            .ihc-hero p {
                color: var(--app-muted);
                font-size: 0.95rem;
                line-height: 1.45;
                margin: 0;
                max-width: 880px;
            }

            .ihc-clock {
                color: var(--app-ink);
                font-size: 1.05rem;
                font-weight: 800;
                white-space: normal;
            }

            .ihc-card {
                background:
                    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 42%),
                    var(--app-panel);
                border: 1px solid var(--app-border);
                border-radius: 8px;
                min-height: 148px;
                padding: 1.05rem 1.08rem;
                position: relative;
                overflow: hidden;
                box-shadow:
                    0 14px 28px rgba(4, 6, 24, 0.18),
                    inset 0 1px 0 rgba(255, 255, 255, 0.045);
            }

            .ihc-card.compact {
                min-height: 122px;
            }

            .ihc-card.alert {
                background: var(--app-panel-strong);
                border-color: rgba(255, 107, 117, 0.82);
                box-shadow: 0 0 0 1px rgba(255, 107, 117, 0.18) inset;
            }

            .ihc-card.success {
                border-color: rgba(88, 219, 107, 0.44);
            }

            .ihc-card.warning {
                border-color: rgba(242, 201, 76, 0.52);
            }

            .ihc-card-title {
                color: var(--app-ink);
                font-size: 1rem;
                font-weight: 800;
                line-height: 1.25;
                margin-bottom: 0.7rem;
            }

            .ihc-card-value {
                color: var(--app-ink);
                font-size: clamp(2.15rem, 5vw, 4.6rem);
                font-weight: 850;
                line-height: 0.98;
                overflow-wrap: anywhere;
            }

            .ihc-card-value.small {
                font-size: clamp(1.65rem, 3vw, 2.7rem);
                line-height: 1.05;
            }

            .ihc-card-subtitle {
                color: var(--app-muted);
                font-size: 0.95rem;
                line-height: 1.35;
                margin-top: 0.55rem;
            }

            .ihc-alert-badge {
                align-items: center;
                background: var(--app-danger);
                border: 2px solid rgba(255, 255, 255, 0.65);
                border-radius: 999px;
                bottom: -0.35rem;
                color: white;
                display: flex;
                font-size: 1.3rem;
                font-weight: 900;
                height: 3rem;
                justify-content: center;
                position: absolute;
                right: -0.35rem;
                width: 3rem;
            }

            .ihc-panel {
                background:
                    linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent 36%),
                    var(--app-panel);
                border: 1px solid var(--app-border);
                border-radius: 8px;
                padding: 1.05rem 1.1rem;
                min-height: 340px;
                box-shadow: 0 14px 28px rgba(4, 6, 24, 0.16);
            }

            .ihc-panel h3 {
                font-size: 1.1rem;
                margin: 0 0 0.85rem 0;
            }

            .ihc-row {
                align-items: center;
                border-top: 1px solid rgba(255, 255, 255, 0.07);
                display: grid;
                gap: 0.75rem;
                grid-template-columns: minmax(0, 1fr) auto;
                padding: 0.66rem 0;
            }

            .ihc-row:first-of-type {
                border-top: 0;
            }

            .ihc-row strong {
                color: var(--app-ink);
                display: block;
                font-size: 0.96rem;
                line-height: 1.25;
                overflow-wrap: anywhere;
            }

            .ihc-row span {
                color: var(--app-muted);
                font-size: 0.82rem;
            }

            .ihc-section-label {
                color: var(--app-dim);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                margin: 1.45rem 0 0.55rem 0;
                text-transform: uppercase;
            }

            .ihc-filter-panel {
                background: rgba(37, 40, 82, 0.72);
                border: 1px solid var(--app-border);
                border-radius: 8px;
                margin-bottom: 1.15rem;
                padding: 1rem 1.1rem 0.75rem 1.1rem;
                box-shadow: 0 12px 26px rgba(4, 6, 24, 0.14);
            }

            .ihc-status {
                border: 1px solid var(--app-border);
                border-radius: 8px;
                padding: 1rem 1.1rem;
                margin: 0.45rem 0 1.05rem 0;
                background: var(--app-panel-strong);
                display: flex;
                gap: 0.85rem;
                align-items: flex-start;
                box-shadow: 0 12px 26px rgba(4, 6, 24, 0.16);
            }

            .ihc-status strong {
                display: block;
                color: var(--app-ink);
                font-size: 1rem;
                margin-bottom: 0.2rem;
            }

            .ihc-status span {
                color: var(--app-muted);
                line-height: 1.45;
            }

            .ihc-status-normal { border-left: 6px solid var(--app-success); }
            .ihc-status-attention { border-left: 6px solid var(--app-warning); }
            .ihc-status-alert { border-left: 6px solid var(--app-danger); }

            .ihc-pill-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin: 0.45rem 0 1.25rem 0;
            }

            .ihc-pill {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid var(--app-border);
                border-radius: 999px;
                color: var(--app-muted);
                display: inline-flex;
                font-size: 0.88rem;
                line-height: 1.35;
                padding: 0.38rem 0.72rem;
            }

            .ihc-empty {
                background: var(--app-panel-strong);
                border: 1px solid rgba(242, 201, 76, 0.62);
                border-left: 6px solid var(--app-warning);
                border-radius: 8px;
                color: var(--app-ink);
                padding: 1rem 1.1rem;
            }

            div[data-testid="stMarkdownContainer"] p,
            div[data-testid="stMarkdownContainer"] li,
            .stCaptionContainer {
                color: var(--app-muted);
            }

            div[data-testid="stDataFrame"] {
                background: #171a3d;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 16px 34px rgba(4, 6, 24, 0.22);
            }

            div[data-testid="stDataFrame"] [role="grid"] {
                background: #171a3d;
            }

            div[data-testid="stDataFrame"] [role="columnheader"] {
                background: #20234c;
                color: var(--app-ink);
                font-weight: 800;
                border-bottom-color: rgba(255, 255, 255, 0.12);
            }

            div[data-testid="stDataFrame"] [role="gridcell"] {
                background: #181b40;
                color: #eef0ff;
                border-color: rgba(255, 255, 255, 0.06);
            }

            div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
                background: #1d2048;
            }

            .stPlotlyChart,
            [data-testid="stVegaLiteChart"],
            [data-testid="stLineChart"] {
                background: var(--app-panel);
                border: 1px solid var(--app-border);
                border-radius: 8px;
                padding: 0.95rem;
                box-shadow: 0 14px 28px rgba(4, 6, 24, 0.16);
            }

            div[data-testid="stVerticalBlock"] {
                gap: 0.85rem;
            }

            hr {
                border-color: rgba(255, 255, 255, 0.08);
            }

            @media (max-width: 900px) {
                .ihc-hero {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .ihc-card {
                    min-height: 124px;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <section class="ihc-hero">
            <div>
                <h1>Monitor de chuva por bairro em Maceió</h1>
                <p>
                    Leitura MQTT em tempo real com indicadores de chuva, vento,
                    umidade e previsão por janela horária.
                </p>
            </div>
            <div class="ihc-clock">tempo real</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def converter_float(dados: Dict[str, Any], chave: str, default: float) -> float:
    try:
        return float(dados.get(chave, default))
    except (TypeError, ValueError):
        return default


def processar_mensagem(pacote: bytes) -> Dict[str, Any]:
    dados = json.loads(pacote.decode())
    agora = datetime.now(FUSO_APP)

    return {
        "local": dados.get("local", "Não informado"),
        "chuva": converter_float(dados, "chuva", 0.0),
        "umidade": converter_float(dados, "umidade", 0.0),
        "temp": converter_float(dados, "temperatura", 25.0),
        "pressao": converter_float(dados, "pressao", 1013.0),
        "previsao_chuva_1h": converter_float(dados, "previsao_chuva_1h", 0.0),
        "previsao_chuva_3h": converter_float(dados, "previsao_chuva_3h", 0.0),
        "previsao_chuva_6h": converter_float(dados, "previsao_chuva_6h", 0.0),
        "vento": converter_float(dados, "vento_velocidade", 0.0),
        "hora": int(dados.get("hora", agora.hour)),
        "dia_semana": dados.get("dia_semana", DIAS_SEMANA_PT[agora.weekday()]),
        "timestamp": dados.get("timestamp") or agora.strftime("%Y-%m-%d %H:%M:%S"),
        "raw": dados,
    }


def ao_receber_mensagem(cliente: mqtt.Client, execucao: RuntimeMqtt, mensagem: mqtt.MQTTMessage) -> None:
    try:
        mensagem_processada = processar_mensagem(mensagem.payload)
        with execucao.trava:
            execucao.historico.append(mensagem_processada)
        print(f"Mensagem MQTT recebida: {mensagem_processada}")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as erro:
        print(f"Erro ao processar mensagem MQTT: {erro}")


@st.cache_resource
def obter_runtime_mqtt() -> RuntimeMqtt:
    cliente = mqtt.Client()
    execucao = RuntimeMqtt(
        cliente=cliente,
        historico=deque(maxlen=MAXIMO_LINHAS_HISTORICO),
        trava=Lock(),
    )
    cliente.user_data_set(execucao)
    cliente.on_message = ao_receber_mensagem

    for tentativa in range(1, TENTATIVAS_MQTT + 1):
        try:
            print(f"Conectando ao MQTT ({tentativa}/{TENTATIVAS_MQTT})...")
            cliente.connect(BROKER_MQTT, PORTA_MQTT)
            cliente.subscribe(TOPICO_MQTT)
            cliente.loop_start()
            print("MQTT conectado.")
            return execucao
        except Exception as erro:
            print(f"Falha ao conectar no MQTT: {erro}")
            sleep(SEGUNDOS_ESPERA_TENTATIVA_MQTT)

    raise RuntimeError("Não foi possível conectar ao broker MQTT.")


def obter_linhas_historico(execucao: RuntimeMqtt) -> List[Dict[str, Any]]:
    with execucao.trava:
        mensagens = list(execucao.historico)

    return [
        {coluna: mensagem[chave] for chave, coluna in COLUNAS_DADOS.items()}
        for mensagem in mensagens
    ]


def montar_dataframe(linhas: List[Dict[str, Any]]) -> pd.DataFrame:
    quadro_dados = pd.DataFrame(linhas)
    quadro_dados["Data/Hora"] = pd.to_datetime(quadro_dados["Data/Hora"], errors="coerce")
    quadro_dados = quadro_dados.dropna(subset=["Data/Hora"]).sort_values("Data/Hora")
    quadro_dados[COLUNA_INTERPRETACAO_CHUVA] = quadro_dados.apply(descrever_condicao_chuva, axis=1)
    return quadro_dados


def classificar_status(chuva: float, vento: float, umidade: float) -> str:
    if chuva >= LIMITE_ALERTA_CHUVA_MM or vento >= LIMITE_ALERTA_VENTO_KMH:
        return "Alerta"

    if chuva > 0 or umidade >= LIMITE_ATENCAO_UMIDADE:
        return "Atenção"

    return "Normal"


def descrever_condicao_chuva(linha: pd.Series) -> str:
    chuva_agora = float(linha[COLUNA_CHUVA_AGORA])
    previsao_1h = float(linha[COLUNA_PREVISAO_1H])
    previsao_3h = float(linha[COLUNA_PREVISAO_3H])

    if chuva_agora >= LIMITE_ALERTA_CHUVA_MM:
        return "Chovendo forte agora"

    if chuva_agora >= 1:
        return "Chovendo agora"

    if chuva_agora > 0:
        return "Chuva fraca agora"

    if previsao_1h >= LIMITE_ALERTA_CHUVA_MM:
        return "Chuva forte prevista em 1h"

    if previsao_1h > 0:
        return "Pode chover em breve"

    if previsao_3h > 0:
        return "Pode chover nas próximas 3h"

    return "Sem chuva prevista"


def classificar_linha_recente(linha: pd.Series) -> str:
    chuva = max(float(linha[COLUNA_CHUVA_AGORA]), float(linha[COLUNA_PREVISAO_1H]))
    vento = float(linha["Vento (km/h)"])
    umidade = float(linha["Umidade (%)"])
    return classificar_status(chuva, vento, umidade)


def montar_ultimas_por_bairro(quadro_dados: pd.DataFrame) -> pd.DataFrame:
    ultimas_por_bairro = (
        quadro_dados.sort_values("Data/Hora")
        .drop_duplicates(subset=["Local"], keep="last")
        .sort_values("Local")
        .reset_index(drop=True)
    )
    ultimas_por_bairro["Status"] = ultimas_por_bairro.apply(classificar_linha_recente, axis=1)
    return ultimas_por_bairro


def estilizar_tabela_escura(quadro_dados: pd.DataFrame) -> pd.io.formats.style.Styler:
    return (
        quadro_dados.style.set_table_styles(
            [
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", "#20234c"),
                        ("color", "#f7f7ff"),
                        ("font-weight", "800"),
                        ("border-color", "rgba(255, 255, 255, 0.12)"),
                    ],
                },
                {
                    "selector": "tbody td",
                    "props": [
                        ("background-color", "#181b40"),
                        ("color", "#eef0ff"),
                        ("border-color", "rgba(255, 255, 255, 0.06)"),
                    ],
                },
            ]
        )
        .set_properties(
            **{
                "background-color": "#181b40",
                "color": "#eef0ff",
                "border-color": "rgba(255, 255, 255, 0.06)",
            }
        )
    )


def renderizar_rotulo_secao(texto: str) -> None:
    st.markdown(f'<p class="ihc-section-label">{escape(texto)}</p>', unsafe_allow_html=True)


def renderizar_aviso_status(status: str, titulo: str, mensagem: str) -> None:
    classe_status = {
        "Normal": "ihc-status-normal",
        "Atenção": "ihc-status-attention",
        "Alerta": "ihc-status-alert",
    }.get(status, "ihc-status-normal")
    st.markdown(
        f"""
        <div class="ihc-status {classe_status}">
            <div>
                <strong>{escape(titulo)}</strong>
                <span>{escape(mensagem)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_pilulas_contexto(itens: List[str]) -> None:
    pilulas = "".join(f'<span class="ihc-pill">{escape(item)}</span>' for item in itens)
    st.markdown(f'<div class="ihc-pill-row">{pilulas}</div>', unsafe_allow_html=True)


def renderizar_card_metrica(
    titulo: str,
    valor: str,
    subtitulo: str,
    estado: str = "normal",
    compacto: bool = False,
) -> None:
    classes_css = ["ihc-card"]
    if compacto:
        classes_css.append("compact")
    if estado in {"alert", "warning", "success"}:
        classes_css.append(estado)

    selo = '<div class="ihc-alert-badge">!</div>' if estado == "alert" else ""
    st.markdown(
        f"""
        <div class="{' '.join(classes_css)}">
            <div class="ihc-card-title">{escape(titulo)}</div>
            <div class="ihc-card-value{' small' if compacto else ''}">{escape(valor)}</div>
            <div class="ihc-card-subtitle">{escape(subtitulo)}</div>
            {selo}
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_painel_linhas(titulo: str, linhas: List[Dict[str, str]]) -> None:
    linhas_renderizadas = "".join(
        f"""
        <div class="ihc-row">
            <div>
                <strong>{escape(linha['title'])}</strong>
                <span>{escape(linha['subtitle'])}</span>
            </div>
            <strong>{escape(linha['value'])}</strong>
        </div>
        """
        for linha in linhas
    )
    st.markdown(
        f"""
        <section class="ihc-panel">
            <h3>{escape(titulo)}</h3>
            {linhas_renderizadas}
        </section>
        """,
        unsafe_allow_html=True,
    )


def renderizar_filtros(quadro_dados: pd.DataFrame) -> pd.DataFrame:
    bairros_recebidos = set(quadro_dados["Local"])
    opcoes = [OPCAO_TODOS_BAIRROS] + sorted(bairros_recebidos)

    renderizar_rotulo_secao("Filtro")
    coluna_filtro, coluna_criterios = st.columns([1.2, 1], gap="large")
    with coluna_filtro:
        bairro_selecionado = st.selectbox(
            "Filtrar por bairro",
            opcoes,
            indice=0,
            help="Escolha um bairro para ver métricas, gráficos e histórico apenas dele.",
        )
    with coluna_criterios:
        st.caption("Critérios do status")
        st.markdown(
            f"""
            - **Alerta:** chuva a partir de {LIMITE_ALERTA_CHUVA_MM} mm ou vento a partir de {LIMITE_ALERTA_VENTO_KMH} km/h.
            - **Atenção:** chuva detectada ou umidade a partir de {LIMITE_ATENCAO_UMIDADE}%.
            - **Normal:** sem sinal relevante de chuva no momento.
            """
        )

    if bairro_selecionado == OPCAO_TODOS_BAIRROS:
        renderizar_pilulas_contexto(
            [
                f"{len(bairros_recebidos)} bairros com dados",
                "Visão geral da cidade",
                f"Atualização automática: {SEGUNDOS_ATUALIZACAO_AUTOMATICA}s",
            ]
        )
        return quadro_dados

    filtered = quadro_dados[quadro_dados["Local"] == bairro_selecionado]
    renderizar_pilulas_contexto(
        [
            f"Bairro selecionado: {bairro_selecionado}",
            f"{len(filtered)} leituras disponíveis",
            f"Atualização automática: {SEGUNDOS_ATUALIZACAO_AUTOMATICA}s",
        ]
    )
    return filtered


def renderizar_estilos_referencia(tema: str) -> None:
    dark = tema == "Escuro"
    cores = {
        "bg": "#100c34" if dark else "#eef2f8",
        "panel": "#292b57" if dark else "#ffffff",
        "panel_alt": "#3a294b" if dark else "#f3f6fb",
        "ink": "#f7f7ff" if dark else "#172033",
        "muted": "#c9cce1" if dark else "#5c6680",
        "line": "rgba(255,255,255,.10)" if dark else "rgba(23,32,51,.10)",
        "accent": "#4cc9ff",
        "yellow": "#f2c94c",
        "green": "#58db6b",
        "danger": "#ff6b75",
        "shadow": "rgba(0,0,0,.18)" if dark else "rgba(23,32,51,.10)",
    }
    st.markdown(
        f"""
        <style>
            :root {{
                --app-ink: {cores['ink']};
                --app-muted: {cores['muted']};
            }}

            .stApp {{
                background: {cores['bg']};
                color: {cores['ink']};
            }}

            .block-container {{
                max-width: none;
                padding: 0.65rem 0.85rem 1.2rem 0.85rem;
                width: 100%;
            }}

            h1, h2, h3, p, span, label, div {{
                letter-spacing: 0;
            }}

            .stApp h1,
            .stApp h2,
            .stApp h3,
            .stApp h4,
            .stApp h5,
            .stApp h6,
            .stApp [data-testid="stMarkdownContainer"] h1,
            .stApp [data-testid="stMarkdownContainer"] h2,
            .stApp [data-testid="stMarkdownContainer"] h3 {{
                color: {cores['ink']} !important;
            }}

            [data-testid="stSelectbox"] label,
            [data-testid="stRadio"] label,
            .stCaptionContainer,
            div[data-testid="stMarkdownContainer"] p,
            div[data-testid="stMarkdownContainer"] li {{
                color: {cores['muted']} !important;
            }}

            .ihc-section-label {{
                color: {cores['muted']} !important;
            }}

            .ihc-top-controls {{
                background: {cores['panel']};
                border: 1px solid {cores['line']};
                border-radius: 8px;
                box-shadow: 0 16px 34px {cores['shadow']};
                margin: 3.25rem 0 1.35rem 0;
                min-height: 150px;
                overflow: visible;
                padding: 3rem 1.45rem 1.35rem 1.45rem;
                width: 100%;
            }}

            .ihc-header-title,
            .ihc-header-meta strong {{
                color: {cores['ink']} !important;
            }}

            .ihc-header-subtitle,
            .ihc-header-meta {{
                color: {cores['muted']} !important;
            }}

            .ihc-dashboard-grid {{
                display: grid;
                gap: 14px;
                grid-template-columns: 1.5fr 1fr 1fr 1fr 1.5fr;
                grid-template-rows: 330px 465px;
            }}

            .ref-card {{
                background: {cores['panel']};
                border: 1px solid {cores['line']};
                border-radius: 8px;
                box-shadow: 0 14px 30px {cores['shadow']};
                color: {cores['ink']};
                overflow: hidden;
                padding: 18px 20px;
                position: relative;
            }}

            .ref-card.alert {{
                background: {cores['panel_alt']};
                border-color: {cores['danger']};
            }}

            .ref-title {{
                color: {cores['ink']};
                font-size: 24px;
                font-weight: 800;
                line-height: 1.1;
                margin: 0 0 18px 0;
            }}

            .ref-value {{
                color: {cores['ink']};
                font-size: 82px;
                font-weight: 850;
                line-height: .95;
                margin: 0;
            }}

            .ref-value.medium {{
                font-size: 58px;
            }}

            .ref-value.small {{
                font-size: 42px;
            }}

            .ref-sub {{
                color: {cores['muted']};
                font-size: 28px;
                line-height: 1.15;
                margin-top: 8px;
            }}

            .ref-sub.small {{
                font-size: 17px;
            }}

            .ref-divider {{
                background: {cores['line']};
                height: 1px;
                margin: 18px 0 8px 0;
            }}

            .ref-alert-box {{
                border: 1px solid {cores['danger']};
                border-radius: 6px;
                margin-top: 16px;
                padding: 10px 10px 8px 10px;
                position: relative;
            }}

            .ref-alert-badge {{
                align-items: center;
                background: {cores['danger']};
                border: 2px solid rgba(255,255,255,.68);
                border-radius: 999px;
                bottom: -14px;
                color: #fff;
                display: flex;
                font-size: 26px;
                font-weight: 900;
                height: 50px;
                justify-content: center;
                position: absolute;
                right: -12px;
                width: 50px;
            }}

            .span-2 {{
                grid-column: span 2;
            }}

            .ref-row {{
                align-items: center;
                border-top: 1px solid {cores['line']};
                display: grid;
                gap: 10px;
                grid-template-columns: minmax(0, 1fr) auto;
                padding: 10px 0;
            }}

            .ref-row:first-of-type {{
                border-top: 0;
            }}

            .ref-row strong {{
                color: {cores['ink']};
                display: block;
                font-size: 20px;
                font-weight: 500;
                overflow-wrap: anywhere;
            }}

            .ref-row span {{
                color: {cores['muted']};
                display: block;
                font-size: 15px;
                margin-top: 2px;
            }}

            .ref-row-value {{
                color: {cores['ink']};
                font-size: 20px;
                font-weight: 700;
            }}

            .feedback-row {{
                align-items: center;
                border-top: 1px solid {cores['line']};
                display: grid;
                gap: 16px;
                grid-template-columns: 42px minmax(0, 1fr);
                padding: 12px 0;
            }}

            .feedback-row:first-of-type {{
                border-top: 0;
            }}

            .feedback-icon {{
                align-items: center;
                background: #5d83f0;
                border-radius: 999px;
                color: white;
                display: flex;
                font-size: 22px;
                height: 42px;
                justify-content: center;
                width: 42px;
            }}

            .chart-wrap {{
                height: 360px;
                margin-top: 6px;
            }}

            .brand-footer {{
                align-items: center;
                color: {cores['ink']};
                display: flex;
                font-size: 28px;
                gap: 12px;
                justify-content: space-between;
                margin-top: 14px;
            }}

            .brand-mark {{
                align-items: center;
                background: {cores['green']};
                border-radius: 4px;
                color: #111;
                display: inline-flex;
                font-size: 24px;
                font-weight: 900;
                height: 40px;
                justify-content: center;
                width: 40px;
            }}

            @media (max-width: 1100px) {{
                .ihc-dashboard-grid {{
                    grid-template-columns: 1fr 1fr;
                    grid-template-rows: auto;
                }}

                .span-2 {{
                    grid-column: span 2;
                }}
            }}

            @media (max-width: 720px) {{
                .ihc-dashboard-grid {{
                    grid-template-columns: 1fr;
                }}

                .span-2 {{
                    grid-column: span 1;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_controles_topo(quadro_dados: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    bairros_recebidos = set(quadro_dados["Local"])
    opcoes = [OPCAO_TODOS_BAIRROS] + sorted(bairros_recebidos)
    marcador_tempo_ultima = quadro_dados["Data/Hora"].max()

    st.markdown(
        f"""
        <style>
            .ihc-top-controls {{
                background: #292b57;
                border: 1px solid rgba(255,255,255,.10);
                border-radius: 8px;
                box-shadow: 0 16px 34px rgba(0,0,0,.18);
                margin: 3.25rem 0 1.35rem 0;
                min-height: 150px;
                overflow: visible;
                padding: 3rem 1.45rem 1.35rem 1.45rem;
                width: 100%;
            }}

            .ihc-header-title {{
                color: #f7f7ff;
                font-size: 1.28rem;
                font-weight: 800;
                line-height: 1.8;
                margin: 0;
                padding: 0;
            }}

            .ihc-header-subtitle,
            .ihc-header-meta {{
                color: #c9cce1;
                font-size: .98rem;
                line-height: 1.45;
                margin-top: .25rem;
            }}

            .ihc-header-meta {{
                text-align: right;
            }}

            .ihc-header-meta strong {{
                color: #f7f7ff;
            }}
        </style>
        <div class="ihc-top-controls">
            <div style="display:flex;justify-content:space-between;gap:1rem;align-items:center;flex-wrap:wrap;">
                <div>
                    <div class="ihc-header-title">
                        Monitor de chuva - Maceió
                    </div>
                    <div class="ihc-header-subtitle">
                        Painel de sensoriamento em tempo real com status, previsão e leituras por bairro.
                    </div>
                </div>
                <div class="ihc-header-meta">
                    <strong>{len(bairros_recebidos)}</strong> bairros com dados<br>
                    Última atualização: {marcador_tempo_ultima.strftime('%d/%m/%Y %H:%M:%S')}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    coluna_filtro, theme_column = st.columns([1.4, 1], gap="large")
    with coluna_filtro:
        bairro_selecionado = st.selectbox(
            "Filtrar por bairro",
            opcoes,
            indice=0,
            help="Escolha um bairro para ver o painel apenas dele.",
        )
    with theme_column:
        tema = st.radio("Tema", ["Escuro", "Claro"], horizontal=True, indice=0)

    if bairro_selecionado == OPCAO_TODOS_BAIRROS:
        return quadro_dados, tema

    return quadro_dados[quadro_dados["Local"] == bairro_selecionado], tema


def escalar_pontos(valores: List[float], largura: int, altura: int, margem_interna: int) -> str:
    if not valores:
        return ""

    valor_minimo = min(valores)
    valor_maximo = max(valores)
    if valor_minimo == valor_maximo:
        valor_minimo = 0
        valor_maximo = max(valor_maximo, 1)

    step = (largura - margem_interna * 2) / max(len(valores) - 1, 1)
    pontos = []
    for indice, valor in enumerate(valores):
        x = margem_interna + indice * step
        y = altura - margem_interna - ((valor - valor_minimo) / (valor_maximo - valor_minimo)) * (altura - margem_interna * 2)
        pontos.append(f"{x:.1f},{y:.1f}")
    return " ".join(pontos)


def montar_svg_grafico_linhas(historico: pd.DataFrame) -> str:
    largura = 680
    altura = 360
    margem_interna = 46
    grafico = historico.tail(8).copy()
    if grafico.empty:
        return ""

    valores_chuva = grafico[COLUNA_CHUVA_AGORA].astype(float).tolist()
    valores_previsao = grafico[COLUNA_PREVISAO_3H].astype(float).tolist()
    all_values = valores_chuva + valores_previsao
    valor_maximo = max(max(all_values), 1)
    labels = grafico["Data/Hora"].dt.strftime("%H:%M").tolist()
    first_label = labels[0]
    middle_label = labels[len(labels) // 2]
    last_label = labels[-1]
    rain_points = escalar_pontos(valores_chuva, largura, altura, margem_interna)
    forecast_points = escalar_pontos(valores_previsao, largura, altura, margem_interna)
    grid_lines = "\n".join(
        f'<line x1="{margem_interna}" y1="{margem_interna + i * 58}" x2="{largura - margem_interna}" y2="{margem_interna + i * 58}" />'
        for i in range(5)
    )

    return f"""
    <svg viewBox="0 0 {largura} {altura}" width="100%" height="100%" role="img" aria-label="Gráfico de chuva">
        <g stroke="rgba(255,255,255,.12)" stroke-width="1">{grid_lines}</g>
        <text x="{margem_interna}" y="28" fill="currentColor" opacity=".78" font-size="14">{valor_maximo:.1f} mm</text>
        <circle cx="{largura - 190}" cy="28" r="5" fill="#4cc9ff" />
        <text x="{largura - 178}" y="33" fill="currentColor" opacity=".82" font-size="15">Agora</text>
        <circle cx="{largura - 100}" cy="28" r="5" fill="#f2c94c" />
        <text x="{largura - 88}" y="33" fill="currentColor" opacity=".82" font-size="15">Prev. 3h</text>
        <polyline points="{rain_points}" fill="none" stroke="#4cc9ff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        <polyline points="{forecast_points}" fill="none" stroke="#f2c94c" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        <text x="{margem_interna}" y="{altura - 12}" fill="currentColor" opacity=".82" font-size="16">{escape(first_label)}</text>
        <text x="{largura / 2 - 25}" y="{altura - 12}" fill="currentColor" opacity=".82" font-size="16">{escape(middle_label)}</text>
        <text x="{largura - margem_interna - 44}" y="{altura - 12}" fill="currentColor" opacity=".82" font-size="16">{escape(last_label)}</text>
    </svg>
    """


def montar_svg_medidor(valor: float) -> str:
    valor = max(0, min(100, valor))
    angle = 180 - (valor / 100 * 180)
    return f"""
    <svg viewBox="0 0 240 182" width="100%" height="182" role="img" aria-label="Medidor de umidade">
        <path d="M 40 112 A 80 80 0 0 1 200 112" fill="none" stroke="rgba(255,255,255,.16)" stroke-width="28" />
        <path d="M 167 55 A 80 80 0 0 1 200 112" fill="none" stroke="#58db6b" stroke-width="28" />
        <line x1="120" y1="112" x2="120" y2="48" stroke="#f7f7ff" stroke-width="7" stroke-linecap="round" transform="rotate({angle:.1f} 120 112)" />
        <circle cx="120" cy="112" r="10" fill="#f7f7ff" />
        <text x="42" y="140" fill="currentColor" opacity=".75" font-size="14">0%</text>
        <text x="176" y="140" fill="currentColor" opacity=".75" font-size="14">100%</text>
        <text x="120" y="174" fill="currentColor" text-anchor="middle" font-size="34" font-weight="850">{valor:.0f}%</text>
    </svg>
    """


def montar_linhas_referencia(linhas: List[Dict[str, str]]) -> str:
    return "".join(
        f"""
        <div class="ref-row">
            <div>
                <strong>{escape(linha['title'])}</strong>
                <span>{escape(linha['subtitle'])}</span>
            </div>
            <div class="ref-row-value">{escape(linha['value'])}</div>
        </div>
        """
        for linha in linhas
    )


def montar_linhas_feedback(linhas: List[Dict[str, str]]) -> str:
    return "".join(
        f"""
        <div class="feedback-row">
            <div class="feedback-icon">✓</div>
            <div>
                <div class="ref-row-value">{escape(linha['title'])}</div>
                <span>{escape(linha['subtitle'])}</span>
            </div>
        </div>
        """
        for linha in linhas
    )


def encurtar_texto(texto: str, max_length: int) -> str:
    if len(texto) <= max_length:
        return texto
    return f"{texto[: max_length - 1].rstrip()}…"


def obter_cores_referencia(tema: str) -> Dict[str, str]:
    dark = tema == "Escuro"
    return {
        "bg": "#100c34" if dark else "#eef2f8",
        "panel": "#292b57" if dark else "#ffffff",
        "panel_alt": "#3a294b" if dark else "#f3f6fb",
        "ink": "#f7f7ff" if dark else "#172033",
        "muted": "#c9cce1" if dark else "#5c6680",
        "line": "rgba(255,255,255,.10)" if dark else "rgba(23,32,51,.10)",
        "accent": "#4cc9ff",
        "yellow": "#f2c94c",
        "green": "#58db6b",
        "danger": "#ff6b75",
        "shadow": "rgba(0,0,0,.18)" if dark else "rgba(23,32,51,.10)",
    }


def montar_css_componente_referencia(tema: str) -> str:
    cores = obter_cores_referencia(tema)
    return f"""
        html, body {{
            background: {cores['bg']};
            color: {cores['ink']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 10px 0 0 0;
            width: 100%;
        }}

        * {{
            box-sizing: border-box;
            letter-spacing: 0;
        }}

        .ihc-dashboard-grid {{
            display: grid;
            gap: 14px;
            grid-template-columns: 1.5fr 1fr 1fr 1fr 1.5fr;
            grid-template-rows: 370px 500px;
            padding: 0 2px;
            width: 100%;
        }}

        .ref-card {{
            background: {cores['panel']};
            border: 1px solid {cores['line']};
            border-radius: 8px;
            box-shadow: 0 14px 30px {cores['shadow']};
            color: {cores['ink']};
            overflow: hidden;
            padding: 26px 22px 20px 22px;
            position: relative;
        }}

        .ref-card.alert {{
            background: {cores['panel_alt']};
            border-color: {cores['danger']};
        }}

        .ref-title {{
            color: {cores['ink']};
            font-size: clamp(18px, 1.25vw, 22px);
            font-weight: 800;
            line-height: 1.34;
            margin: 0 0 12px 0;
            padding-top: 2px;
        }}

        .ref-value {{
            color: {cores['ink']};
            font-size: clamp(46px, 4vw, 64px);
            font-weight: 850;
            line-height: 1.14;
            margin: 0;
            padding-top: 4px;
        }}

        .ref-value.medium {{
            font-size: clamp(34px, 3vw, 46px);
            line-height: 1.08;
        }}

        .ref-sub {{
            color: {cores['muted']};
            font-size: clamp(18px, 1.35vw, 23px);
            line-height: 1.15;
            margin-top: 8px;
        }}

        .ref-sub.small {{
            font-size: clamp(15px, 1.1vw, 17px);
            overflow-wrap: anywhere;
        }}

        .ref-divider {{
            background: {cores['line']};
            height: 1px;
            margin: 18px 0 8px 0;
        }}

            .ref-alert-box {{
                border: 1px solid {cores['danger']};
                border-radius: 6px;
                margin-top: 12px;
                padding: 10px 12px 12px 12px;
                position: relative;
            }}

            .ref-alert-box .ref-value.medium {{
                font-size: clamp(34px, 3vw, 46px);
            }}

        .ref-alert-badge {{
            align-items: center;
            background: {cores['danger']};
            border: 2px solid rgba(255,255,255,.68);
            border-radius: 999px;
            bottom: 8px;
            color: #fff;
            display: flex;
            font-size: 22px;
            font-weight: 900;
            height: 44px;
            justify-content: center;
            position: absolute;
            right: 10px;
            width: 44px;
        }}

        .span-2 {{
            grid-column: span 2;
        }}

        .ref-row {{
            align-items: center;
            border-top: 1px solid {cores['line']};
            display: grid;
            gap: 10px;
            grid-template-columns: minmax(0, 1fr) auto;
            padding: 10px 0;
        }}

        .ref-row:first-of-type {{
            border-top: 0;
        }}

            .ref-row strong {{
                color: {cores['ink']};
                display: block;
                font-size: clamp(17px, 1.25vw, 20px);
                font-weight: 500;
                overflow-wrap: anywhere;
            }}

        .ref-row span {{
            color: {cores['muted']};
            display: block;
                font-size: clamp(13px, 1vw, 15px);
                margin-top: 2px;
            }}

        .ref-row-value {{
            color: {cores['ink']};
                font-size: clamp(17px, 1.25vw, 20px);
                font-weight: 700;
                overflow-wrap: anywhere;
            }}

            .feedback-row {{
            align-items: center;
            border-top: 1px solid {cores['line']};
            display: grid;
            gap: 16px;
            grid-template-columns: 36px minmax(0, 1fr);
                padding: 11px 0;
            }}

        .feedback-row:first-of-type {{
            border-top: 0;
        }}

        .feedback-icon {{
            align-items: center;
            background: #5d83f0;
            border-radius: 999px;
            color: white;
            display: flex;
            font-size: 18px;
            height: 36px;
            justify-content: center;
            width: 36px;
        }}

        .scroll-list {{
            overflow-y: auto;
            padding-right: 8px;
        }}

        .scroll-list.top {{
            max-height: 275px;
        }}

        .scroll-list.bottom {{
            max-height: 395px;
        }}

        .scroll-list::-webkit-scrollbar {{
            width: 8px;
        }}

        .scroll-list::-webkit-scrollbar-track {{
            background: rgba(255,255,255,.05);
            border-radius: 999px;
        }}

        .scroll-list::-webkit-scrollbar-thumb {{
            background: rgba(255,255,255,.28);
            border-radius: 999px;
        }}

        .scroll-list::-webkit-scrollbar-thumb:hover {{
            background: rgba(255,255,255,.42);
        }}

            .chart-wrap {{
                height: 390px;
                margin-top: 6px;
            }}

        .ref-card.alert .ref-value.medium {{
            font-size: clamp(32px, 2.6vw, 42px);
            line-height: 1.16;
            overflow-wrap: anywhere;
            margin-bottom: 6px;
        }}

            .ref-card.alert .ref-sub.small {{
                font-size: clamp(14px, 1vw, 16px);
                line-height: 1.2;
            }}

        .brand-footer {{
            align-items: center;
            color: {cores['ink']};
            display: flex;
            font-size: 28px;
            gap: 12px;
            justify-content: space-between;
            margin-top: 14px;
        }}

        .brand-mark {{
            align-items: center;
            background: {cores['green']};
            border-radius: 4px;
            color: #111;
            display: inline-flex;
            font-size: 24px;
            font-weight: 900;
            height: 40px;
            justify-content: center;
            width: 40px;
        }}

        @media (max-width: 1100px) {{
            .ihc-dashboard-grid {{
                grid-template-columns: 1fr 1fr;
                grid-template-rows: auto;
            }}

            .span-2 {{
                grid-column: span 2;
            }}
        }}

        @media (max-width: 720px) {{
            .ihc-dashboard-grid {{
                grid-template-columns: 1fr;
            }}

            .span-2 {{
                grid-column: span 1;
            }}
        }}
    """


def renderizar_dashboard_referencia(quadro_dados: pd.DataFrame, ultima: pd.Series, tema: str) -> None:
    recentes = quadro_dados.tail(LINHAS_HISTORICO_RECENTE)
    ultimas_por_bairro = montar_ultimas_por_bairro(quadro_dados)
    condicoes = classificar_condicoes(ultima, recentes)

    quantidade_bairros = ultimas_por_bairro["Local"].nunique()
    quantidade_atencao = int((ultimas_por_bairro["Status"] != "Normal").sum())
    chuva_agora = float(ultima[COLUNA_CHUVA_AGORA])
    previsao_1h = float(ultima[COLUNA_PREVISAO_1H])
    previsao_3h = float(ultima[COLUNA_PREVISAO_3H])
    previsao_6h = float(ultima[COLUNA_PREVISAO_6H])
    umidade = float(ultima["Umidade (%)"])
    vento = float(ultima["Vento (km/h)"])
    pressao = float(ultima["Pressão (hPa)"])
    svg_grafico = montar_svg_grafico_linhas(quadro_dados)
    svg_medidor = montar_svg_medidor(umidade)
    classe_status = "alert" if condicoes["status"] == "Alerta" else ""

    ranking_status = {"Alerta": 3, "Atenção": 2, "Normal": 1}
    fonte_critica = ultimas_por_bairro.assign(
        _status_rank=ultimas_por_bairro["Status"].map(ranking_status).fillna(0),
        _rain_priority=ultimas_por_bairro[COLUNA_CHUVA_AGORA] + ultimas_por_bairro[COLUNA_PREVISAO_1H],
    ).sort_values(["_status_rank", "_rain_priority", "Vento (km/h)"], ascending=False)

    linhas_criticas = [
        {
            "title": str(linha["Local"]),
            "subtitle": encurtar_texto(f"{linha['Status']} - {linha[COLUNA_INTERPRETACAO_CHUVA]}", 42),
            "value": f"{linha[COLUNA_CHUVA_AGORA]:.1f}",
        }
        for _, linha in fonte_critica.head(6).iterrows()
    ]
    linhas_feedback = [
        {"title": encurtar_texto(ultima[COLUNA_INTERPRETACAO_CHUVA], 34), "subtitle": f"{ultima['Local']} - agora"},
        {"title": f"Previsão 1h: {previsao_1h:.1f} mm", "subtitle": "Próxima janela de chuva"},
        {"title": f"Previsão 3h: {previsao_3h:.1f} mm", "subtitle": "Tendência acumulada"},
        {"title": f"Previsão 6h: {previsao_6h:.1f} mm", "subtitle": "Horizonte estendido"},
        {"title": f"Pressão: {pressao:.1f} hPa", "subtitle": "Última leitura atmosférica"},
    ]
    linhas_vento = [
        {
            "title": str(linha["Local"]),
            "subtitle": encurtar_texto(f"Umidade {linha['Umidade (%)']:.0f}% | {linha[COLUNA_INTERPRETACAO_CHUVA]}", 44),
            "value": f"{linha['Vento (km/h)']:.1f}",
        }
        for _, linha in ultimas_por_bairro.sort_values("Vento (km/h)", ascending=False).head(10).iterrows()
    ]

    html_dashboard = f"""
        <style>{montar_css_componente_referencia(tema)}</style>
        <div class="ihc-dashboard-grid">
            <section class="ref-card">
                <h3 class="ref-title">Bairros monitorados</h3>
                <div class="ref-value">{quantidade_bairros}</div>
                <div class="ref-sub">com dados</div>
                <div class="ref-alert-box">
                    <div class="ref-value medium">{quantidade_atencao}</div>
                    <div class="ref-sub">em atenção</div>
                    {'<div class="ref-alert-badge">!</div>' if quantidade_atencao else ''}
                </div>
            </section>

            <section class="ref-card">
                <h3 class="ref-title">Chuva hoje</h3>
                <div class="ref-value medium">{chuva_agora:.1f}<span style="font-size:22px">mm</span></div>
                <div class="ref-sub small">Agora</div>
                <div class="ref-divider"></div>
                <div class="ref-value medium">{previsao_3h:.1f}<span style="font-size:22px">mm</span></div>
                <div class="ref-sub small">Previsto em 3h</div>
            </section>

            <section class="ref-card">
                <h3 class="ref-title">Umidade</h3>
                {svg_medidor}
            </section>

            <section class="ref-card alert">
                <h3 class="ref-title">Status geral</h3>
                <div class="ref-value medium">{escape(condicoes['status'])}</div>
                <div class="ref-sub small">{escape(encurtar_texto(condicoes['message'], 118))}</div>
                {'<div class="ref-alert-badge">!</div>' if condicoes['status'] != 'Normal' else ''}
            </section>

            <section class="ref-card">
                <h3 class="ref-title">Bairros críticos</h3>
                <div class="scroll-list top">
                    {montar_linhas_referencia(linhas_criticas)}
                </div>
            </section>

            <section class="ref-card span-2">
                <h3 class="ref-title">Chuva agora vs previsão</h3>
                <div class="chart-wrap">{svg_grafico}</div>
            </section>

            <section class="ref-card span-2">
                <h3 class="ref-title">Leituras e previsões</h3>
                <div class="scroll-list bottom">
                    {montar_linhas_feedback(linhas_feedback)}
                </div>
            </section>

            <section class="ref-card">
                <h3 class="ref-title">Vento por bairro</h3>
                <div class="scroll-list bottom">
                    {montar_linhas_referencia(linhas_vento)}
                </div>
            </section>
        </div>
        <div class="brand-footer">
            <div><span class="brand-mark">↻</span> Monitoramento de chuva</div>
            <strong>{ultima['Data/Hora'].strftime('%H:%M')}</strong>
        </div>
    """
    components.html(html_dashboard, altura=970, scrolling=False)


def classificar_condicoes(ultima: pd.Series, recentes: pd.DataFrame) -> Dict[str, str]:
    soma_chuva = float(recentes[COLUNA_CHUVA_AGORA].sum())
    previsao_1h = float(ultima[COLUNA_PREVISAO_1H])
    max_wind = float(recentes["Vento (km/h)"].max())
    umidade = float(ultima["Umidade (%)"])
    status = classificar_status(max(soma_chuva, previsao_1h), max_wind, umidade)

    if status == "Alerta":
        return {
            "status": "Alerta",
            "message": "Há risco operacional por chuva, previsão próxima ou vento forte. Verifique o bairro em atenção e acompanhe os próximos registros.",
        }

    if status == "Atenção":
        return {
            "status": "Atenção",
            "message": "Há indício de chuva, previsão próxima ou umidade elevada. Continue monitorando a evolução dos dados.",
        }

    return {
        "status": "Normal",
        "message": "As últimas leituras não indicam chuva ou vento em nível de atenção.",
    }


def obter_bairro_atencao(recentes: pd.DataFrame) -> str:
    agrupado = (
        recentes.groupby("Local", as_index=False)
        .agg({COLUNA_CHUVA_AGORA: "sum", "Vento (km/h)": "max"})
        .sort_values([COLUNA_CHUVA_AGORA, "Vento (km/h)"], ascending=False)
    )
    bairro = agrupado.iloc[0]
    return f"{bairro['Local']} ({bairro[COLUNA_CHUVA_AGORA]:.2f} mm)"


def obter_bairro_mais_vento(recentes: pd.DataFrame) -> str:
    agrupado = (
        recentes.groupby("Local", as_index=False)["Vento (km/h)"]
        .max()
        .sort_values("Vento (km/h)", ascending=False)
    )
    bairro = agrupado.iloc[0]
    return f"{bairro['Local']} ({bairro['Vento (km/h)']:.1f} km/h)"


def renderizar_condicoes(quadro_dados: pd.DataFrame, ultima: pd.Series) -> None:
    recentes = quadro_dados.tail(LINHAS_HISTORICO_RECENTE)
    condicoes = classificar_condicoes(ultima, recentes)
    state_by_status = {
        "Normal": "success",
        "Atenção": "warning",
        "Alerta": "alert",
    }

    renderizar_rotulo_secao("Situação do monitoramento")
    renderizar_aviso_status(
        condicoes["status"],
        f"Status atual: {condicoes['status']}",
        condicoes["message"],
    )

    columns = st.columns(4, gap="large")
    with columns[0]:
        renderizar_card_metrica(
            "Status",
            condicoes["status"],
            "Classificação automática",
            state_by_status.get(condicoes["status"], "success"),
            compacto=True,
        )
    with columns[1]:
        renderizar_card_metrica(
            "Chuva recente",
            f"{recentes[COLUNA_CHUVA_AGORA].sum():.2f} mm",
            f"Últimos {len(recentes)} registros",
            "warning" if recentes[COLUNA_CHUVA_AGORA].sum() > 0 else "success",
            compacto=True,
        )
    with columns[2]:
        renderizar_card_metrica(
            "Bairro em atenção",
            obter_bairro_atencao(recentes),
            "Maior volume recente",
            "warning",
            compacto=True,
        )
    with columns[3]:
        renderizar_card_metrica(
            "Maior vento",
            obter_bairro_mais_vento(recentes),
            "Pico registrado",
            "alert" if recentes["Vento (km/h)"].max() >= LIMITE_ALERTA_VENTO_KMH else "success",
            compacto=True,
        )


def renderizar_resumo(ultima: pd.Series) -> None:
    renderizar_rotulo_secao("Leitura mais recente")
    renderizar_pilulas_contexto(
        [
            f"Local: {ultima['Local']}",
            f"Última atualização: {ultima['Data/Hora'].strftime('%d/%m/%Y às %H:%M:%S')}",
            f"Dia: {ultima['Dia da semana']}",
        ]
    )

    chuva_agora = float(ultima[COLUNA_CHUVA_AGORA])
    previsao_3h = float(ultima[COLUNA_PREVISAO_3H])
    vento = float(ultima["Vento (km/h)"])
    umidade = float(ultima["Umidade (%)"])

    columns = st.columns([1.35, 1, 1, 1, 1], gap="large")
    with columns[0]:
        rain_state = "alert" if chuva_agora >= LIMITE_ALERTA_CHUVA_MM else "warning" if chuva_agora > 0 else "success"
        renderizar_card_metrica(
            "Chuva agora",
            f"{chuva_agora:.2f}",
            f"mm - {ultima[COLUNA_INTERPRETACAO_CHUVA]}",
            rain_state,
        )
    with columns[1]:
        forecast_state = "alert" if previsao_3h >= LIMITE_ALERTA_CHUVA_MM else "warning" if previsao_3h > 0 else "success"
        renderizar_card_metrica(
            "Previsão 3h",
            f"{previsao_3h:.2f}",
            "mm acumulados",
            forecast_state,
        )
    with columns[2]:
        renderizar_card_metrica(
            "Temperatura",
            f"{ultima['Temperatura (°C)']:.1f}",
            "graus Celsius",
            "normal",
        )
    with columns[3]:
        renderizar_card_metrica(
            "Umidade",
            f"{umidade:.0f}%",
            "ar úmido" if umidade >= LIMITE_ATENCAO_UMIDADE else "nível observado",
            "warning" if umidade >= LIMITE_ATENCAO_UMIDADE else "normal",
        )
    with columns[4]:
        renderizar_card_metrica(
            "Vento",
            f"{vento:.1f}",
            "km/h",
            "alert" if vento >= LIMITE_ALERTA_VENTO_KMH else "normal",
        )

    details = [
        ("Previsão 1h", f"{ultima[COLUNA_PREVISAO_1H]:.2f} mm"),
        ("Previsão 6h", f"{ultima[COLUNA_PREVISAO_6H]:.2f} mm"),
        ("Pressão", f"{ultima['Pressão (hPa)']:.1f} hPa"),
        ("Interpretação", ultima[COLUNA_INTERPRETACAO_CHUVA]),
    ]
    for coluna, (label, valor) in zip(st.columns(4, gap="large"), details):
        with coluna:
            renderizar_card_metrica(label, str(valor), "detalhe da leitura", compacto=True)


def renderizar_ultimas_por_bairro(quadro_dados: pd.DataFrame) -> None:
    ultimas_por_bairro = montar_ultimas_por_bairro(quadro_dados)

    renderizar_rotulo_secao("Cobertura por bairro")
    st.subheader("Última leitura disponível")
    st.caption(
        "A tabela prioriza comparação entre bairros. Os valores em milímetros indicam chuva acumulada."
    )
    st.dataframe(
        estilizar_tabela_escura(ultimas_por_bairro[COLUNAS_ULTIMAS_POR_BAIRRO]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Resumo da condição calculada a partir de chuva, previsão, umidade e vento.",
            ),
            COLUNA_INTERPRETACAO_CHUVA: st.column_config.TextColumn(
                COLUNA_INTERPRETACAO_CHUVA,
                help="Explicação simples dos valores de chuva para facilitar a leitura.",
            ),
            COLUNA_CHUVA_AGORA: st.column_config.NumberColumn(
                COLUNA_CHUVA_AGORA,
                help="Chuva registrada na hora atual para o bairro, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_1H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_1H,
                help="Chuva acumulada prevista para a próxima 1 hora, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_3H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_3H,
                help="Chuva acumulada prevista para as próximas 3 horas, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_6H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_6H,
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


def renderizar_paineis_operacionais(quadro_dados: pd.DataFrame) -> None:
    ultimas_por_bairro = montar_ultimas_por_bairro(quadro_dados)
    ranking_status = {"Alerta": 3, "Atenção": 2, "Normal": 1}
    latest_ranked = ultimas_por_bairro.assign(
        _status_rank=ultimas_por_bairro["Status"].map(ranking_status).fillna(0),
        _rain_priority=ultimas_por_bairro[COLUNA_CHUVA_AGORA] + ultimas_por_bairro[COLUNA_PREVISAO_1H],
    ).sort_values(["_status_rank", "_rain_priority", "Vento (km/h)"], ascending=False)

    attention_rows = [
        {
            "title": str(linha["Local"]),
            "subtitle": f"{linha['Status']} - {linha[COLUNA_INTERPRETACAO_CHUVA]}",
            "value": f"{linha[COLUNA_CHUVA_AGORA]:.2f} mm",
        }
        for _, linha in latest_ranked.head(6).iterrows()
    ]

    forecast_rows = [
        {
            "title": str(linha["Local"]),
            "subtitle": f"1h: {linha[COLUNA_PREVISAO_1H]:.2f} mm | 6h: {linha[COLUNA_PREVISAO_6H]:.2f} mm",
            "value": f"{linha[COLUNA_PREVISAO_3H]:.2f} mm",
        }
        for _, linha in ultimas_por_bairro.sort_values(COLUNA_PREVISAO_3H, ascending=False).head(6).iterrows()
    ]

    linhas_vento = [
        {
            "title": str(linha["Local"]),
            "subtitle": f"Umidade: {linha['Umidade (%)']:.0f}% | Pressão: {linha['Pressão (hPa)']:.0f} hPa",
            "value": f"{linha['Vento (km/h)']:.1f}",
        }
        for _, linha in ultimas_por_bairro.sort_values("Vento (km/h)", ascending=False).head(6).iterrows()
    ]

    renderizar_rotulo_secao("Painéis rápidos")
    columns = st.columns(3, gap="large")
    with columns[0]:
        renderizar_painel_linhas("Bairros críticos", attention_rows)
    with columns[1]:
        renderizar_painel_linhas("Previsão de chuva", forecast_rows)
    with columns[2]:
        renderizar_painel_linhas("Vento por bairro", linhas_vento)


def renderizar_graficos(quadro_dados: pd.DataFrame) -> None:
    historico = quadro_dados.tail(LINHAS_HISTORICO_RECENTE).set_index("Data/Hora")

    renderizar_rotulo_secao("Tendências recentes")
    st.subheader("Evolução dos últimos registros")
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("**Temperatura e umidade**")
        st.line_chart(historico[["Temperatura (°C)", "Umidade (%)"]])

    with right:
        st.markdown("**Chuva, previsão e vento**")
        st.line_chart(historico[[COLUNA_CHUVA_AGORA, COLUNA_PREVISAO_3H, "Vento (km/h)"]])


def renderizar_historico(quadro_dados: pd.DataFrame, ultima: pd.Series) -> None:
    renderizar_rotulo_secao("Auditoria")
    st.subheader("Histórico recente")
    tabela = quadro_dados.tail(20).reset_index(drop=True)
    st.dataframe(
        estilizar_tabela_escura(tabela[COLUNAS_TABELA]),
        use_container_width=True,
        hide_index=True,
        column_config={
            COLUNA_INTERPRETACAO_CHUVA: st.column_config.TextColumn(
                COLUNA_INTERPRETACAO_CHUVA,
                help="Explicação simples dos valores de chuva para facilitar a leitura.",
            ),
            COLUNA_CHUVA_AGORA: st.column_config.NumberColumn(
                COLUNA_CHUVA_AGORA,
                help="Chuva registrada na hora atual para o bairro, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_1H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_1H,
                help="Chuva acumulada prevista para a próxima 1 hora, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_3H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_3H,
                help="Chuva acumulada prevista para as próximas 3 horas, em milímetros.",
                format="%.2f",
            ),
            COLUNA_PREVISAO_6H: st.column_config.NumberColumn(
                COLUNA_PREVISAO_6H,
                help="Chuva acumulada prevista para as próximas 6 horas, em milímetros.",
                format="%.2f",
            ),
        },
    )

    st.subheader("Último pacote MQTT recebido")
    with st.expander("Abrir JSON completo"):
        st.json(ultima["Dados brutos"])


def renderizar_dashboard(execucao: RuntimeMqtt) -> None:
    linhas = obter_linhas_historico(execucao)
    if not linhas:
        renderizar_estilos_referencia("Escuro")
        st.markdown(
            """
            <div class="ihc-empty">
                Nenhum dado chegou ainda. Aguarde o primeiro pacote MQTT publicado pelo sensor.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    quadro_dados = montar_dataframe(linhas)
    if quadro_dados.empty:
        renderizar_estilos_referencia("Escuro")
        st.markdown(
            """
            <div class="ihc-empty">
                Dados recebidos, mas nenhum timestamp válido foi encontrado para exibição.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    quadro_dados, tema = renderizar_controles_topo(quadro_dados)
    renderizar_estilos_referencia(tema)
    if quadro_dados.empty:
        st.markdown(
            """
            <div class="ihc-empty">
                Ainda não há leituras para o bairro selecionado.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    ultima = quadro_dados.iloc[-1]
    renderizar_dashboard_referencia(quadro_dados, ultima, tema)

    renderizar_rotulo_secao("Dados detalhados")
    renderizar_ultimas_por_bairro(quadro_dados)
    renderizar_historico(quadro_dados, ultima)


def configurar_pagina() -> None:
    st.set_page_config(page_title="Monitor de Chuva - Maceió", page_icon="🌧️", layout="wide")


def principal() -> None:
    configurar_pagina()
    try:
        execucao_mqtt = obter_runtime_mqtt()
    except RuntimeError as erro:
        renderizar_aviso_status(
            "Alerta",
            "Conexão MQTT indisponível",
            f"{erro} A tela tentará reconectar automaticamente em {SEGUNDOS_ATUALIZACAO_AUTOMATICA}s.",
        )
        sleep(SEGUNDOS_ATUALIZACAO_AUTOMATICA)
        st.rerun()

    renderizar_dashboard(execucao_mqtt)

    sleep(SEGUNDOS_ATUALIZACAO_AUTOMATICA)
    st.rerun()


principal()
