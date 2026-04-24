import pandas as pd
import numpy as np
import requests
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score
import joblib
import random
from datetime import datetime, date, timedelta

# ----------------------------
# CONFIGURAÇÃO (MACEIÓ + BAIRROS)
# ----------------------------
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

TIMEZONE = "America/Sao_Paulo"

BAIRROS_COORDS = {
    "Ponta Verde": (-9.659, -35.700),
    "Pajuçara": (-9.665, -35.715),
    "Jatiúca": (-9.655, -35.705),
    "Farol": (-9.655, -35.735),
    "Benedito Bentes": (-9.590, -35.750),
    "Centro": (-9.6658, -35.7353)
}

# ----------------------------
# FEATURE ENGINEERING
# ----------------------------
def calcular_feature_engineering(df):
    df = df.copy()
    df['delta_pressao'] = df['pressao'].diff().fillna(0)
    df['media_umidade_3h'] = df['umidade'].rolling(3, min_periods=1).mean()
    df['chuva_ultimas_3h'] = df['precipitacao'].rolling(3, min_periods=1).sum()
    df['hora_sin'] = np.sin(2 * np.pi * df['hora'] / 24)
    df['hora_cos'] = np.cos(2 * np.pi * df['hora'] / 24)
    df['tendencia_chuva'] = df['precipitacao'].diff().fillna(0)
    return df

# ----------------------------
# DADOS REAIS (OPEN-METEO)
# ----------------------------
def obter_dados_reais_open_meteo_archive(days=90):
    bairro = random.choice(list(BAIRROS_COORDS.keys()))
    LATITUDE, LONGITUDE = BAIRROS_COORDS[bairro]

    start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = date.today().strftime('%Y-%m-%d')

    try:
        resposta = requests.get(OPEN_METEO_ARCHIVE_URL, params={
            'latitude': LATITUDE,
            'longitude': LONGITUDE,
            'start_date': start_date,
            'end_date': end_date,
            'hourly': 'temperature_2m,relativehumidity_2m,pressure_msl,precipitation,windspeed_10m',
            'timezone': TIMEZONE
        }, timeout=30)

        resposta.raise_for_status()
        dados_api = resposta.json()
        hourly = dados_api.get('hourly', {})

        registros = []
        for i, time_str in enumerate(hourly.get('time', [])):
            dt = datetime.fromisoformat(time_str)
            registros.append({
                'tempo': dt,
                'temperatura': hourly['temperature_2m'][i],
                'umidade': hourly['relativehumidity_2m'][i],
                'pressao': hourly['pressure_msl'][i],
                'vento_velocidade': hourly['windspeed_10m'][i],
                'precipitacao': hourly['precipitation'][i],
                'dia_semana': dt.strftime('%A'),
                'hora': dt.hour
            })

        df = pd.DataFrame(registros).sort_values('tempo')

        df['vai_chover'] = (
            df['precipitacao'].rolling(3).sum().shift(-3) > 0.5
        ).astype(int)

        df = df.dropna()
        return calcular_feature_engineering(df)

    except Exception as e:
        print("⚠️ Erro Open-Meteo:", e)
        return pd.DataFrame()

# ----------------------------
# DADOS SINTÉTICOS
# ----------------------------
def gerar_dados_treinamento(n=5000):
    dados = []
    dias = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    for i in range(n):
        temp = random.uniform(20,35)
        umid = random.uniform(40,100)
        press = random.uniform(1000,1020)
        vento = random.uniform(0,20)
        hora = i % 24

        prob = 0
        if umid > 80: prob += 0.4
        elif umid > 60: prob += 0.2
        if press < 1010: prob += 0.3
        if 22 <= temp <= 28: prob += 0.2

        prob += random.uniform(-0.1,0.1)
        prob = max(0,min(1,prob))

        chuva = random.uniform(0,3) if random.random() < prob else random.uniform(0,0.3)

        dados.append({
            'tempo': datetime.now() + timedelta(hours=i),
            'temperatura': temp,
            'umidade': umid,
            'pressao': press,
            'vento_velocidade': vento,
            'hora': hora,
            'dia_semana': random.choice(dias),
            'precipitacao': chuva
        })

    df = pd.DataFrame(dados).sort_values('tempo')

    df['vai_chover'] = (
        df['precipitacao'].rolling(3).sum().shift(-3) > 0.5
    ).astype(int)

    df = df.dropna()
    return calcular_feature_engineering(df)

# ----------------------------
# PREPROCESSAMENTO
# ----------------------------
def preprocessar(df):
    mapa = {
        "Monday":0,"Tuesday":1,"Wednesday":2,
        "Thursday":3,"Friday":4,"Saturday":5,"Sunday":6
    }

    df = df.copy()
    df['dia_semana'] = df['dia_semana'].str.strip().str.capitalize().map(mapa)
    df = df.dropna(subset=['dia_semana'])

    return df

# ----------------------------
# TREINO
# ----------------------------
def treinar_modelo():

    print("🔄 Buscando dados reais...")
    df_real = obter_dados_reais_open_meteo_archive()

    if df_real.empty:
        print("⚠️ usando dados sintéticos")
        df = gerar_dados_treinamento()
    else:
        df = df_real

    df = preprocessar(df)

    features = [
        'temperatura','umidade','pressao','vento_velocidade',
        'hora','dia_semana','delta_pressao','media_umidade_3h',
        'chuva_ultimas_3h','hora_sin','hora_cos','tendencia_chuva'
    ]

    X = df[features]
    y = df['vai_chover']

    # pesos balanceados
    total = len(y)
    dist = y.value_counts()
    weights = {
        0: total/(2*dist.get(0,1)),
        1: total/(2*dist.get(1,1))
    }

    tscv = TimeSeriesSplit(n_splits=5)

    for train_idx, test_idx in tscv.split(X):
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            random_state=42,
            class_weight=weights
        )
        model.fit(X.iloc[train_idx], y.iloc[train_idx])

    # treino final
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        random_state=42,
        class_weight=weights
    )
    model.fit(X,y)

    joblib.dump({
        'modelo': model,
        'features': features
    }, 'modelo_chuva.pkl')

    print("✅ Modelo treinado e salvo!")

# ----------------------------
if __name__ == "__main__":
    treinar_modelo()