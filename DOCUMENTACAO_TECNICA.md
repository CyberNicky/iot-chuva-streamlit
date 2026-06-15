# Documentação Técnica da Aplicação

## 1. Visão geral

Esta aplicação é um sistema de sensoriamento climático em tempo real para bairros de Maceió/AL. O projeto simula um fluxo de Internet das Coisas (IoT), no qual um sensor coleta dados climáticos, publica essas informações em um broker MQTT e um dashboard web recebe e apresenta os dados ao usuário.

O sistema é composto por três partes principais:

1. **Sensor Python (`sensor.py`)**: busca bairros de Maceió, consulta dados climáticos da API Open-Meteo e publica mensagens MQTT.
2. **Broker MQTT Mosquitto (`mosquitto`)**: recebe as mensagens publicadas pelo sensor e distribui para clientes inscritos no tópico.
3. **Dashboard Streamlit (`dashboard_web.py`)**: assina o tópico MQTT, recebe as mensagens, armazena um histórico recente e exibe indicadores, última leitura por bairro, gráficos e tabelas.

O projeto é executado com Docker Compose, o que facilita a inicialização de todos os serviços necessários.

## 2. Arquitetura da aplicação

O fluxo principal da aplicação funciona da seguinte forma:

```text
OpenStreetMap/Overpass
        |
        | busca bairros e coordenadas
        v
sensor.py --------> Open-Meteo
        |              |
        |              | retorna dados climáticos
        v
Broker MQTT Mosquitto
        |
        | tópico iot/chuva
        v
dashboard_web.py
        |
        v
Interface web Streamlit
```

Em termos práticos, o sensor percorre em sequência os bairros carregados da base do OpenStreetMap/Overpass, consulta a previsão/condição climática para as coordenadas de cada bairro na Open-Meteo e monta um pacote JSON com os dados. Esse pacote é publicado no tópico MQTT `iot/chuva`. O dashboard está inscrito nesse mesmo tópico, recebe cada mensagem, converte os dados para uma estrutura tabular e atualiza a interface web, incluindo uma tabela com a última leitura disponível de cada bairro.

## 3. Estrutura de arquivos

```text
projetoSensoriamento/
├── dashboard_web.py
├── sensor.py
├── neighborhoods.py
├── docker-compose.yml
├── Dockerfile.dashboard
├── Dockerfile.sensor
├── mosquitto.conf
├── requirements.txt
├── .gitignore
├── cache/
├── README.md
├── secao5_avaliacao_desempenho.md
└── DOCUMENTACAO_TECNICA.md
```

### 3.1 `sensor.py`

Arquivo responsável por atuar como o sensor/publicador do sistema. Ele carrega os bairros, consulta a API climática e envia os dados para o broker MQTT.

### 3.2 `dashboard_web.py`

Arquivo responsável pelo dashboard web. Ele se conecta ao broker MQTT, recebe as mensagens publicadas pelo sensor e exibe os dados em uma interface Streamlit.

### 3.3 `neighborhoods.py`

Arquivo auxiliar usado para buscar dinamicamente os bairros de Maceió no OpenStreetMap/Overpass. Ele retorna um dicionário com nome do bairro e suas coordenadas.

### 3.4 `docker-compose.yml`

Arquivo de orquestração dos containers. Define os serviços `mosquitto`, `sensor` e `dashboard`, suas portas, variáveis de ambiente e dependências.

### 3.5 `Dockerfile.sensor`

Define a imagem Docker usada pelo serviço do sensor.

### 3.6 `Dockerfile.dashboard`

Define a imagem Docker usada pelo serviço do dashboard Streamlit.

### 3.7 `mosquitto.conf`

Arquivo de configuração do broker Mosquitto.

### 3.8 `requirements.txt`

Lista as dependências Python do projeto.

### 3.9 `.gitignore`

Define arquivos e pastas que não devem ser enviados para o GitHub, como ambiente virtual, caches Python e a pasta local `cache/`.

### 3.10 `cache/`

Pasta local usada para armazenar o cache de bairros gerado em tempo de execução. Ela é ignorada pelo Git, pois pode ser recriada automaticamente pela aplicação.

### 3.11 `README.md`

Contém instruções gerais de uso, execução e descrição resumida do projeto.

### 3.12 `secao5_avaliacao_desempenho.md`

Arquivo com a seção de avaliação de desempenho escrita para o artigo.

## 4. Funcionamento do `sensor.py`

O arquivo `sensor.py` é o publicador MQTT. Ele executa continuamente e envia dados climáticos em intervalos configuráveis.

### 4.1 Importações

```python
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Union
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
import requests

from neighborhoods import Neighborhoods, format_neighborhoods, load_neighborhoods
```

As bibliotecas utilizadas têm os seguintes papéis:

| Biblioteca | Uso |
| --- | --- |
| `json` | Converter o pacote climático para JSON antes da publicação MQTT |
| `os` | Ler variáveis de ambiente |
| `time` | Controlar pausas entre tentativas e publicações |
| `datetime` | Gerar timestamp da leitura |
| `ZoneInfo` | Aplicar o fuso horário de Maceió |
| `paho.mqtt.client` | Conectar e publicar mensagens MQTT |
| `requests` | Fazer requisições HTTP para a API Open-Meteo |
| `neighborhoods` | Carregar e formatar bairros vindos do Overpass |

### 4.2 Configurações globais

```python
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot/chuva")
MQTT_RETAIN = os.getenv("MQTT_RETAIN", "true").lower() == "true"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Maceio")
```

Essas constantes configuram a conexão MQTT e o fuso horário da aplicação. Os valores podem ser definidos por variáveis de ambiente no `docker-compose.yml`. Caso nenhuma variável seja informada, o código usa valores padrão.

```python
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PUBLISH_INTERVAL_SECONDS = int(os.getenv("PUBLISH_INTERVAL_SECONDS", "60"))
```

Essas constantes definem a API climática usada e o intervalo entre publicações. No Docker Compose, esse intervalo foi configurado como 5 segundos para facilitar a demonstração e preencher a tabela de bairros mais rapidamente.

```python
MAX_MQTT_RETRIES = 10
MQTT_RETRY_DELAY_SECONDS = 2
MAX_NEIGHBORHOOD_RETRIES = 10
NEIGHBORHOOD_RETRY_DELAY_SECONDS = 5
```

Esses valores controlam as tentativas de reconexão ao MQTT e as tentativas de carregamento dos bairros. Isso evita que a aplicação falhe imediatamente caso algum serviço demore a responder.

### 4.3 Tipo `WeatherPayload`

```python
WeatherPayload = Dict[str, Union[float, int, str]]
```

Esse tipo representa o formato geral do pacote climático publicado pelo sensor. O pacote contém valores numéricos, como temperatura e umidade, e valores textuais, como bairro e timestamp.

### 4.4 Dicionário `WEEKDAYS_PT`

```python
WEEKDAYS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    ...
}
```

Esse dicionário converte o número do dia da semana retornado pelo Python para texto em português.

### 4.5 Função `connect_mqtt`

```python
def connect_mqtt() -> mqtt.Client:
```

Essa função cria um cliente MQTT e tenta conectá-lo ao broker configurado. Ela faz até 10 tentativas, aguardando 2 segundos entre cada uma. Se a conexão for bem-sucedida, retorna o cliente conectado. Caso todas as tentativas falhem, lança um erro.

Essa função é importante porque, em ambientes com Docker Compose, o container do sensor pode iniciar antes de o broker estar totalmente pronto. As retentativas reduzem esse problema.

### 4.6 Função `load_dynamic_neighborhoods`

```python
def load_dynamic_neighborhoods() -> Neighborhoods:
```

Essa função chama `load_neighborhoods`, definida em `neighborhoods.py`, para buscar os bairros de Maceió. Assim como a conexão MQTT, ela também usa retentativas. Se a API Overpass falhar temporariamente, o sensor tenta novamente.

Quando a busca funciona, a função imprime no terminal todos os bairros carregados com suas coordenadas.

### 4.7 Função `build_open_meteo_params`

```python
def build_open_meteo_params(latitude: float, longitude: float) -> Dict[str, Union[str, float, bool]]:
```

Essa função monta os parâmetros enviados para a API Open-Meteo. Ela recebe latitude e longitude e retorna um dicionário com:

| Parâmetro | Finalidade |
| --- | --- |
| `latitude` | Latitude do bairro |
| `longitude` | Longitude do bairro |
| `current_weather` | Solicita dados meteorológicos atuais |
| `hourly` | Solicita séries horárias de temperatura, umidade, pressão, precipitação e vento |
| `timezone` | Define o fuso horário da resposta |

### 4.8 Função `find_current_hour_index`

```python
def find_current_hour_index(hourly: Dict[str, list], current_time: Optional[str]) -> int:
```

A API Open-Meteo retorna listas de valores por horário. Essa função encontra qual posição da lista corresponde à hora atual. Para isso, ela compara o prefixo do timestamp atual com os horários disponíveis na resposta.

Se não encontrar uma correspondência, retorna o índice `0` como fallback.

### 4.9 Função `sum_precipitation`

```python
def sum_precipitation(hourly: Dict[str, list], start_index: int, hours: int) -> float:
```

Essa função soma a precipitação prevista nas próximas horas a partir do índice horário atual. Ela é usada para calcular a previsão acumulada de chuva para as próximas 1h, 3h e 6h.

A previsão não é calculada por um modelo próprio do projeto. Ela vem do campo horário `precipitation` retornado pela Open-Meteo; o sistema apenas identifica a hora atual e soma os próximos valores da série para obter os acumulados de 1h, 3h e 6h.

No dashboard, esses valores aparecem como `Chuva prevista 1h (mm)`, `Chuva prevista 3h (mm)` e `Chuva prevista 6h (mm)`. A unidade `mm` significa milímetros de chuva acumulada.

### 4.10 Função `fetch_weather`

```python
def fetch_weather(neighborhood: str, latitude: float, longitude: float) -> Optional[WeatherPayload]:
```

Essa é uma das funções centrais do sensor. Ela realiza os seguintes passos:

1. Recebe o nome, a latitude e a longitude de um bairro.
2. Consulta a API Open-Meteo para essas coordenadas.
3. Localiza os dados correspondentes à hora atual.
4. Calcula a previsão acumulada de chuva para as próximas 1h, 3h e 6h.
5. Monta um dicionário com os dados climáticos.

O pacote retornado possui a seguinte estrutura:

```json
{
  "temperatura": 26.9,
  "umidade": 78.0,
  "pressao": 1014.6,
  "vento_velocidade": 16.4,
  "chuva": 0.1,
  "previsao_chuva_1h": 0.2,
  "previsao_chuva_3h": 0.4,
  "previsao_chuva_6h": 0.8,
  "local": "Jaraguá",
  "latitude": -9.6758227,
  "longitude": -35.7240256,
  "fonte_localizacao": "OpenStreetMap/Overpass",
  "fonte_clima": "Open-Meteo",
  "dia_semana": "segunda-feira",
  "hora": 14,
  "timestamp": "2026-06-15 14:35:27"
}
```

Se a API climática falhar ou retornar uma estrutura inesperada, a função retorna `None`, evitando que uma mensagem inválida seja publicada.

### 4.11 Função `publish_weather`

```python
def publish_weather(client: mqtt.Client, payload: WeatherPayload) -> bool:
```

Essa função recebe o cliente MQTT e o pacote climático, converte o pacote para JSON e publica no tópico configurado. O parâmetro `retain` indica se o broker deve manter a última mensagem publicada. No projeto, ele é configurado como `true`, permitindo que o dashboard receba a última leitura ao se conectar.

A função também verifica o código de retorno da publicação MQTT. Se o cliente MQTT indicar falha, o erro é registrado no log e a função retorna `False`; caso contrário, retorna `True`.

### 4.12 Função `run`

```python
def run() -> None:
```

Essa função coordena todo o ciclo do sensor:

1. Carrega os bairros.
2. Conecta ao broker MQTT.
3. Entra em um loop infinito.
4. Percorre todos os bairros em ordem.
5. Busca uma nova leitura climática para o bairro atual.
6. Publica a leitura, caso seja válida.
7. Aguarda o intervalo configurado antes de avançar para o próximo bairro.

### 4.13 Bloco principal

```python
if __name__ == "__main__":
    run()
```

Esse bloco faz com que o sensor seja iniciado quando o arquivo `sensor.py` é executado diretamente.

## 5. Funcionamento do `neighborhoods.py`

O arquivo `neighborhoods.py` concentra a lógica de busca, limpeza e organização dos bairros de Maceió.

### 5.1 Tipos auxiliares

```python
Coordinates = Tuple[float, float]
Neighborhoods = Dict[str, Coordinates]
```

`Coordinates` representa um par de latitude e longitude. `Neighborhoods` representa um dicionário em que a chave é o nome do bairro e o valor é o par de coordenadas.

### 5.2 Configurações da API Overpass

```python
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
CITY_NAME = os.getenv("CITY_NAME", "Maceió")
STATE_NAME = os.getenv("STATE_NAME", "Alagoas")
COUNTRY_NAME = os.getenv("COUNTRY_NAME", "Brasil")
```

Essas variáveis definem onde buscar os dados e qual cidade deve ser consultada.

```python
OVERPASS_TIMEOUT_SECONDS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "30"))
NEIGHBORHOOD_CACHE_FILE = Path(os.getenv("NEIGHBORHOOD_CACHE_FILE", "neighborhoods_cache.json"))
```

`OVERPASS_TIMEOUT_SECONDS` define o tempo máximo da consulta ao Overpass. `NEIGHBORHOOD_CACHE_FILE` define onde a lista de bairros será salva em cache depois de uma busca bem-sucedida.

### 5.3 Prefixos ignorados

```python
IGNORED_NAME_PREFIXES = (
    "Condomínio ",
    "Conjunto ",
    "Loteamento ",
    "Village ",
)
```

Alguns nomes retornados pelo OpenStreetMap podem representar condomínios, loteamentos ou conjuntos, e não bairros propriamente ditos. Esses prefixos são usados para filtrar esse tipo de resultado.

### 5.4 Função `build_overpass_query`

```python
def build_overpass_query() -> str:
```

Essa função monta a consulta na linguagem Overpass QL. A consulta procura, dentro da área administrativa de Maceió, elementos classificados como `neighbourhood`, `suburb` ou `quarter`, além de algumas fronteiras administrativas menores.

O resultado solicitado inclui centro e tags dos elementos, o que permite obter nome e coordenadas dos bairros.

### 5.5 Função `get_element_coordinates`

```python
def get_element_coordinates(element: dict) -> Coordinates:
```

Essa função extrai as coordenadas de um elemento retornado pela API. Se o elemento possuir diretamente `lat` e `lon`, esses valores são usados. Caso contrário, a função tenta usar o campo `center`.

Isso é necessário porque o Overpass pode retornar diferentes tipos de elementos, como nós, caminhos e relações.

### 5.6 Função `is_valid_neighborhood_name`

```python
def is_valid_neighborhood_name(name: str) -> bool:
```

Essa função verifica se o nome encontrado deve ser aceito. Ela rejeita:

- nomes vazios;
- nomes iguais à cidade, ao estado ou ao país;
- nomes iniciados com prefixos ignorados, como `Condomínio` ou `Loteamento`.

### 5.7 Função `normalize_neighborhood_name`

```python
def normalize_neighborhood_name(name: str) -> str:
```

Essa função limpa o nome do bairro. Se o nome começar com `Bairro `, esse prefixo é removido. Por exemplo, `Bairro Farol` vira apenas `Farol`.

### 5.8 Função `load_cached_neighborhoods`

```python
def load_cached_neighborhoods() -> Neighborhoods:
```

Essa função tenta carregar a lista de bairros a partir do arquivo de cache local. Se o arquivo não existir ou estiver inválido, retorna um dicionário vazio.

### 5.9 Função `save_cached_neighborhoods`

```python
def save_cached_neighborhoods(neighborhoods: Neighborhoods) -> None:
```

Essa função salva os bairros carregados em um arquivo JSON. O cache reduz a dependência da API Overpass em execuções futuras e permite continuar usando a última lista válida caso a API externa falhe temporariamente.

### 5.10 Função `load_neighborhoods`

```python
def load_neighborhoods() -> Neighborhoods:
```

Essa é a função principal do arquivo. Ela:

1. Envia uma requisição POST para a API Overpass.
2. Recebe a resposta em JSON.
3. Percorre os elementos retornados.
4. Extrai o nome de cada bairro.
5. Normaliza e valida o nome.
6. Extrai as coordenadas.
7. Armazena o bairro em um dicionário.
8. Salva os bairros em cache local.
9. Retorna os bairros ordenados por nome.

Caso algum elemento venha incompleto ou com coordenadas inválidas, ele é ignorado. Se a consulta ao Overpass falhar, a função tenta carregar os bairros do cache local.

### 5.11 Função `format_neighborhoods`

```python
def format_neighborhoods(neighborhoods: Neighborhoods) -> List[str]:
```

Essa função formata os bairros para exibição no terminal. Ela retorna uma lista de strings no formato:

```text
Nome do bairro (latitude, longitude)
```

## 6. Funcionamento do `dashboard_web.py`

O arquivo `dashboard_web.py` implementa a interface web e a lógica de recebimento MQTT.

### 6.1 Importações

```python
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
```

As principais bibliotecas usadas são:

| Biblioteca | Uso |
| --- | --- |
| `json` | Interpretar mensagens JSON recebidas via MQTT |
| `os` | Ler variáveis de ambiente |
| `deque` | Guardar histórico limitado de mensagens |
| `dataclass` | Criar estrutura para o runtime MQTT |
| `Lock` | Proteger acesso ao histórico em ambiente com thread MQTT |
| `pandas` | Criar e manipular tabelas de dados |
| `paho.mqtt.client` | Conectar ao broker e receber mensagens |
| `streamlit` | Criar a interface web |

### 6.2 Configurações globais

```python
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot/chuva")
```

Essas variáveis definem a conexão MQTT do dashboard.

```python
MAX_HISTORY_ROWS = 500
RECENT_HISTORY_ROWS = 24
AUTO_REFRESH_SECONDS = 2
```

Essas constantes definem:

| Constante | Significado |
| --- | --- |
| `MAX_HISTORY_ROWS` | Quantidade máxima de mensagens guardadas em memória |
| `RECENT_HISTORY_ROWS` | Quantidade de registros usados para cálculos recentes |
| `AUTO_REFRESH_SECONDS` | Intervalo de atualização automática da tela |

### 6.3 Colunas de dados

```python
TABLE_COLUMNS = [...]
DATA_COLUMNS = {...}
```

`TABLE_COLUMNS` define as colunas exibidas na tabela de histórico. `DATA_COLUMNS` define o mapeamento entre os nomes internos usados pelo código e os nomes amigáveis exibidos no dashboard.

### 6.4 Classe `MqttRuntime`

```python
@dataclass
class MqttRuntime:
    client: mqtt.Client
    history: Deque[Dict[str, Any]]
    lock: Lock
```

Essa classe agrupa os objetos necessários para a execução MQTT:

- `client`: cliente MQTT conectado ao broker;
- `history`: fila com o histórico das mensagens recebidas;
- `lock`: mecanismo de proteção para evitar acesso simultâneo inseguro ao histórico.

O `Lock` é importante porque o MQTT recebe mensagens em uma thread separada, enquanto o Streamlit renderiza a interface na thread principal.

### 6.5 Função `configure_page`

```python
def configure_page() -> None:
```

Configura a página Streamlit com título, ícone, layout largo e texto introdutório.

### 6.6 Função `parse_float`

```python
def parse_float(data: Dict[str, Any], key: str, default: float) -> float:
```

Essa função tenta converter um campo para `float`. Se o valor estiver ausente ou inválido, retorna um valor padrão. Isso evita que o dashboard quebre ao receber uma mensagem incompleta.

### 6.7 Função `parse_message`

```python
def parse_message(payload: bytes) -> Dict[str, Any]:
```

Essa função recebe o conteúdo bruto da mensagem MQTT, decodifica o JSON e transforma os campos no formato interno usado pelo dashboard.

Ela converte, por exemplo:

| Campo recebido | Campo interno |
| --- | --- |
| `temperatura` | `temp` |
| `vento_velocidade` | `vento` |
| `previsao_chuva_1h` | `previsao_chuva_1h` |
| `previsao_chuva_3h` | `previsao_chuva_3h` |
| `previsao_chuva_6h` | `previsao_chuva_6h` |
| `timestamp` | `timestamp` |
| `local` | `local` |

Também mantém o JSON original no campo `raw`, que depois é exibido no dashboard como “Último pacote MQTT recebido”.

### 6.8 Função `on_message`

```python
def on_message(client: mqtt.Client, runtime: MqttRuntime, message: mqtt.MQTTMessage) -> None:
```

Essa função é chamada automaticamente sempre que uma mensagem MQTT chega. Ela:

1. Chama `parse_message`.
2. Adiciona a mensagem convertida ao histórico.
3. Usa `runtime.lock` para proteger a alteração.
4. Imprime a mensagem recebida nos logs.

Se a mensagem vier com JSON inválido, o erro é capturado e registrado no terminal.

### 6.9 Função `get_mqtt_runtime`

```python
@st.cache_resource
def get_mqtt_runtime() -> MqttRuntime:
```

Essa função cria e configura a conexão MQTT do dashboard. Ela:

1. Cria o cliente MQTT.
2. Cria o `MqttRuntime`.
3. Associa o runtime ao cliente com `user_data_set`.
4. Define `on_message` como callback.
5. Tenta conectar ao broker.
6. Assina o tópico `iot/chuva`.
7. Inicia o loop MQTT em segundo plano.

O decorador `@st.cache_resource` evita que uma nova conexão MQTT seja criada a cada atualização do Streamlit.

### 6.10 Função `get_history_rows`

```python
def get_history_rows(runtime: MqttRuntime) -> List[Dict[str, Any]]:
```

Essa função copia o histórico de mensagens de forma segura e converte cada mensagem para um dicionário com os nomes das colunas que serão exibidas no dashboard.

### 6.11 Função `build_dataframe`

```python
def build_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
```

Essa função transforma a lista de mensagens em um `DataFrame` do Pandas. Também converte a coluna `Data/Hora` para tipo de data e remove registros com timestamp inválido.

### 6.12 Função `classify_status`

```python
def classify_status(rain: float, wind: float, humidity: float) -> str:
```

Centraliza as regras de classificação climática. Essa função evita repetição de lógica no dashboard, pois tanto a classificação da última leitura por bairro quanto a classificação da situação geral usam os mesmos limites de chuva, vento e umidade.

### 6.13 Função `describe_rain_condition`

```python
def describe_rain_condition(row: pd.Series) -> str:
```

Converte os valores numéricos de chuva em uma mensagem simples para o usuário. Em vez de mostrar apenas valores em milímetros, o dashboard também exibe interpretações como `Chuva fraca agora`, `Pode chover em breve`, `Pode chover nas próximas 3h` ou `Sem chuva prevista`.

Essa função ajuda usuários não técnicos a entenderem se está chovendo no momento, se pode chover nas próximas horas ou se não há chuva prevista.

### 6.14 Função `classify_latest_row`

```python
def classify_latest_row(row: pd.Series) -> str:
```

Classifica a última leitura de um bairro específico. A regra considera a chuva observada, a previsão de chuva para a próxima hora, o vento e a umidade. Chuva igual ou superior a 3 mm, previsão de chuva da próxima hora igual ou superior a 3 mm ou vento igual ou superior a 45 km/h gera `Alerta`; chuva maior que 0 mm, previsão de chuva maior que 0 mm ou umidade igual ou superior a 80% gera `Atenção`; caso contrário, o status é `Normal`.

### 6.15 Função `build_latest_by_neighborhood`

```python
def build_latest_by_neighborhood(dataframe: pd.DataFrame) -> pd.DataFrame:
```

Monta uma tabela consolidada com apenas a leitura mais recente de cada bairro. Para isso, ordena os dados por data/hora, remove leituras antigas mantendo a última ocorrência de cada local e adiciona as colunas `Status` e `Interpretação da chuva`.

Essa função é o que permite transformar o projeto em uma ferramenta de consulta por bairro, pois o usuário passa a enxergar a condição mais recente disponível para cada local já percorrido pelo sensor.

### 6.16 Função `render_filters`

```python
def render_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
```

Renderiza o filtro de bairro no dashboard. O usuário pode escolher:

- todos os bairros;
- um bairro específico entre os que já apareceram nas mensagens recebidas.

A função retorna o DataFrame filtrado.

### 6.17 Função `classify_conditions`

```python
def classify_conditions(latest: pd.Series, recent: pd.DataFrame) -> Dict[str, str]:
```

Classifica a situação atual com base nos registros recentes. As regras são:

| Condição | Status |
| --- | --- |
| Chuva recente ou previsão da próxima hora maior ou igual a 3 mm, ou vento maior ou igual a 45 km/h | `Alerta` |
| Chuva recente ou previsão da próxima hora maior que 0 mm, ou umidade maior ou igual a 80% | `Atenção` |
| Nenhuma das condições anteriores | `Normal` |

A função retorna o status, um ícone e uma mensagem explicativa.

### 6.18 Função `get_attention_neighborhood`

```python
def get_attention_neighborhood(recent: pd.DataFrame) -> str:
```

Agrupa os registros recentes por bairro, soma a chuva e identifica o bairro com maior atenção, priorizando chuva acumulada e vento.

### 6.19 Função `get_windiest_neighborhood`

```python
def get_windiest_neighborhood(recent: pd.DataFrame) -> str:
```

Agrupa os registros recentes por bairro e retorna aquele com maior velocidade de vento registrada.

### 6.20 Função `render_conditions`

```python
def render_conditions(dataframe: pd.DataFrame, latest: pd.Series) -> None:
```

Renderiza a seção “Situação atual”. Ela exibe:

- status geral;
- chuva recente;
- bairro em atenção;
- maior vento;
- mensagem de interpretação.

### 6.21 Função `render_summary`

```python
def render_summary(latest: pd.Series) -> None:
```

Renderiza o resumo da última leitura recebida. Mostra temperatura, umidade, `Chuva agora (mm)`, `Chuva prevista 3h (mm)`, vento, bairro, horário, dia da semana, pressão e uma mensagem de interpretação da chuva.

### 6.22 Função `render_latest_by_neighborhood`

```python
def render_latest_by_neighborhood(dataframe: pd.DataFrame) -> None:
```

Renderiza no dashboard a tabela “Última leitura por bairro”. Essa seção mostra a condição mais recente de cada bairro, incluindo status, interpretação da chuva, data/hora, temperatura, umidade, pressão, `Chuva agora (mm)`, `Chuva prevista 1h (mm)`, `Chuva prevista 3h (mm)`, `Chuva prevista 6h (mm)` e vento.

### 6.23 Função `render_charts`

```python
def render_charts(dataframe: pd.DataFrame) -> None:
```

Renderiza os gráficos de tendência dos registros recentes. São exibidos:

- gráfico de temperatura e umidade;
- gráfico de `Chuva agora (mm)`, `Chuva prevista 3h (mm)` e vento.

### 6.24 Função `render_history`

```python
def render_history(dataframe: pd.DataFrame, latest: pd.Series) -> None:
```

Renderiza a tabela com os 20 registros mais recentes e também exibe o último pacote MQTT bruto em JSON.

### 6.25 Função `render_dashboard`

```python
def render_dashboard(runtime: MqttRuntime) -> None:
```

Essa função organiza a renderização completa do dashboard. Ela:

1. Obtém as mensagens do histórico.
2. Mostra aviso caso ainda não haja dados.
3. Cria o DataFrame.
4. Renderiza a tabela de última leitura por bairro.
5. Aplica filtro de bairro.
6. Seleciona a última leitura.
7. Renderiza resumo, situação atual, gráficos e histórico.

### 6.26 Função `main`

```python
def main() -> None:
```

Função principal do dashboard. Ela configura a página, inicializa o runtime MQTT, renderiza o dashboard, aguarda 2 segundos e força a atualização da tela com `st.rerun()`.

### 6.27 Chamada final

```python
main()
```

Inicia o dashboard quando o arquivo é executado pelo Streamlit.

## 7. Funcionamento do Docker

O projeto usa Docker para executar os serviços de forma isolada e reproduzível.

### 7.1 Serviço `mosquitto`

```yaml
mosquitto:
  image: eclipse-mosquitto:latest
  container_name: mqtt-broker
  ports:
    - "1883:1883"
    - "9001:9001"
  volumes:
    - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
  restart: always
```

Esse serviço executa o broker MQTT. Ele expõe:

- porta `1883` para comunicação MQTT;
- porta `9001` para comunicação MQTT via WebSocket.

O arquivo `mosquitto.conf` local é montado dentro do container para configurar o broker.

### 7.2 Serviço `sensor`

```yaml
sensor:
  build:
    context: .
    dockerfile: Dockerfile.sensor
  container_name: sensor-publisher
  depends_on:
    - mosquitto
```

Esse serviço constrói uma imagem a partir de `Dockerfile.sensor` e executa o sensor Python.

Principais variáveis de ambiente:

| Variável | Valor | Função |
| --- | --- | --- |
| `APP_TIMEZONE` | `America/Maceio` | Define o fuso horário |
| `MQTT_BROKER` | `mosquitto` | Nome do serviço MQTT dentro da rede Docker |
| `MQTT_PORT` | `1883` | Porta MQTT |
| `MQTT_TOPIC` | `iot/chuva` | Tópico onde as mensagens são publicadas |
| `MQTT_RETAIN` | `true` | Mantém última mensagem no broker |
| `PUBLISH_INTERVAL_SECONDS` | `5` | Intervalo entre a consulta/publicação de um bairro e o próximo |
| `CITY_NAME` | `Maceió` | Cidade usada na busca dos bairros |
| `STATE_NAME` | `Alagoas` | Estado usado para validação |
| `COUNTRY_NAME` | `Brasil` | País usado para validação |
| `OVERPASS_URL` | URL da Overpass | Endpoint de busca geográfica |
| `NEIGHBORHOOD_CACHE_FILE` | `/app/cache/neighborhoods_cache.json` | Arquivo usado para salvar e reutilizar o cache de bairros |

### 7.3 Serviço `dashboard`

```yaml
dashboard:
  build:
    context: .
    dockerfile: Dockerfile.dashboard
  container_name: dashboard-streamlit
  ports:
    - "8501:8501"
```

Esse serviço executa o dashboard Streamlit e expõe a porta `8501`, permitindo acessar a interface em:

```text
http://localhost:8501
```

O dashboard usa as variáveis `MQTT_BROKER`, `MQTT_PORT` e `MQTT_TOPIC` para assinar o mesmo tópico em que o sensor publica.

## 8. Funcionamento dos Dockerfiles

### 8.1 `Dockerfile.sensor`

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY neighborhoods.py sensor.py .

CMD ["python", "sensor.py"]
```

Esse Dockerfile:

1. Usa uma imagem leve do Python 3.10.
2. Define `/app` como diretório de trabalho.
3. Copia o arquivo de dependências.
4. Instala as dependências.
5. Copia os arquivos necessários para o sensor.
6. Executa `sensor.py`.

### 8.2 `Dockerfile.dashboard`

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard_web.py .

EXPOSE 8501

CMD ["streamlit", "run", "dashboard_web.py", "--server.address=0.0.0.0"]
```

Esse Dockerfile:

1. Usa Python 3.10 slim.
2. Instala as dependências.
3. Copia o dashboard.
4. Expõe a porta 8501.
5. Inicia o Streamlit aceitando conexões externas ao container.

## 9. Configuração do Mosquitto

O arquivo `mosquitto.conf` possui:

```text
listener 1883
protocol mqtt

listener 9001
protocol websockets

allow_anonymous true
```

Isso significa que o broker aceita conexões MQTT na porta 1883 e conexões WebSocket na porta 9001. A opção `allow_anonymous true` permite conexão sem usuário e senha, o que simplifica o ambiente acadêmico/local.

Em um ambiente real de produção, seria recomendável configurar autenticação, autorização e, se necessário, criptografia.

## 10. Dependências do projeto

O arquivo `requirements.txt` contém:

```text
paho-mqtt==1.6.1
requests==2.31.0
streamlit==1.28.1
pandas==2.1.1
```

| Dependência | Função |
| --- | --- |
| `paho-mqtt` | Cliente MQTT usado pelo sensor e pelo dashboard |
| `requests` | Requisições HTTP para OpenStreetMap/Overpass e Open-Meteo |
| `streamlit` | Framework usado para criar a interface web |
| `pandas` | Manipulação dos dados recebidos e criação de tabelas |

## 11. Formato das mensagens MQTT

As mensagens publicadas no tópico `iot/chuva` são JSONs com dados climáticos e metadados.

Exemplo:

```json
{
  "temperatura": 26.9,
  "umidade": 78.0,
  "pressao": 1014.6,
  "vento_velocidade": 16.4,
  "chuva": 0.1,
  "previsao_chuva_1h": 0.2,
  "previsao_chuva_3h": 0.4,
  "previsao_chuva_6h": 0.8,
  "local": "Jaraguá",
  "latitude": -9.6758227,
  "longitude": -35.7240256,
  "fonte_localizacao": "OpenStreetMap/Overpass",
  "fonte_clima": "Open-Meteo",
  "dia_semana": "segunda-feira",
  "hora": 14,
  "timestamp": "2026-06-15 14:35:27"
}
```

O dashboard usa esses campos para montar a tabela, os cards e os gráficos.

## 12. Regras de classificação climática

O dashboard possui uma regra simples para classificar a situação atual:

| Regra | Status exibido |
| --- | --- |
| Chuva recente maior ou igual a 3 mm | `Alerta` |
| Previsão de chuva da próxima hora maior ou igual a 3 mm | `Alerta` |
| Vento maior ou igual a 45 km/h | `Alerta` |
| Chuva recente maior que 0 mm | `Atenção` |
| Previsão de chuva da próxima hora maior que 0 mm | `Atenção` |
| Umidade maior ou igual a 80% | `Atenção` |
| Nenhuma condição relevante | `Normal` |

Essas regras estão implementadas na função `classify_conditions`.

## 13. Como executar a aplicação

Para iniciar todos os serviços:

```bash
docker compose up -d --build
```

Para verificar se os containers estão em execução:

```bash
docker compose ps
```

Para acessar o dashboard:

```text
http://localhost:8501
```

Para acompanhar os logs:

```bash
docker compose logs -f sensor dashboard
```

Para parar a aplicação:

```bash
docker compose down
```

## 14. Pontos fortes da implementação

O sistema possui uma arquitetura simples e coerente com aplicações IoT. O uso de MQTT é adequado porque permite comunicação leve entre produtor e consumidor de dados. A separação entre sensor, broker e dashboard facilita manutenção e testes. Além disso, o Docker Compose torna o ambiente fácil de reproduzir.

Outro ponto positivo é a busca dinâmica de bairros. Em vez de manter uma lista fixa no código, o sistema consulta o OpenStreetMap/Overpass, obtendo nomes e coordenadas atualizados. Após a primeira busca bem-sucedida, a lista é salva em cache local, reduzindo a dependência da API geográfica em execuções futuras. O dashboard também apresenta informações em diferentes formatos, como cards, previsão de chuva para as próximas horas, gráficos, tabela histórica e JSON bruto.

## 15. Limitações e possíveis melhorias

Apesar de funcional, a aplicação depende de APIs externas. Se a Open-Meteo estiver indisponível, o sensor pode falhar temporariamente ou deixar de publicar novas leituras climáticas. No caso da Overpass, o projeto já reduz esse risco usando retentativas e cache local dos bairros após a primeira busca bem-sucedida.

Outra melhoria seria persistir o histórico em banco de dados. Atualmente, o dashboard mantém os dados apenas em memória. Se o container for reiniciado, o histórico é perdido. Para trabalhos futuros, poderiam ser usados SQLite, PostgreSQL, InfluxDB ou outro banco adequado para séries temporais.

Também seria possível adicionar autenticação ao Mosquitto, criar testes automatizados, configurar monitoramento dos containers e melhorar as regras de alerta com critérios meteorológicos mais robustos.

## 16. Resumo final

A aplicação implementa um pipeline completo de sensoriamento climático: coleta de localização, cache de bairros, consulta meteorológica, publicação MQTT, recebimento em tempo real e visualização web. O sensor busca bairros de Maceió, percorre todos em sequência, consulta a Open-Meteo, calcula previsão acumulada de chuva para as próximas 1h, 3h e 6h, publica leituras no tópico `iot/chuva`, e o dashboard Streamlit apresenta essas informações em tempo real para o usuário.

O código está dividido de forma clara: `neighborhoods.py` cuida dos bairros, `sensor.py` cuida da coleta e publicação, `dashboard_web.py` cuida da recepção e visualização, e os arquivos Docker configuram a execução da aplicação em containers.
