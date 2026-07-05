"""Geocoding van plaatsnamen voor de locatiekaart in het dashboard.

Gebruikt de gratis Nominatim-API van OpenStreetMap. Resultaten worden
opgeslagen in de `locations`-tabel in de database, zodat elke plaats maar
één keer hoeft te worden opgevraagd -- ook mislukte lookups worden
gecachet (als NULL) om herhaald falen te voorkomen.

Let op de gebruiksvoorwaarden van Nominatim (max. 1 request/seconde, een
herkenbare User-Agent) -- zie https://operations.osmfoundation.org/policies/nominatim/.
"""
import re
import time

import requests

import db

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "gaspedaal-stelvio-analyzer/1.0 (persoonlijk, niet-commercieel onderzoeksproject)"
REQUEST_DELAY_SECONDS = 1.1


def extract_city(location):
    """Haalt de plaatsnaam uit een locatieveld zoals 'Veen (NB)' -> 'Veen'."""
    if not location:
        return None
    match = re.match(r"^(.*?)\s*\([A-Za-z]{2}\)\s*$", str(location).strip())
    city = match.group(1) if match else str(location)
    return city.strip() or None


def _lookup(city):
    params = {"city": city, "country": "Netherlands", "format": "json", "limit": 1}
    resp = requests.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None, None
    return float(results[0]["lat"]), float(results[0]["lon"])


def geocode_missing_cities(cities, on_log=print):
    """Geocodeert alle plaatsnamen uit `cities` die nog niet in de cache staan.
    `on_log` ontvangt elke voortgangsregel (standaard print())."""
    unique_cities = sorted({c for c in cities if c})
    with db.connect() as conn:
        todo = [c for c in unique_cities if db.get_location(conn, c) is None]
        if not todo:
            on_log("[geocode] Alle plaatsen al eerder gegeocodeerd, niets te doen.")
            return
        on_log(f"[geocode] {len(todo)} nieuwe plaatsen te geocoderen...")
        for i, city in enumerate(todo, 1):
            on_log(f"[geocode] ({i}/{len(todo)}) {city}")
            try:
                lat, lon = _lookup(city)
            except requests.RequestException as exc:
                on_log(f"[geocode]  fout bij '{city}': {exc}")
                lat, lon = None, None
            db.save_location(conn, city, lat, lon)
            if i < len(todo):
                time.sleep(REQUEST_DELAY_SECONDS)
