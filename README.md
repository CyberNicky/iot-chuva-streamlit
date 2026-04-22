# 🌧️ Dashboard Inteligente de Chuva - Recife

Projeto de monitoramento inteligente de chuva e risco de desastres em Recife, utilizando IoT, MQTT e IA.

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

O dashboard começará a exibir dados em tempo real assim que o sensor iniciar.

## 🛑 Para Parar os Serviços

```bash
docker-compose down
```

## 📦 Estrutura do Projeto

- **sensor.py** - Coleta dados reais/simulados da API APAC e publica via MQTT
- **dashboard_web.py** - Interface Streamlit que escuta MQTT e exibe dados em tempo real
- **ia_model.py** - Modelo de IA que classifica risco (BAIXO, MÉDIO, ALTO)
- **docker-compose.yml** - Orquestração dos serviços
- **Dockerfile.sensor** - Imagem Docker para o sensor
- **Dockerfile.dashboard** - Imagem Docker para o dashboard
- **mosquitto.conf** - Configuração do broker MQTT
- **requirements.txt** - Dependências Python

## 🔧 Variáveis de Ambiente

O sensor usa as seguintes variáveis (definidas automaticamente no docker-compose):

- `MQTT_BROKER` - Endereço do broker (padrão: mosquitto)
- `MQTT_PORT` - Porta do broker (padrão: 1883)

## 📊 O que Você Vai Ver

### Métricas em Tempo Real
- 🌧️ Última Chuva registrada
- 💧 Umidade percentual
- 📅 Dia da semana

### Dados em Tabela
- Histórico dos últimos 10 registros

### Análises
- 📈 Gráfico de chuva ao longo do tempo
- 🗺️ Mapa de risco por região (BAIXO, MÉDIO, ALTO)
- 📌 Região mais crítica no momento
- 🚨 Alertas gerais quando múltiplas regiões têm risco alto
- 🏆 Ranking de regiões por número de alertas
- 📈 Tendência de chuva (aumento/estável)

## 🏘️ Regiões Monitoradas

- Boa Viagem
- Casa Amarela
- Várzea
- Ibura
- Afogados
- Centro

## 🐛 Troubleshooting

### Containers não iniciam
```bash
docker-compose logs
```
Ver logs de todos os serviços.

### Dashboard não aparece em http://localhost:8501
```bash
docker-compose logs dashboard
```
Verificar logs do Streamlit.

### Sensor não conecta ao MQTT
```bash
docker-compose logs sensor
```
O sensor fará fallback para dados simulados se a API falhar.

## 🔗 Verificar Conexão MQTT

Para testar a conexão MQTT manualmente:
```bash
docker-compose exec mosquitto mosquitto_sub -t "iot/chuva" -v
```

## 📂 Estrutura de Diretórios

```
projetoSensoriamento/
├── sensor.py              # Script do sensor
├── dashboard_web.py       # Dashboard Streamlit
├── ia_model.py           # Modelo de IA
├── requirements.txt      # Dependências Python
├── docker-compose.yml    # Orquestração Docker
├── Dockerfile.sensor     # Imagem do sensor
├── Dockerfile.dashboard  # Imagem do dashboard
├── mosquitto.conf        # Config do MQTT
└── README.md            # Este arquivo
```

## 🎯 Modelo de IA

O modelo classifica o risco de desastres baseado em:
- **Chuva**: > 60mm (risco +2) ou > 30mm (risco +1)
- **Local**: Ibura (risco +2), Afogados/Várzea (risco +1)

Resultado final:
- **BAIXO**: risco ≤ 1
- **MÉDIO**: risco = 2
- **ALTO**: risco > 2
