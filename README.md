# 🌧️ Dashboard Inteligente de Chuva - Maceió

Projeto de monitoramento inteligente de chuva e risco de desastres em Maceió, utilizando IoT, MQTT e **Inteligência Artificial** com Machine Learning.

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Nenhuma outra dependência necessária!

## 🚀 Como Rodar com Docker

### 1. Inicie todos os serviços

```bash
docker-compose up -d
```

Isso vai iniciar:

- ✅ Broker MQTT (Mosquitto) - porta `1883`
- ✅ Sensor de dados - coleta e publica dados via MQTT
- ✅ Dashboard Streamlit - acesso em `http://localhost:8501`

### 2. Acesse o Dashboard

Abra no navegador: **http://localhost:8501**

O dashboard começará a exibir dados em tempo real com predições de IA.

## 🤖 Sistema de Inteligência Artificial

### Modelo de Machine Learning

- **Algoritmo**: Random Forest Classifier
- **Acurácia**: ~96% em dados de teste
- **Features utilizadas**:
  - 🌡️ Temperatura (°C)
  - 💧 Umidade relativa (%)
  - 📊 Pressão atmosférica (hPa)
  - 🌬️ Velocidade do vento (km/h)
  - 🕐 Hora do dia
  - 📍 Local da medição
  - 📅 Dia da semana

### Como Funciona

1. **Coleta de Dados**: Sensor coleta umidade, localização e dia da semana
2. **Estimativa de Features**: Sistema estima temperatura, pressão e vento (valores típicos de Recife)
3. **Predição IA**: Modelo calcula probabilidade de chuva em tempo real
4. **Classificação de Risco**: Combina predição IA + vulnerabilidade local

### Exemplo de Predições

```
🤖 IA: Boa Viagem - Probabilidade de chuva: 83.7% → ALTO
🤖 IA: Casa Amarela - Probabilidade de chuva: 27.5% → BAIXO
🤖 IA: Ibura - Probabilidade de chuva: 55.1% → ALTO (local vulnerável)
```

## 📦 Estrutura do Projeto

- **sensor.py** - Coleta dados reais/simulados da API APAC e publica via MQTT
- **dashboard_web.py** - **Interface Streamlit com modelo de IA integrado**
- **train_model.py** - Script para treinar/retreinar o modelo de IA
- **modelo_chuva.pkl** - Arquivo do modelo treinado (Random Forest)
- **docker-compose.yml** - Orquestração dos serviços
- **Dockerfile.sensor** - Imagem Docker para o sensor
- **Dockerfile.dashboard** - Imagem Docker para o dashboard
- **mosquitto.conf** - Configuração do broker MQTT
- **requirements.txt** - Dependências Python (incluindo scikit-learn)

## 🎯 Predições em Tempo Real

### Métricas no Dashboard

- 🌧️ Última Chuva registrada
- 💧 Umidade percentual
- 📅 Dia da semana
- 🤖 **Probabilidade de chuva** calculada por IA

### Classificação de Risco

O sistema combina:

- **Predição de IA** (probabilidade de chuva)
- **Fatores locais** (vulnerabilidade de cada bairro)

**Resultado Final:**

- **BAIXO**: Probabilidade < 30% + baixo risco local
- **MÉDIO**: Probabilidade 30-60% + médio risco local
- **ALTO**: Probabilidade > 60% + alto risco local

## 🏘️ Regiões Monitoradas

- **Boa Viagem** - Litoral, alta probabilidade de chuva
- **Casa Amarela** - Interior, menor probabilidade
- **Várzea** - Área baixa, médio risco
- **Ibura** - Litoral, **alto risco de alagamento**
- **Afogados** - Médio risco
- **Centro** - Área urbana

## 🔄 Retreinamento do Modelo

Para melhorar o modelo com novos dados:

```bash
# Executar treinamento
python3 train_model.py

# Reconstruir containers
docker-compose down
docker-compose up -d --build
```

## 📊 Análises Disponíveis

### Dados em Tempo Real

- Histórico dos últimos 10 registros
- Gráfico de chuva ao longo do tempo
- Mapa de risco por região (BAIXO/MÉDIO/ALTO)

### Alertas Inteligentes

- 🚨 Regiões com risco ALTO
- 📍 Maior risco atual
- 🏆 Ranking de regiões por alertas
- 📈 Tendência de chuva (aumento/estável)

## 🐛 Troubleshooting

### Modelo não carrega

```bash
# Verificar se arquivo existe
ls -la modelo_chuva.pkl

# Retreinar modelo
python3 train_model.py
```

### Dashboard não conecta MQTT

```bash
# Verificar logs
docker-compose logs dashboard

# Reiniciar serviços
docker-compose restart
```

### Baixa acurácia

- Modelo usa dados sintéticos para demonstração
- Para produção: coletar dados reais históricos
- Retreinar com `python3 train_model.py`

## 🎓 Sobre o Modelo de IA

### Dataset de Treinamento

- **15.000 amostras** sintéticas baseadas em padrões reais
- **Features**: temperatura, umidade, pressão, vento, hora, local, dia
- **Target**: vai_chover (0/1)

### Algoritmo Random Forest

- **Estimators**: 100 árvores
- **Max Depth**: 10 níveis
- **Balanceamento**: classe_weight='balanced'

### Importância das Features

1. 📊 Pressão atmosférica (46.8%)
2. 💧 Umidade (31.5%)
3. 🌡️ Temperatura (19.0%)
4. 🌬️ Vento, hora, local, dia (< 5% cada)

## 📂 Estrutura de Diretórios

```
projetoSensoriamento/
├── sensor.py              # Script do sensor
├── dashboard_web.py       # 🤖 Dashboard com IA integrada
├── train_model.py         # Script de treinamento
├── modelo_chuva.pkl       # Modelo treinado (2.8MB)
├── requirements.txt      # Dependências + scikit-learn
├── docker-compose.yml    # Orquestração Docker
├── Dockerfile.sensor     # Imagem do sensor
├── Dockerfile.dashboard  # Imagem do dashboard
├── mosquitto.conf        # Config MQTT
└── README.md            # Este arquivo
```

---

**🚀 Projeto com IA totalmente integrada e simplificada!**
