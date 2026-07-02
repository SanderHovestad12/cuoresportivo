# Alfa Romeo Stelvio Analyzer

Een kleine webapp om advertenties van [gaspedaal.nl](https://www.gaspedaal.nl)
voor de **Alfa Romeo Stelvio** te verzamelen en te analyseren: verdeling van
motoriseringen, bouwjaren, kleuren en uitvoeringen, en inzicht in de
aanschafwaarde (vraagprijs) per segment.

Bestaat uit twee delen:

1. **`scraper.py`** – haalt advertenties op van gaspedaal.nl en slaat ze op in
   een lokale SQLite-database (`data/stelvio.db`).
2. **`app.py`** – een Streamlit-dashboard dat die database uitleest en
   interactieve grafieken en filters toont.

## Belangrijk om te weten

- **Dit script is gebouwd zonder live toegang tot gaspedaal.nl.** De sandbox
  waarin dit is ontwikkeld blokkeert uitgaand internetverkeer naar de site,
  dus de scraper kon hier niet tegen de echte site getest worden. De
  parsing-logica is bewust defensief opgezet (meerdere fallback-strategieën,
  zie hieronder), maar het is goed mogelijk dat je bij het eerste gebruik
  iets moet bijstellen als de site een andere structuur blijkt te hebben.
  Zie **"Als de scraper niets vindt"** verderop.
- **Gebruik dit alleen voor persoonlijk, niet-commercieel onderzoek** (bv. om
  zelf een auto te kopen), en met mate. Het script respecteert standaard een
  wachttijd van 2,5–5 seconden tussen requests om de site niet te belasten.
  Controleer zelf ook de gebruiksvoorwaarden/robots.txt van gaspedaal.nl
  voordat je dit intensief gebruikt — sommige sites staan geautomatiseerd
  ophalen niet toe.
- Advertenties die niet meer worden teruggevonden bij een nieuwe scrape
  worden gemarkeerd als `is_active = 0` (waarschijnlijk verkocht/verwijderd),
  maar blijven in de database staan voor historische analyse.

## Installatie

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Gebruik

### 1. Data verzamelen

```bash
python scraper.py --details
```

- `--details` haalt per advertentie ook de detailpagina op voor motorisering,
  kleur, uitvoering, transmissie, vermogen en km-stand. Dit is nodig voor
  zinvolle analyse, maar duurt langer (2,5–5 sec per advertentie).
- `--ids-only` verzamelt alleen welke advertenties er zijn, zonder
  detailpagina's op te halen (snel, maar zonder motorisering/kleur/etc.).
- `--max-pages N` beperkt het aantal zoekresultaatpagina's (standaard 20).
- `--debug` slaat de ruwe HTML van elke opgehaalde pagina op in `debug/`, zodat
  je kunt controleren of de parsing nog klopt.

Draai dit script periodiek (bv. 1x per dag, handmatig of via cron/Taakplanner)
om de dataset actueel te houden en prijstrends over tijd op te bouwen.

### 2. Dashboard bekijken

```bash
streamlit run app.py
```

Opent een lokaal dashboard in je browser met filters op bouwjaar, prijs,
brandstof, motorisering, uitvoering en kleur, plus:

- KPI's: aantal advertenties, gemiddelde vraagprijs, mediaan bouwjaar, gemiddelde km-stand
- Prijsverdeling en bouwjaar-vs-prijs (depreciatie)
- Aantal en gemiddelde prijs per motorisering
- Verdeling van kleuren en uitvoeringen
- Prijstrend over tijd (op basis van meerdere scrape-runs)
- Doorzoekbare tabel met links naar de originele advertenties

## Als de scraper niets vindt

Omdat dit niet tegen de live site getest kon worden, kan het zijn dat de
aannames over de paginastructuur niet (meer) kloppen. Ga dan zo te werk:

1. Draai `python scraper.py --debug --max-pages 1`.
2. Bekijk `debug/search_page_1.html` (en eventuele `debug/detail_*.html`) en
   vergelijk met wat je in de browser ziet via "Element inspecteren" (F12).
3. Pas zo nodig aan in:
   - `scraper.py` → `find_listing_urls_fallback` / `urls_from_json`: hoe
     advertentie-links op de zoekpagina herkend worden.
   - `config.LABEL_MAP`: de Nederlandse veldlabels ("Kleur", "Uitvoering",
     ...) zoals ze daadwerkelijk op de detailpagina staan.
4. Tip: kijk in de browser-devtools onder het "Network"-tabblad of
   gaspedaal.nl de resultaten via een los JSON/XHR-verzoek laadt — als dat zo
   is, is dat vaak een veel stabielere databron dan de HTML zelf.

## Projectstructuur

```
config.py      Instellingen: URL's, wachttijden, labelmapping, bekende trims
normalize.py   Parsing/normalisatie van ruwe tekst (prijs, jaar, km, merk-varianten)
db.py          SQLite-schema en lees/schrijf-functies
scraper.py     Ophalen en parsen van gaspedaal.nl
app.py         Streamlit-dashboard
data/          SQLite-database (niet in git)
debug/         Opgeslagen ruwe HTML bij --debug (niet in git)
```

## Database-schema

**`listings`**: `id, url, title, price, build_year, mileage_km, fuel_type,
engine, power_hp, transmission, color, trim, body_type, location,
seller_type, first_seen, last_seen, is_active`

**`price_history`**: `listing_id, price, seen_at` — een rij per scrape waarbij
de prijs van een advertentie is vastgelegd (voor trendanalyse).

**`scrape_runs`**: `run_at, listings_found, listings_new` — log van elke
scraper-run.
