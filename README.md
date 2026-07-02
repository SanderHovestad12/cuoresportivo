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

- **De parsing-logica is geverifieerd tegen een echte zoekpagina** van
  gaspedaal.nl (aangeleverd door de gebruiker, aangezien de ontwikkelomgeving
  zelf geen toegang tot de site had). Gaspedaal.nl is een Next.js-app die de
  volledige advertentiedata (prijs, bouwjaar, km-stand, motor, kleur,
  uitvoering, verkoper, ...) als gestructureerde JSON meestuurt in de HTML
  (in `<script>self.__next_f.push(...)</script>`-tags). De scraper leest die
  JSON rechtstreeks uit — dat is veel betrouwbaarder dan de zichtbare HTML
  parsen, en betekent ook dat er **geen aparte detailpagina's per
  advertentie** hoeven te worden opgehaald: alle velden staan al op de
  zoekresultatenpagina. Mocht gaspedaal.nl deze opzet ooit wijzigen, dan valt
  het script terug op het parsen van de zichtbare advertentiekaarten. Zie
  **"Als de scraper niets vindt"** verderop.
- Gaspedaal.nl is zelf een vergelijkingssite: er is geen eigen
  gaspedaal-detailpagina per auto. De `url` van elke advertentie in de
  database is daarom een redirect-link (`api.gaspedaal.nl/redirect/...`) naar
  de daadwerkelijke bron (dealersite, AutoTrack, AutoScout24, ...).
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
python scraper.py
```

Dit doorloopt alle zoekresultaatpagina's voor de Alfa Romeo Stelvio (het
aantal pagina's wordt automatisch door gaspedaal.nl zelf meegegeven) en
slaat elke advertentie direct met alle velden op — er worden geen losse
detailpagina's opgehaald.

- `--max-pages N` beperkt het aantal zoekresultaatpagina's als
  veiligheidsmarge (standaard 30; gaspedaal.nl geeft zelf aan hoeveel
  pagina's er daadwerkelijk zijn).
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
- **Waardebehoud & afschrijving**: gemiddelde prijs per bouwjaar en per
  km-stand, restwaarde (%) per bouwjaar t.o.v. het nieuwste bouwjaar in de
  selectie, gemiddelde waardedaling per jaar, en een prijsmatrix van
  bouwjaar × km-stand. Dit is een marktindicatie op basis van huidige
  vraagprijzen (er is geen nieuwprijs-data beschikbaar) — filter op één
  motorisering voor een eerlijke vergelijking.
- Aantal en gemiddelde prijs per motorisering
- Verdeling van kleuren en uitvoeringen
- Prijstrend over tijd (op basis van meerdere scrape-runs)
- Doorzoekbare tabel met links naar de originele advertenties

## Als de scraper niets vindt

Als gaspedaal.nl zijn pagina-opbouw wijzigt, kan het zijn dat de aannames in
dit script niet meer kloppen. Ga dan zo te werk:

1. Draai `python scraper.py --debug --max-pages 1`.
2. Open `debug/search_page_1.html` en zoek naar `self.__next_f.push` — dat
   is de plek waar de advertentiedata als JSON in de pagina staat
   (`scraper.extract_listings_from_json`). Vergelijk de veldnamen
   (`advertentieId`, `prijs`, `autogegevens.algemeen.kleur`, enz.) met wat je
   in het bestand ziet.
3. Vind je die JSON niet meer terug, zoek dan naar
   `data-testid="occasion-item"` (de zichtbare advertentiekaarten) — dat is
   waar de fallback `scraper.parse_occasion_cards` op leunt.
4. Pas de betreffende functie in `scraper.py` aan op de nieuwe structuur.
5. Tip: kijk ook in de browser-devtools onder "Network" of gaspedaal.nl de
   resultaten inmiddels via een apart JSON/XHR-verzoek laadt — dat zou een
   nog stabielere databron zijn dan beide huidige strategieën.

## Projectstructuur

```
config.py      Instellingen: URL's, wachttijden, veldmapping, bekende trims
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
