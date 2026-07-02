"""Configuratie voor de Gaspedaal Stelvio Analyzer."""

BASE_URL = "https://www.gaspedaal.nl"
SEARCH_PATH = "/alfa-romeo/stelvio"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Wachttijd tussen requests (seconden). Hoger = beleefder voor gaspedaal.nl en
# minder kans op een blokkade. Verlaag dit niet te agressief.
MIN_DELAY_SECONDS = 2.5
MAX_DELAY_SECONDS = 5.0

DB_PATH = "data/stelvio.db"
DEBUG_DIR = "debug"

MAX_PAGES_DEFAULT = 20

# Bekende Stelvio-uitvoeringen. Gebruikt als fallback om de trim uit de
# advertentietitel te herkennen wanneer de detailpagina geen los
# "Uitvoering"-veld heeft. Vul aan als je een uitvoering mist.
KNOWN_TRIMS = [
    "Quadrifoglio",
    "Veloce",
    "Ti",
    "Super",
    "Sprint",
    "Milano Edizione",
    "Executive",
    "Business",
    "Lusso",
    "Speciale",
    "B-Tech",
    "First Edition",
    "Competizione",
]

# Nederlandse veldlabels zoals ze doorgaans in de specificatietabel van een
# advertentiepagina staan, gemapt naar onze interne kolomnamen. Voeg hier
# labels aan toe of pas ze aan als gaspedaal.nl andere bewoordingen blijkt te
# gebruiken (check met `python scraper.py --debug`, zie README.md).
LABEL_MAP = {
    "bouwjaar": "build_year",
    "eerste registratie": "build_year",
    "km stand": "mileage_km",
    "kilometerstand": "mileage_km",
    "brandstof": "fuel_type",
    "kleur": "color",
    "uitvoering": "trim",
    "transmissie": "transmission",
    "vermogen": "power_hp",
    "carrosserie": "body_type",
    "motorinhoud": "engine_capacity",
    "aantal deuren": "doors",
    "vraagprijs": "price",
    "prijs": "price",
}
