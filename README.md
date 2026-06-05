# Dashboard de Chuva - Maceió

Projeto de monitoramento de clima em Maceió usando Open-Meteo, MQTT, Mosquitto e Streamlit.

## O que o projeto faz

1. `sensor.py` escolhe um bairro de Maceió e consulta dados climáticos na API Open-Meteo.
2. O sensor publica a leitura no tópico MQTT `iot/chuva`.
3. `dashboard_web.py` recebe as leituras e mostra métricas, gráficos e histórico recente em uma página web.

## Pré-requisitos

- Docker instalado e aberto.
- Docker Compose disponível no terminal.
- Porta `8501` livre para acessar o dashboard.

## Como rodar com Docker

### 1. Entre na pasta do projeto

```bash
cd /Users/monique/Documents/projetoSensoriamento
```

### 2. Suba todos os serviços

```bash
docker-compose up -d --build
```

Esse comando inicia:

- Mosquitto, o broker MQTT.
- Sensor, que consulta a Open-Meteo e publica dados a cada 15 segundos.
- Dashboard Streamlit, que exibe os dados na web.

### 3. Confira se está tudo rodando

```bash
docker-compose ps
```

Os serviços `mosquitto`, `sensor` e `dashboard` devem aparecer como `Up`.

### 4. Abra o dashboard no navegador

Acesse:

```text
http://localhost:8501
```

Se a página já estiver aberta, recarregue a aba depois de subir os containers.

### 5. Acompanhe os logs

```bash
docker-compose logs -f sensor dashboard
```

Você deve ver mensagens parecidas com:

```text
[SENSOR] {"temperatura": 27.3, "umidade": 70.0, ...}
Mensagem MQTT recebida: {'local': 'Ponta Verde', ...}
```

### 6. Pare o projeto quando terminar

```bash
docker-compose down
```

## Endereços usados

| Serviço | Endereço |
| --- | --- |
| Dashboard web | `http://localhost:8501` |
| MQTT | `localhost:1883` |
| MQTT WebSocket | `localhost:9001` |

## Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `APP_TIMEZONE` | `America/Maceio` | Fuso horário usado nos timestamps exibidos |
| `MQTT_BROKER` | `mosquitto` no Docker | Host do broker MQTT |
| `MQTT_PORT` | `1883` | Porta MQTT |
| `MQTT_TOPIC` | `iot/chuva` | Tópico usado para publicar e assinar leituras |
| `MQTT_RETAIN` | `true` | Mantém a última leitura no broker para o dashboard carregar imediatamente |
| `PUBLISH_INTERVAL_SECONDS` | `15` no Docker Compose | Intervalo de publicação do sensor |

## Rodar sem Docker

Use esta opção apenas se você já tiver um broker MQTT rodando localmente.

### 1. Instale as dependências

```bash
python3 -m pip install -r requirements.txt
```

### 2. Execute o sensor

```bash
MQTT_BROKER=localhost python3 sensor.py
```

### 3. Execute o dashboard

Em outro terminal:

```bash
MQTT_BROKER=localhost streamlit run dashboard_web.py
```

Depois abra:

```text
http://localhost:8501
```

## Estrutura

```text
projetoSensoriamento/
├── dashboard_web.py       # Dashboard Streamlit
├── sensor.py              # Coletor Open-Meteo e publicador MQTT
├── docker-compose.yml     # Orquestração dos serviços
├── Dockerfile.dashboard   # Imagem do dashboard
├── Dockerfile.sensor      # Imagem do sensor
├── mosquitto.conf         # Configuração do broker MQTT
├── requirements.txt       # Dependências Python
└── README.md
```
