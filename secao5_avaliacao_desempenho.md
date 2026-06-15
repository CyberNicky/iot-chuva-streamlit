# 5. Avaliação de Desempenho

Esta seção apresenta a avaliação de desempenho do sistema de monitoramento climático em tempo real para bairros de Maceió/AL. A avaliação foi organizada conforme a metodologia proposta por Raj Jain, partindo da definição do objetivo da avaliação, da descrição do ambiente experimental, da seleção das métricas e parâmetros de carga de trabalho e, por fim, da discussão dos resultados obtidos nos experimentos.

## 5.1 Objetivo da avaliação

O objetivo principal da avaliação foi verificar se a solução proposta é capaz de coletar, transmitir, receber e exibir leituras climáticas de forma contínua por meio de uma arquitetura baseada em sensores simulados, protocolo MQTT, broker Mosquitto e dashboard web desenvolvido com Streamlit. Especificamente, buscou-se avaliar: (i) a inicialização correta dos serviços; (ii) a entrega das mensagens MQTT entre o sensor e o dashboard; (iii) o comportamento temporal do fluxo de publicação; (iv) o consumo de recursos computacionais dos containers; (v) a capacidade do dashboard de apresentar os dados recebidos em formato compreensível para o usuário final; (vi) a consulta da última leitura disponível para cada bairro monitorado; e (vii) a exibição de previsão acumulada de chuva para as próximas 1h, 3h e 6h.

## 5.2 Ambiente experimental

Os testes foram executados em um computador MacBook Air com chip Apple M4, 10 núcleos de CPU e 16 GB de memória RAM, executando macOS em arquitetura ARM64. A aplicação foi implantada com Docker 28.5.2 e Docker Compose v2.40.3. A solução é composta por três serviços orquestrados pelo arquivo `docker-compose.yml`: o broker MQTT Mosquitto, o sensor publicador e o dashboard web.

O serviço `mosquitto` utiliza a imagem `eclipse-mosquitto:latest` e disponibiliza o protocolo MQTT na porta 1883 e WebSocket na porta 9001. O serviço `sensor` executa o arquivo `sensor.py`, carrega dinamicamente os bairros de Maceió por meio da API OpenStreetMap/Overpass, mantém cache local da lista de bairros, percorre esses bairros em sequência, consulta dados meteorológicos recentes da API Open-Meteo e publica as leituras no tópico MQTT `iot/chuva`. O serviço `dashboard` executa o arquivo `dashboard_web.py`, assina o mesmo tópico MQTT, armazena as mensagens recebidas em memória e apresenta métricas, gráficos, histórico, previsão de chuva e uma tabela de última leitura por bairro por meio de uma interface web acessível pela porta 8501.

Na configuração utilizada, o sensor foi parametrizado para consultar e publicar uma leitura a cada 5 segundos (`PUBLISH_INTERVAL_SECONDS=5`), avançando para o próximo bairro após cada publicação. Como foram carregados 56 bairros, uma volta completa por todos os bairros leva aproximadamente 5 minutos, desconsiderando pequenas variações causadas pelo tempo de resposta das APIs externas. O dashboard realiza atualização automática da interface a cada 2 segundos (`AUTO_REFRESH_SECONDS=2`) e mantém um histórico máximo de 500 mensagens (`MAX_HISTORY_ROWS=500`). Para a análise visual recente, são considerados os 24 registros mais recentes (`RECENT_HISTORY_ROWS=24`).

## 5.3 Métricas, fatores e parâmetros

As métricas escolhidas consideram tanto o funcionamento da comunicação quanto o custo computacional da solução. A Tabela 1 resume as métricas utilizadas na avaliação.

**Tabela 1 - Métricas avaliadas**

| Métrica | Descrição | Forma de medição |
| --- | --- | --- |
| Quantidade de bairros carregados | Número de bairros retornados pela consulta OpenStreetMap/Overpass | Logs do container `sensor` |
| Taxa de entrega MQTT | Relação entre mensagens publicadas pelo sensor e mensagens recebidas pelo dashboard | Comparação entre logs de publicação e recebimento |
| Intervalo entre publicações | Tempo observado entre mensagens consecutivas publicadas no tópico `iot/chuva` | Timestamps das mensagens do sensor |
| Cobertura por bairro | Capacidade de percorrer os bairros carregados e manter uma última leitura consultável por bairro | Logs do sensor e tabela do dashboard |
| Previsão de chuva | Precipitação acumulada prevista para as próximas 1h, 3h e 6h | Campos `previsao_chuva_1h`, `previsao_chuva_3h` e `previsao_chuva_6h` |
| Uso de cache | Criação e reutilização da lista local de bairros | Arquivo `cache/neighborhoods_cache.json` |
| Uso de CPU | Percentual de CPU consumido por cada container | Comando `docker stats --no-stream` |
| Uso de memória | Memória utilizada por cada container durante a execução | Comando `docker stats --no-stream` |
| Disponibilidade funcional | Capacidade dos três serviços permanecerem em execução | Comando `docker compose ps` |

Os fatores e níveis adotados no experimento são apresentados na Tabela 2.

**Tabela 2 - Fatores e níveis do experimento**

| Fator | Valor utilizado |
| --- | --- |
| Cidade monitorada | Maceió/AL |
| Fonte de localização | OpenStreetMap/Overpass |
| Fonte climática | Open-Meteo |
| Protocolo de comunicação | MQTT |
| Broker | Eclipse Mosquitto |
| Tópico MQTT | `iot/chuva` |
| Intervalo de publicação | 5 segundos entre um bairro e o próximo |
| Ordem de consulta dos bairros | Sequencial, seguindo a lista carregada do OpenStreetMap/Overpass |
| Cache dos bairros | `cache/neighborhoods_cache.json` |
| Atualização do dashboard | 2 segundos |
| Histórico máximo em memória | 500 mensagens |
| Serviços avaliados | `mosquitto`, `sensor` e `dashboard` |

## 5.4 Experimento 1: inicialização e carregamento dos bairros

O primeiro experimento avaliou se o sistema consegue inicializar a pilha de serviços e obter a lista de bairros monitorados. Após a execução do comando `docker compose up -d`, os três containers permaneceram em execução: `mqtt-broker`, `sensor-publisher` e `dashboard-streamlit`.

Durante a inicialização do sensor, foram carregados 56 bairros de Maceió, incluindo Jaraguá, Jacarecica, Canaã, Santo Amaro, Pitanguinha, Ponta Verde, Pajuçara, Centro, entre outros. A implementação também salvou a lista em `cache/neighborhoods_cache.json`, permitindo que o sistema reutilize a última lista válida caso a API Overpass apresente instabilidade em uma execução futura.

Esse resultado indica que o sistema possui tolerância básica a falhas transitórias na etapa de carregamento geográfico. Em aplicações que dependem de APIs públicas, esse comportamento é relevante, uma vez que indisponibilidades momentâneas podem ocorrer fora do controle da aplicação.

## 5.5 Experimento 2: publicação sequencial e entrega das mensagens MQTT

O segundo experimento avaliou o fluxo principal da solução: publicação sequencial das leituras pelo sensor e recebimento pelo dashboard. Após a conexão com o broker MQTT, o sensor iniciou a varredura pela lista de bairros carregados e publicou mensagens no tópico `iot/chuva`. O dashboard recebeu as mesmas mensagens e passou a atualizar sua tabela de última leitura por bairro.

**Tabela 3 - Amostra de mensagens publicadas e recebidas**

| Horário | Bairro | Interpretação | Temperatura | Umidade | Pressão | Chuva agora | Chuva prevista 3h | Vento | Resultado |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 16:02:30 | Antares | Chuva fraca agora | 26,1 °C | 81% | 1014,2 hPa | 0,1 mm | 0,4 mm | 14,1 km/h | Recebida |
| 16:02:36 | Barro Duro | Chuva fraca agora | 26,1 °C | 81% | 1014,2 hPa | 0,1 mm | 0,4 mm | 14,1 km/h | Recebida |
| 16:02:42 | Bebedouro | Chuva fraca agora | 26,1 °C | 81% | 1014,2 hPa | 0,1 mm | 0,4 mm | 14,1 km/h | Recebida |
| 16:02:48 | Benedito Bentes | Chuva fraca agora | 25,6 °C | 85% | 1014,3 hPa | 0,1 mm | 0,2 mm | 13,1 km/h | Recebida |
| 16:02:54 | Benedito Bentes II | Chuva fraca agora | 25,6 °C | 85% | 1014,3 hPa | 0,1 mm | 0,2 mm | 13,1 km/h | Recebida |

Na amostra observada após as melhorias, 5 mensagens consecutivas foram publicadas pelo sensor e recebidas pelo dashboard, resultando em taxa de entrega de 100% no período avaliado. A ordem dos bairros observados nos logs foi Antares, Barro Duro, Bebedouro, Benedito Bentes e Benedito Bentes II, confirmando que o sensor percorre a lista de bairros sequencialmente. O intervalo médio observado entre as publicações ficou próximo de 6 segundos, valor compatível com o parâmetro configurado de 5 segundos somado ao tempo de consulta à API climática e construção do pacote JSON.

## 5.6 Experimento 3: consumo de recursos computacionais

O terceiro experimento mediu o consumo de CPU e memória dos containers durante a execução do sistema. A medição foi realizada com o comando `docker stats --no-stream`, após a aplicação estar em funcionamento e com mensagens sendo publicadas e recebidas.

**Tabela 4 - Consumo de recursos dos containers**

| Container | CPU | Memória utilizada | Observação |
| --- | ---: | ---: | --- |
| `dashboard-streamlit` | 0,45% | 114,3 MiB | Maior consumo relativo, por executar a interface web e renderizar gráficos |
| `sensor-publisher` | 0,00% | 18,25 MiB | Baixo consumo, pois executa uma coleta periódica simples |
| `mqtt-broker` | 0,08% | 2,258 MiB | Consumo muito baixo, compatível com broker leve |

Os resultados indicam que a solução possui baixo custo computacional no cenário avaliado. O serviço mais custoso foi o dashboard, o que é esperado, pois ele mantém a interface Streamlit, renderiza componentes visuais e atualiza periodicamente a página. Ainda assim, o consumo de memória permaneceu próximo de 100 MiB, valor adequado para execução local em computadores pessoais ou pequenos servidores.

O broker Mosquitto apresentou uso de memória inferior a 4 MiB e uso de CPU praticamente nulo, indicando que o protocolo MQTT é adequado para o volume de mensagens utilizado. O sensor também apresentou baixo consumo de memória e CPU, pois sua principal atividade é executar consultas periódicas às APIs externas e publicar mensagens pequenas em JSON.

## 5.7 Experimento 4: análise funcional do dashboard

O quarto experimento avaliou se as mensagens recebidas eram convertidas corretamente em informações úteis ao usuário. O dashboard processa os campos recebidos no JSON, incluindo bairro, temperatura, umidade, pressão, precipitação, velocidade do vento, horário e dia da semana. Em seguida, esses dados são exibidos em cards de resumo, tabela de última leitura por bairro, tabela histórica, gráficos de tendência e seção de situação atual.

Na amostra coletada, os registros apresentaram chuva positiva, previsão acumulada para as próximas horas e umidade igual ou superior a 81% em alguns bairros. Segundo as regras implementadas no arquivo `dashboard_web.py`, o sistema classifica a situação como `Atenção` quando há chuva recente, previsão de chuva próxima ou umidade elevada. Assim, os dados observados validam o comportamento esperado do mecanismo de classificação: o dashboard não apenas exibe os valores brutos, mas também traduz as leituras em um indicador operacional de acompanhamento. Além disso, a tabela “Última leitura por bairro” permite consultar rapidamente a condição mais recente disponível para cada bairro já percorrido pelo sensor e inclui a coluna “Interpretação da chuva”, que apresenta mensagens textuais como “Chuva fraca agora” ou “Sem chuva prevista”.

Para documentar visualmente este experimento no artigo, recomenda-se inserir uma captura de tela do dashboard em execução, mostrando: (i) o resumo atual; (ii) a tabela de última leitura por bairro; (iii) a situação atual; (iv) os gráficos de tendência; (v) a tabela de histórico recente; e (vi) o último pacote MQTT recebido em JSON. Essa imagem deve ser referenciada no texto como evidência visual da integração entre coleta, comunicação e visualização.

## 5.8 Discussão dos resultados

Os resultados obtidos demonstram que a solução atende ao objetivo proposto de monitoramento climático em tempo real para bairros de Maceió. O sistema conseguiu carregar dinamicamente 56 bairros, salvar a lista em cache local, coletar dados climáticos da API Open-Meteo, publicar leituras no broker MQTT e exibir as mensagens no dashboard web. A taxa de entrega observada foi de 100% na amostra avaliada, com 5 mensagens sequenciais publicadas e 5 mensagens recebidas.

O intervalo entre publicações ficou próximo do valor configurado, demonstrando que o parâmetro de carga de trabalho definido no sensor é respeitado. A diferença entre os 5 segundos configurados e os cerca de 6 segundos observados decorre do tempo necessário para consultar a API externa e processar a resposta antes do envio MQTT. Como o sensor percorre todos os bairros em sequência, o dashboard passa a acumular uma visão progressiva da cidade até completar uma rodada por todos os locais monitorados.

Em relação ao consumo de recursos, a arquitetura mostrou-se leve. O broker Mosquitto foi o componente de menor custo, enquanto o dashboard apresentou maior consumo relativo, devido à atualização automática e à renderização da interface. Mesmo assim, o uso de memória e CPU permaneceu baixo para o ambiente de teste, indicando que a solução pode ser executada em um computador comum sem exigir infraestrutura robusta.

Uma limitação importante é que parte do funcionamento depende da disponibilidade de serviços externos. Entretanto, o mecanismo de retentativa e o cache local de bairros reduzem o impacto de falhas temporárias na API Overpass. Caso a API geográfica esteja indisponível após uma execução bem-sucedida anterior, o sistema pode reutilizar a lista salva em `cache/neighborhoods_cache.json`.

De forma geral, os experimentos validam a viabilidade da solução proposta. A aplicação apresenta funcionamento integrado, baixo consumo de recursos e capacidade de transformar dados climáticos em informações visuais e indicadores úteis para acompanhamento de chuva e condições meteorológicas em bairros de Maceió. A alteração para varredura sequencial também aproxima o sistema do uso como ferramenta de consulta por bairro, pois cada bairro passa a ter sua última leitura registrada e exibida no dashboard.

## 5.9 Figuras e gráficos recomendados para o artigo

Para complementar a seção no documento final, recomenda-se inserir os seguintes recursos visuais:

**Figura 1 - Arquitetura do sistema:** diagrama com o fluxo `OpenStreetMap/Overpass + Open-Meteo -> Sensor Python -> Broker Mosquitto -> Dashboard Streamlit`.

**Figura 2 - Dashboard em execução:** captura de tela de `http://localhost:8501`, mostrando resumo atual, previsão de chuva, tabela de última leitura por bairro, situação, gráficos e histórico.

**Gráfico 1 - Mensagens publicadas e recebidas:** gráfico de barras comparando 5 mensagens publicadas e 5 mensagens recebidas, evidenciando taxa de entrega de 100% na amostra após as melhorias.

**Gráfico 2 - Consumo de memória por container:** gráfico de barras com `dashboard-streamlit` = 114,3 MiB, `sensor-publisher` = 18,25 MiB e `mqtt-broker` = 2,258 MiB.

**Gráfico 3 - Intervalo entre publicações:** gráfico de linha ou tabela mostrando os horários 16:02:30, 16:02:36, 16:02:42, 16:02:48 e 16:02:54, com intervalos aproximados de 6 segundos.
