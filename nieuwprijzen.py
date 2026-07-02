"""Historische nieuwprijzen van de Alfa Romeo Stelvio, gebruikt om de
werkelijke afschrijving (huidige vraagprijs t.o.v. oorspronkelijke
nieuwprijs) te berekenen.

Bron: de "Carbase" van AutoWeek.nl
(https://www.autoweek.nl/carbase/alfa-romeo/stelvio/), die per
uitvoering/motorisering de catalogusprijs vermeldt zoals die gold in het
bouwjaarbereik waarin die versie werd verkocht. Dit is bewust een vaste,
in de repo opgeslagen tabel (net als config.KNOWN_TRIMS) in plaats van een
live scrape: de tabel verandert nauwelijks en dit voorkomt afhankelijkheid
van een tweede site tijdens elke scraper-run.

Elke rij: (titel, vanaf-bouwjaar, tot-bouwjaar, brandstof, vermogen in pk,
nieuwprijs in euro's). Vul aan met `python -c` of handmatig als AutoWeek de
carbase bijwerkt met nieuwe uitvoeringen.
"""
import pandas as pd

PRICE_TABLE = [
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Sprint", 2023, 2025, "Benzine", 280, 84100),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Ti", 2023, 2023, "Benzine", 280, 80675),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Veloce", 2023, 2026, "Benzine", 280, 92900),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Competizione", 2023, 2023, "Benzine", 280, 89175),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Tributo Italiano", 2023, 2025, "Benzine", 280, 97100),
    ("Alfa Romeo Stelvio Quadrifoglio", 2023, 2026, "Benzine", 510, 185900),
    ("Alfa Romeo Stelvio 2.2 JTD 210pk AWD Sprint", 2023, 2025, "Diesel", 210, 77100),
    ("Alfa Romeo Stelvio 2.2 JTD 210pk AWD Ti", 2023, 2023, "Diesel", 210, 75025),
    ("Alfa Romeo Stelvio 2.2 JTD 210pk AWD Veloce", 2023, 2025, "Diesel", 210, 82600),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD", 2020, 2021, "Benzine", 200, 63905),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD Super", 2020, 2023, "Benzine", 200, 68775),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD Sprint", 2020, 2023, "Benzine", 200, 70775),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD Ti", 2020, 2023, "Benzine", 200, 75775),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Veloce", 2020, 2023, "Benzine", 280, 80775),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Veloce Ti", 2021, 2022, "Benzine", 280, 82335),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Villa d'Este", 2021, 2022, "Benzine", 280, 81865),
    ("Alfa Romeo Stelvio 2.9 V6 AWD Quadrifoglio", 2020, 2023, "Benzine", 510, 140825),
    ("Alfa Romeo Stelvio 2.2 JTD 190pk Super", 2020, 2021, "Diesel", 190, 64915),
    ("Alfa Romeo Stelvio 2.2 JTD 190pk Sprint", 2020, 2021, "Diesel", 190, 67555),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD", 2017, 2019, "Benzine", 200, 59825),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD Super", 2017, 2019, "Benzine", 200, 62825),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD Super Business Edition", 2019, 2020, "Benzine", 200, 59190),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD B-Tech", 2018, 2019, "Benzine", 200, 68825),
    ("Alfa Romeo Stelvio 2.0T 200pk AWD B-Tech Business Edition", 2019, 2020, "Benzine", 200, 64825),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Super", 2017, 2019, "Benzine", 280, 67325),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD Super Business Edition", 2019, 2020, "Benzine", 280, 63690),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD B-Tech", 2018, 2019, "Benzine", 280, 73325),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD B-Tech Super Business Edition", 2019, 2020, "Benzine", 280, 69325),
    ("Alfa Romeo Stelvio 2.0T 280pk AWD First Edition", 2017, 2018, "Benzine", 280, 67325),
]


def _valid(value):
    """True voor bruikbare waarden; False voor None/lege string en voor NaN
    (pandas geeft ontbrekende waarden terug als een NaN-float, niet als
    None -- en NaN is 'truthy' in Python, dus een simpele `if value` check
    is niet genoeg)."""
    if value is None or value == "":
        return False
    try:
        return not pd.isna(value)
    except (TypeError, ValueError):
        return True


def _year_distance(build_year, vanaf, tot):
    if build_year < vanaf:
        return vanaf - build_year
    if build_year > tot:
        return build_year - tot
    return 0


def estimate_nieuwprijs(build_year, fuel_type, power_hp, trim):
    """Schat de nieuwprijs van een advertentie op basis van bouwjaar (!),
    brandstof, vermogen en uitvoering. Geeft (nieuwprijs, referentietitel)
    terug, of (None, None) als er onvoldoende gegevens zijn om te matchen."""
    if not _valid(build_year):
        return None, None
    build_year = int(build_year)

    candidates = list(PRICE_TABLE)
    if _valid(fuel_type):
        fuel_matches = [c for c in candidates if c[3] == fuel_type]
        if fuel_matches:
            candidates = fuel_matches

    # Eerst alleen de rijen waarvan het bouwjaar daadwerkelijk in het
    # verkoopbereik valt; is dat er geen, pak dan het dichtstbijzijnde bereik.
    exact_year = [c for c in candidates if c[1] <= build_year <= c[2]]
    if exact_year:
        candidates = exact_year
    else:
        min_distance = min(_year_distance(build_year, c[1], c[2]) for c in candidates)
        candidates = [c for c in candidates if _year_distance(build_year, c[1], c[2]) == min_distance]

    if _valid(trim):
        trim_matches = [c for c in candidates if trim.lower() in c[0].lower()]
        if trim_matches:
            candidates = trim_matches

    if _valid(power_hp):
        candidates.sort(key=lambda c: abs((c[4] or 0) - power_hp))
    else:
        candidates.sort(key=lambda c: c[5])

    best = candidates[0]
    return best[5], best[0]
