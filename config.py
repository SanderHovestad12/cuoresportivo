"""Configuratie voor de Gaspedaal Stelvio Analyzer."""

BASE_URL = "https://www.gaspedaal.nl"
SEARCH_PATH = "/alfa-romeo/stelvio"
PAGE_QUERY_PARAM = "page"  # bevestigd via een echte zoekpagina: ?page=2, ?page=3, ...

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

# Veiligheidslimiet: het daadwerkelijke aantal pagina's wordt bepaald door
# "numberOfPages" uit de data van gaspedaal.nl zelf, maar dit is een
# bovengrens voor het geval dat veld ooit ontbreekt.
MAX_PAGES_SAFETY_CAP = 30

# Bekende Stelvio-uitvoeringen. Het "uitvoering"-veld van gaspedaal.nl bevat
# de vrije advertentietekst (bv. "2.0 T AWD 280PK|PANO|CAMERA|..."), dus we
# zoeken hierin naar een van deze bekende namen. Vul aan als je een
# uitvoering mist in de resultaten.
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

# Vertaling van de ruwe (Engelse/technische) waarden uit de gaspedaal.nl-data
# naar leesbare Nederlandse labels voor het dashboard.
FUEL_MAP = {
    "BENZINE": "Benzine",
    "DIESEL": "Diesel",
    "ELEKTRICITEIT": "Elektrisch",
    "HYBRIDE": "Hybride",
    "LPG": "LPG",
    "AARDGAS": "Aardgas",
    "WATERSTOF": "Waterstof",
}

TRANSMISSION_MAP = {
    "AUTOMATISCH": "Automaat",
    "HANDGESCHAKELD": "Handgeschakeld",
}

# Motorinhoud in cc zoals gaspedaal.nl die aanlevert, gemapt naar het label
# dat de fabrikant er zelf aan geeft. Nodig omdat wiskundig afronden van
# cc/1000 niet altijd klopt: de "2.2 JTDm"-diesel is bijvoorbeeld feitelijk
# 2143cc, wat naar 2.1 zou afronden. Vul aan als een motor verkeerd
# gelabeld wordt (zie normalize.label_engine_cc).
KNOWN_ENGINE_CC = {
    1995: "2.0L",
    2000: "2.0L",
    2143: "2.2L",
    2200: "2.2L",
    2891: "2.9L",
    2900: "2.9L",
}
