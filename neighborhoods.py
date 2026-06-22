import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import requests


Coordenadas = Tuple[float, float]
Bairros = Dict[str, Coordenadas]

URL_OVERPASS = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
NOME_CIDADE = os.getenv("CITY_NAME", "Maceió")
NOME_ESTADO = os.getenv("STATE_NAME", "Alagoas")
NOME_PAIS = os.getenv("COUNTRY_NAME", "Brasil")

SEGUNDOS_TIMEOUT_OVERPASS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "30"))
ARQUIVO_CACHE_BAIRROS = Path(os.getenv("NEIGHBORHOOD_CACHE_FILE", "neighborhoods_cache.json"))
ATUALIZAR_BAIRROS_AO_INICIAR = os.getenv("REFRESH_NEIGHBORHOODS_ON_START", "false").lower() == "true"
PREFIXOS_NOMES_IGNORADOS = (
    "Condomínio ",
    "Conjunto ",
    "Loteamento ",
    "Village ",
)


def montar_consulta_overpass() -> str:
    return f"""
    [out:json][timeout:{SEGUNDOS_TIMEOUT_OVERPASS}];
    area["boundary"="administrative"]["name"="{NOME_CIDADE}"]["admin_level"="8"]->.city;
    (
      nwr(area.city)["place"~"^(neighbourhood|suburb|quarter)$"]["name"];
      nwr(area.city)["boundary"="administrative"]["name"]["admin_level"~"^(9|10|11)$"];
    );
    out center tags;
    """


def obter_coordenadas_elemento(elemento: dict) -> Coordenadas:
    if "lat" in elemento and "lon" in elemento:
        return float(elemento["lat"]), float(elemento["lon"])

    centro = elemento.get("center", {})
    return float(centro["lat"]), float(centro["lon"])


def nome_bairro_valido(nome: str) -> bool:
    normalizado = nome.strip().lower()
    nomes_bloqueados = {
        NOME_CIDADE.lower(),
        NOME_ESTADO.lower(),
        NOME_PAIS.lower(),
    }
    return (
        bool(normalizado)
        and normalizado not in nomes_bloqueados
        and not nome.startswith(PREFIXOS_NOMES_IGNORADOS)
    )


def normalizar_nome_bairro(nome: str) -> str:
    nome = nome.strip()
    if nome.startswith("Bairro "):
        return nome.removeprefix("Bairro ").strip()
    return nome


def carregar_bairros_cache() -> Bairros:
    if not ARQUIVO_CACHE_BAIRROS.exists():
        return {}

    try:
        dados = json.loads(ARQUIVO_CACHE_BAIRROS.read_text(encoding="utf-8"))
        return {
            str(nome): (float(coordenadas[0]), float(coordenadas[1]))
            for nome, coordenadas in dados.items()
        }
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def salvar_bairros_cache(bairros: Bairros) -> None:
    try:
        ARQUIVO_CACHE_BAIRROS.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_CACHE_BAIRROS.write_text(
            json.dumps(bairros, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as erro:
        print(f"Não foi possível salvar cache de bairros: {erro}")


def carregar_bairros() -> Bairros:
    cacheado = carregar_bairros_cache()
    if cacheado and not ATUALIZAR_BAIRROS_AO_INICIAR:
        print(f"{len(cacheado)} bairros carregados do cache local.")
        return cacheado

    try:
        resposta = requests.post(
            URL_OVERPASS,
            data={"data": montar_consulta_overpass()},
            timeout=SEGUNDOS_TIMEOUT_OVERPASS + 5,
            headers={"User-Agent": "projeto-sensoriamento-maceio/1.0"},
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except (requests.RequestException, ValueError):
        if cacheado:
            print(f"{len(cacheado)} bairros carregados do cache local.")
            return cacheado
        raise

    bairros: Bairros = {}
    for elemento in dados.get("elements", []):
        etiquetas = elemento.get("tags", {})
        nome = normalizar_nome_bairro(etiquetas.get("name", ""))
        if not nome or not nome_bairro_valido(nome):
            continue

        try:
            bairros[nome.strip()] = obter_coordenadas_elemento(elemento)
        except (KeyError, TypeError, ValueError):
            continue

    bairros = dict(sorted(bairros.items()))
    if bairros:
        salvar_bairros_cache(bairros)
        return bairros

    if cacheado:
        print(f"{len(cacheado)} bairros carregados do cache local.")
    return cacheado


def formatar_bairros(bairros: Bairros) -> List[str]:
    return [f"{nome} ({lat:.5f}, {lon:.5f})" for nome, (lat, lon) in bairros.items()]
