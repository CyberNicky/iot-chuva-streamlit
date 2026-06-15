import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import requests


Coordinates = Tuple[float, float]
Neighborhoods = Dict[str, Coordinates]

OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
CITY_NAME = os.getenv("CITY_NAME", "Maceió")
STATE_NAME = os.getenv("STATE_NAME", "Alagoas")
COUNTRY_NAME = os.getenv("COUNTRY_NAME", "Brasil")

OVERPASS_TIMEOUT_SECONDS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "30"))
NEIGHBORHOOD_CACHE_FILE = Path(os.getenv("NEIGHBORHOOD_CACHE_FILE", "neighborhoods_cache.json"))
IGNORED_NAME_PREFIXES = (
    "Condomínio ",
    "Conjunto ",
    "Loteamento ",
    "Village ",
)


def build_overpass_query() -> str:
    return f"""
    [out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];
    area["boundary"="administrative"]["name"="{CITY_NAME}"]["admin_level"="8"]->.city;
    (
      nwr(area.city)["place"~"^(neighbourhood|suburb|quarter)$"]["name"];
      nwr(area.city)["boundary"="administrative"]["name"]["admin_level"~"^(9|10|11)$"];
    );
    out center tags;
    """


def get_element_coordinates(element: dict) -> Coordinates:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])

    center = element.get("center", {})
    return float(center["lat"]), float(center["lon"])


def is_valid_neighborhood_name(name: str) -> bool:
    normalized = name.strip().lower()
    blocked_names = {
        CITY_NAME.lower(),
        STATE_NAME.lower(),
        COUNTRY_NAME.lower(),
    }
    return (
        bool(normalized)
        and normalized not in blocked_names
        and not name.startswith(IGNORED_NAME_PREFIXES)
    )


def normalize_neighborhood_name(name: str) -> str:
    name = name.strip()
    if name.startswith("Bairro "):
        return name.removeprefix("Bairro ").strip()
    return name


def load_cached_neighborhoods() -> Neighborhoods:
    if not NEIGHBORHOOD_CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(NEIGHBORHOOD_CACHE_FILE.read_text(encoding="utf-8"))
        return {
            str(name): (float(coordinates[0]), float(coordinates[1]))
            for name, coordinates in data.items()
        }
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def save_cached_neighborhoods(neighborhoods: Neighborhoods) -> None:
    try:
        NEIGHBORHOOD_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        NEIGHBORHOOD_CACHE_FILE.write_text(
            json.dumps(neighborhoods, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as error:
        print(f"Não foi possível salvar cache de bairros: {error}")


def load_neighborhoods() -> Neighborhoods:
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": build_overpass_query()},
            timeout=OVERPASS_TIMEOUT_SECONDS + 5,
            headers={"User-Agent": "projeto-sensoriamento-maceio/1.0"},
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        cached = load_cached_neighborhoods()
        if cached:
            print(f"{len(cached)} bairros carregados do cache local.")
            return cached
        raise

    neighborhoods: Neighborhoods = {}
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = normalize_neighborhood_name(tags.get("name", ""))
        if not name or not is_valid_neighborhood_name(name):
            continue

        try:
            neighborhoods[name.strip()] = get_element_coordinates(element)
        except (KeyError, TypeError, ValueError):
            continue

    neighborhoods = dict(sorted(neighborhoods.items()))
    if neighborhoods:
        save_cached_neighborhoods(neighborhoods)
        return neighborhoods

    cached = load_cached_neighborhoods()
    if cached:
        print(f"{len(cached)} bairros carregados do cache local.")
    return cached


def format_neighborhoods(neighborhoods: Neighborhoods) -> List[str]:
    return [f"{name} ({lat:.5f}, {lon:.5f})" for name, (lat, lon) in neighborhoods.items()]
