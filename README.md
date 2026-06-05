# Dashboard de Chuva - Maceió

Projeto de monitoramento de clima em Maceió usando Open-Meteo, MQTT, Mosquitto e Streamlit.

## O que o projeto faz

1. `sensor.py` escolhe um bairro de Maceió e consulta dados climáticos na API Open-Meteo.
2. O sensor publica a leitura no tópico MQTT `iot/chuva`.
3. `dashboard_web.py` recebe as leituras e mostra métricas, gráficos e histórico recente em uma página web.

## O que aparece no dashboard

- Resumo atual com temperatura, umidade, chuva, vento, local, horário e pressão.
- Filtro para visualizar todos os bairros ou um bairro específico.
- Situação atual, com status simples (`Normal`, `Atenção` ou `Alerta`), chuva recente, bairro em atenção e maior vento.
- Tendências recentes de chuva, pressão, temperatura, umidade e vento.
- Ranking rápido de bairro com maior chuva e maior vento nos últimos registros.
- Histórico recente em tabela.
- Último pacote MQTT recebido em JSON.

## Pré-requisitos

- Docker instalado e aberto.
- Docker Compose disponível no terminal.
- Porta `8501` livre para acessar o dashboard.

## Passo a passo para rodar o projeto

### 1. Entre na pasta do projeto

```bash
cd /Users/monique/Documents/projetoSensoriamento
```

### 2. Verifique se o Docker está aberto

Antes de subir o projeto, confirme se o Docker ou OrbStack está em execução.

### 3. Suba todos os serviços

```bash
docker-compose up -d --build
```

Esse comando inicia:

- Mosquitto, o broker MQTT.
- Sensor, que consulta a Open-Meteo e publica dados a cada 15 segundos.
- Dashboard Streamlit, que exibe os dados na web.

### 4. Confira se está tudo rodando

```bash
docker-compose ps
```

Os serviços `mosquitto`, `sensor` e `dashboard` devem aparecer como `Up`.

### 5. Abra o dashboard na web

Acesse:

```text
http://localhost:8501
```

Se a página já estiver aberta, recarregue a aba depois de subir os containers.

### 6. Use o dashboard

Na página web você pode:

- acompanhar as métricas atuais de clima;
- selecionar um bairro específico no filtro `Filtrar por bairro`;
- ver condições de atenção;
- acompanhar gráficos de tendência;
- consultar o histórico recente;
- abrir o último pacote MQTT recebido em JSON.

### 7. Acompanhe os logs

```bash
docker-compose logs -f sensor dashboard
```

Você deve ver mensagens parecidas com:

```text
[SENSOR] {"temperatura": 27.3, "umidade": 70.0, ...}
Mensagem MQTT recebida: {'local': 'Ponta Verde', ...}
```

Para sair dos logs, pressione `Ctrl + C`.

### 8. Pare o projeto quando terminar

```bash
docker-compose down
```

### 9. Rode novamente depois

Quando quiser abrir o projeto outra vez, use:

```bash
docker-compose up -d
```

Depois acesse novamente:

```text
http://localhost:8501
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
├── neighborhoods.py       # Lista compartilhada de bairros monitorados
├── docker-compose.yml     # Orquestração dos serviços
├── Dockerfile.dashboard   # Imagem do dashboard
├── Dockerfile.sensor      # Imagem do sensor
├── mosquitto.conf         # Configuração do broker MQTT
├── requirements.txt       # Dependências Python
└── README.md
```

## Resumo do projeto

Este projeto simula um fluxo de monitoramento climático em tempo real para bairros de Maceió. O sensor consulta dados da Open-Meteo, publica as leituras em um broker MQTT e o dashboard Streamlit exibe essas informações em uma interface web com métricas, gráficos, filtro por bairro, histórico e condições de atenção calculadas por regras simples. A aplicação roda com Docker Compose e pode ser acessada pelo navegador em `http://localhost:8501`.

O fluxo MQTT do projeto é atualizado continuamente, pois o sensor publica novas mensagens em intervalos definidos no Docker Compose. Já os dados climáticos vêm da API Open-Meteo, então são dados meteorológicos recentes, mas não necessariamente mudam a cada requisição. Por isso, o dashboard funciona em tempo real no recebimento das mensagens, enquanto os valores da API dependem da frequência de atualização da própria Open-Meteo.
