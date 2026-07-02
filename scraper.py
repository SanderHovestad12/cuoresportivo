"""
Scraper voor Alfa Romeo Stelvio-advertenties op gaspedaal.nl.

Gaspedaal.nl is een Next.js-app (App Router) die de zoekresultaten
server-side rendert, maar de onderliggende data staat als volledig
gestructureerde JSON verstopt in <script>self.__next_f.push(...)</script>-
tags (React Server Components "flight"-payload). Deze JSON bevat per
advertentie exact de velden die we nodig hebben (prijs, bouwjaar, km-stand,
brandstof, motor, kleur, uitvoering, transmissie, verkoper, ...), en is
veel betrouwbaarder dan de zichtbare HTML zelf.

Deze data is bevestigd aan de hand van een echte, door de gebruiker
aangeleverde zoekpagina (zie git-geschiedenis / debug-output). Mocht
gaspedaal.nl haar pagina-opbouw wijzigen, dan valt dit script terug op het
parsen van de zichtbare advertentiekaarten (`data-testid="occasion-item"`).

Draai bij problemen eerst:

    python scraper.py --debug --max-pages 1

en bekijk `debug/search_page_1.html`. Zoek daarin naar
`self.__next_f.push` (JSON-databron) of `data-testid="occasion-item"`
(zichtbare kaarten) om te zien wat er is veranderd, en pas zo nodig
`extract_listings_from_json` of `parse_occasion_cards` hieronder aan.
"""
import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config
import db
import normalize as norm

FUEL_WORDS = {"Benzine", "Diesel", "Hybride", "Elektrisch", "LPG", "Aardgas", "Waterstof"}
TRANSMISSION_WORDS = {"Automaat", "Handgeschakeld"}
COLOR_WORDS = {
    "Wit", "Zwart", "Grijs", "Rood", "Blauw", "Groen", "Geel", "Bruin",
    "Beige", "Zilver", "Oranje", "Paars", "Goud", "Overig", "Crème", "Roze",
}


def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    })
    return session


def polite_sleep():
    time.sleep(random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS))


def fetch(session, url):
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def save_debug(name, html):
    Path(config.DEBUG_DIR).mkdir(exist_ok=True)
    path = Path(config.DEBUG_DIR) / name
    path.write_text(html, encoding="utf-8")
    print(f"[debug] HTML opgeslagen in {path}")


# --- Strategie 1: gestructureerde JSON uit de Next.js flight-payload -------

def extract_next_f_chunks(html):
    """Haalt de string-payloads uit self.__next_f.push([...])-scripts."""
    chunks = []
    for match in re.finditer(r"self\.__next_f\.push\((\[.*?\])\)\s*</script>", html, re.S):
        try:
            arr = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if len(arr) >= 2 and isinstance(arr[1], str):
            chunks.append(arr[1])
    return chunks


def extract_listings_from_json(html):
    """Doorzoekt de flight-payload naar advertentie-objecten en het totaal aantal pagina's."""
    raw_listings = []
    total_pages = None

    def walk(node):
        nonlocal total_pages
        if isinstance(node, dict):
            prijs = node.get("prijs")
            if "advertentieId" in node and isinstance(prijs, dict) and "totaal" in prijs:
                raw_listings.append(node)
            if isinstance(node.get("numberOfPages"), int):
                total_pages = node["numberOfPages"]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for chunk in extract_next_f_chunks(html):
        # Elke chunk begint met een rij-id zoals "35:" gevolgd door JSON.
        match = re.match(r"^[0-9a-fA-F]+:(.*)$", chunk, re.S)
        body = match.group(1) if match else chunk
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        walk(data)

    return raw_listings, total_pages


def normalize_json_listing(raw):
    algemeen = raw.get("autogegevens", {}).get("algemeen", {})
    motor = raw.get("autogegevens", {}).get("motor", {})
    geschiedenis = raw.get("autogegevens", {}).get("geschiedenis", {})
    aanbiedergegevens = raw.get("aanbieder", {}).get("aanbiedergegevens", {})
    portalen = raw.get("portalen") or []

    url = next((p["klikUrl"] for p in portalen if p.get("tip") and p.get("klikUrl")), None)
    if not url and portalen:
        url = portalen[0].get("klikUrl")
    if not url:
        url = f"{config.BASE_URL}{config.SEARCH_PATH}#o{raw['advertentieId']}"

    uitvoering = algemeen.get("uitvoering")
    merknaam = algemeen.get("merknaam", "")
    modelnaam = algemeen.get("modelnaam", "")
    title = f"{merknaam} {modelnaam} - {uitvoering}" if uitvoering else f"{merknaam} {modelnaam}"

    location = None
    if aanbiedergegevens.get("plaatsnaam"):
        location = aanbiedergegevens["plaatsnaam"]
        if aanbiedergegevens.get("provincieHulpwaarde"):
            location += f" ({aanbiedergegevens['provincieHulpwaarde']})"

    fuel_raw = algemeen.get("brandstofsoort")
    transmission_raw = algemeen.get("transmissietype")
    power_hp = motor.get("vermogenPk")
    engine_cc = motor.get("motorinhoud")

    return {
        "id": str(raw["advertentieId"]),
        "url": url,
        "title": norm.clean(title),
        "price": raw.get("prijs", {}).get("totaal"),
        "build_year": geschiedenis.get("bouwjaar"),
        "mileage_km": geschiedenis.get("kilometerstand"),
        "fuel_type": config.FUEL_MAP.get(fuel_raw, fuel_raw.title() if fuel_raw else None),
        "engine": norm.label_engine_cc(engine_cc) or norm.guess_engine(uitvoering),
        "power_hp": round(power_hp) if power_hp else None,
        "transmission": config.TRANSMISSION_MAP.get(transmission_raw, transmission_raw),
        "color": (algemeen.get("kleur") or "").title() or None,
        "trim": norm.guess_trim(uitvoering),
        "body_type": algemeen.get("carrosserievorm"),
        "location": location,
        "seller_type": "Particulier" if raw.get("aanbieder", {}).get("soort") == "PARTICULIER" else "Dealer",
    }


# --- Strategie 2 (fallback): de zichtbare advertentiekaarten in de HTML ---

def parse_occasion_cards(soup):
    listings = []
    for card in soup.find_all(attrs={"data-testid": "occasion-item"}):
        card_id = (card.get("id") or "").replace("oc", "", 1)
        if not card_id:
            continue

        price_tag = card.find(attrs={"data-testid": "price"})
        price = norm.parse_price(price_tag.get_text()) if price_tag else None

        title_tag = card.find("h2")
        title = norm.clean(title_tag.get_text()) if title_tag else None

        text = card.get_text(" ", strip=True)
        year_match = re.search(r"Bouwjaar:?\s*(\d{4})", text)
        mileage_match = re.search(r"Km\.?\s?stand:?\s*([\d.]+)", text)

        fuel = transmission = color = body_type = engine_cc = None
        for span in card.find_all("span"):
            token = norm.clean(span.get_text())
            if not token:
                continue
            if token in FUEL_WORDS:
                fuel = token
            elif token in TRANSMISSION_WORDS:
                transmission = token
            elif token in COLOR_WORDS:
                color = token
            elif re.match(r"^[\d.,]+\s?cc$", token, re.I):
                engine_cc = token
            elif "terreinwagen" in token.lower() or token.lower() in {
                "hatchback", "sedan", "stationwagon", "cabriolet", "coupe", "mpv",
            }:
                body_type = token

        listings.append({
            "id": card_id,
            "url": f"{config.BASE_URL}{config.SEARCH_PATH}#o{card_id}",
            "title": title,
            "price": price,
            "build_year": int(year_match.group(1)) if year_match else norm.parse_year(title),
            "mileage_km": norm.parse_mileage(mileage_match.group(1)) if mileage_match else None,
            "fuel_type": fuel or norm.guess_fuel(title),
            "engine": engine_cc or norm.guess_engine(title),
            "transmission": transmission,
            "color": color,
            "trim": norm.guess_trim(title),
            "body_type": body_type,
        })
    return listings


# --- Orkestratie ------------------------------------------------------------

def parse_search_page(html):
    """Geeft (listings, totaal_aantal_paginas) terug. totaal_aantal_paginas kan None zijn."""
    raw_listings, total_pages = extract_listings_from_json(html)
    if raw_listings:
        return [normalize_json_listing(r) for r in raw_listings], total_pages

    soup = BeautifulSoup(html, "lxml")
    return parse_occasion_cards(soup), None


def build_search_url(page):
    url = f"{config.BASE_URL}{config.SEARCH_PATH}"
    return url if page == 1 else f"{url}?{config.PAGE_QUERY_PARAM}={page}"


def collect_listings(session, max_pages, debug):
    listings_by_id = {}
    total_pages = None
    page = 1

    while page <= max_pages and (total_pages is None or page <= total_pages):
        url = build_search_url(page)
        print(f"[scraper] Ophalen zoekpagina {page}: {url}")
        try:
            html = fetch(session, url)
        except requests.RequestException as exc:
            print(f"[scraper] Fout bij ophalen {url}: {exc}")
            break

        if debug:
            save_debug(f"search_page_{page}.html", html)

        listings, page_total_pages = parse_search_page(html)
        if page_total_pages:
            total_pages = page_total_pages

        print(f"[scraper]  -> {len(listings)} advertenties gevonden op pagina {page}"
              + (f" (totaal {total_pages} pagina's)" if total_pages else ""))

        if not listings:
            break

        for listing in listings:
            listings_by_id[listing["id"]] = listing

        page += 1
        if total_pages is None or page <= total_pages:
            polite_sleep()

    return list(listings_by_id.values())


def run(max_pages, debug):
    db.init_db()
    session = make_session()

    listings = collect_listings(session, max_pages, debug)
    print(f"[scraper] Totaal {len(listings)} unieke advertenties gevonden.")

    if not listings:
        print(
            "[scraper] Geen advertenties gevonden. De site-structuur is "
            "vermoedelijk gewijzigd t.o.v. de aannames in dit script -- "
            "draai met --debug en vergelijk de opgeslagen HTML met de "
            "live site. Zie README.md."
        )
        return

    now = datetime.now(timezone.utc).isoformat()
    new_count = 0

    with db.connect() as conn:
        for listing in listings:
            if db.upsert_listing(conn, listing, now):
                new_count += 1
        db.mark_inactive(conn, [listing["id"] for listing in listings], now)
        db.record_run(conn, now, len(listings), new_count)

    print(f"[scraper] Klaar. {new_count} nieuwe advertenties, {len(listings)} totaal actief gezien.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES_SAFETY_CAP,
                         help="Maximaal aantal zoekresultaatpagina's om te doorlopen")
    parser.add_argument("--debug", action="store_true",
                         help="Sla ruwe HTML op in debug/ voor inspectie")
    args = parser.parse_args()

    run(max_pages=args.max_pages, debug=args.debug)


if __name__ == "__main__":
    main()
