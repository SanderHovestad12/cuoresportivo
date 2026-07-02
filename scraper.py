"""
Scraper voor Alfa Romeo Stelvio-advertenties op gaspedaal.nl.

LET OP: dit script is gebouwd zonder live toegang tot gaspedaal.nl (de
omgeving waarin dit is geschreven blokkeert uitgaand verkeer naar de site).
De parsing-strategie is daarom bewust defensief opgezet met meerdere
fallbacks (embedded JSON, generieke link-detectie, generieke label/waarde-
extractie), maar het is goed mogelijk dat je iets in dit bestand of in
config.LABEL_MAP moet bijstellen aan de hand van de actuele site.

Draai eerst:

    python scraper.py --debug --max-pages 1

en bekijk de opgeslagen HTML in de map `debug/` (of open de site in je
browser en gebruik "Element inspecteren") om te controleren of de aannames
nog kloppen. Zie README.md voor meer uitleg.
"""
import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config
import db
import normalize as norm


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


def extract_next_data(soup):
    """Next.js-apps embedden vaak de volledige paginadata als JSON in de HTML."""
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def find_listing_urls_fallback(soup, base_url):
    """Generieke fallback: zoek links die naar een advertentie lijken te wijzen."""
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/stelvio/.+-\d{5,}", href) or "/advertentie/" in href:
            urls.append(urljoin(base_url, href))
    return _dedupe(urls)


def _dedupe(items):
    seen = set()
    unique = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def urls_from_json(data, base_url):
    """Doorzoekt embedded JSON generiek naar velden die op een advertentie-URL lijken."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            url_val = node.get("url")
            if isinstance(url_val, str) and "/stelvio/" in url_val:
                found.append(urljoin(base_url, url_val))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return _dedupe(found)


def has_next_page(soup):
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link:
        return True
    return soup.find("a", string=re.compile(r"volgende", re.I)) is not None


def parse_search_page(html, page_url):
    """Geeft (listing_urls, heeft_volgende_pagina) terug."""
    soup = BeautifulSoup(html, "lxml")

    data = extract_next_data(soup)
    if data:
        listing_urls = urls_from_json(data, page_url)
        if listing_urls:
            return listing_urls, has_next_page(soup)

    return find_listing_urls_fallback(soup, page_url), has_next_page(soup)


def extract_spec_pairs(soup):
    """Haalt generiek label/waarde-paren uit dt/dd- en 2-koloms tabelstructuren."""
    pairs = {}

    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            label = norm.clean(dt.get_text())
            value = norm.clean(dd.get_text())
            if label:
                pairs[label.lower().rstrip(":")] = value

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            label = norm.clean(cells[0].get_text())
            value = norm.clean(cells[1].get_text())
            if label:
                pairs[label.lower().rstrip(":")] = value

    return pairs


def listing_id_from_url(url):
    match = re.search(r"(\d{5,})(?:[/?#]|$)", url)
    return match.group(1) if match else url


def parse_detail_page(html, url):
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1")
    title = norm.clean(title_tag.get_text()) if title_tag else None

    price = None
    price_match = re.search(r"€\s?[\d.,]+", soup.get_text())
    if price_match:
        price = norm.parse_price(price_match.group(0))

    listing = {
        "id": listing_id_from_url(url),
        "url": url,
        "title": title,
        "price": price,
    }

    for label, value in extract_spec_pairs(soup).items():
        field = config.LABEL_MAP.get(label)
        if not field or value is None:
            continue
        if field == "build_year":
            listing[field] = norm.parse_year(value)
        elif field == "mileage_km":
            listing[field] = norm.parse_mileage(value)
        elif field == "power_hp":
            listing[field] = norm.parse_power(value)
        elif field == "price":
            listing[field] = norm.parse_price(value) or listing.get("price")
        else:
            listing[field] = norm.clean(value)

    # Fallbacks op basis van de titel als de spec-tabel iets niet vermeldt.
    if not listing.get("trim"):
        listing["trim"] = norm.guess_trim(title)
    if not listing.get("fuel_type"):
        listing["fuel_type"] = norm.guess_fuel(title)
    if not listing.get("engine"):
        listing["engine"] = norm.guess_engine(title)
    if not listing.get("build_year"):
        listing["build_year"] = norm.parse_year(title)

    return listing


def build_search_url(page):
    url = f"{config.BASE_URL}{config.SEARCH_PATH}"
    return url if page == 1 else f"{url}?pagina={page}"


def collect_listing_urls(session, max_pages, debug):
    all_urls = []
    for page in range(1, max_pages + 1):
        url = build_search_url(page)
        print(f"[scraper] Ophalen zoekpagina {page}: {url}")
        try:
            html = fetch(session, url)
        except requests.RequestException as exc:
            print(f"[scraper] Fout bij ophalen {url}: {exc}")
            break

        if debug:
            save_debug(f"search_page_{page}.html", html)

        urls, more_pages = parse_search_page(html, url)
        print(f"[scraper]  -> {len(urls)} advertenties gevonden op pagina {page}")
        all_urls.extend(urls)

        if not urls or not more_pages:
            break
        polite_sleep()

    return _dedupe(all_urls)


def run(max_pages, fetch_details, debug):
    db.init_db()
    session = make_session()

    unique_urls = collect_listing_urls(session, max_pages, debug)
    print(f"[scraper] Totaal {len(unique_urls)} unieke advertenties gevonden.")

    if not unique_urls:
        print(
            "[scraper] Geen advertenties gevonden. De site-structuur is "
            "vermoedelijk gewijzigd t.o.v. de aannames in dit script -- "
            "draai met --debug en vergelijk de opgeslagen HTML met de "
            "live site. Zie README.md."
        )
        return

    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    seen_ids = [listing_id_from_url(u) for u in unique_urls]

    with db.connect() as conn:
        for i, url in enumerate(unique_urls, 1):
            listing = {"id": listing_id_from_url(url), "url": url}

            if fetch_details:
                print(f"[scraper] ({i}/{len(unique_urls)}) Detailpagina: {url}")
                try:
                    html = fetch(session, url)
                except requests.RequestException as exc:
                    print(f"[scraper]  fout bij ophalen detailpagina: {exc}")
                    continue
                if debug:
                    save_debug(f"detail_{listing['id']}.html", html)
                listing = parse_detail_page(html, url)
                polite_sleep()

            if db.upsert_listing(conn, listing, now):
                new_count += 1

        db.mark_inactive(conn, seen_ids, now)
        db.record_run(conn, now, len(unique_urls), new_count)

    print(f"[scraper] Klaar. {new_count} nieuwe advertenties, {len(unique_urls)} totaal actief gezien.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES_DEFAULT,
                         help="Maximaal aantal zoekresultaatpagina's om te doorlopen")
    parser.add_argument("--ids-only", action="store_true",
                         help="Alleen advertentie-URLs verzamelen, geen detailpagina's ophalen "
                              "(sneller, maar zonder motorisering/kleur/uitvoering/prijs)")
    parser.add_argument("--debug", action="store_true",
                         help="Sla ruwe HTML op in debug/ voor inspectie")
    args = parser.parse_args()

    run(max_pages=args.max_pages, fetch_details=not args.ids_only, debug=args.debug)


if __name__ == "__main__":
    main()
