"""Hulpfuncties om ruwe teksten van gaspedaal.nl om te zetten naar bruikbare types."""
import re

from config import KNOWN_TRIMS

_NUM_RE = re.compile(r"[\d.,]+")


def parse_int(text):
    if text is None:
        return None
    match = _NUM_RE.search(str(text).replace("\xa0", " "))
    if not match:
        return None
    digits = match.group(0).replace(".", "").replace(",", "")
    if not digits.isdigit():
        return None
    return int(digits)


def parse_price(text):
    return parse_int(text)


def parse_year(text):
    if text is None:
        return None
    match = re.search(r"(19|20)\d{2}", str(text))
    return int(match.group(0)) if match else None


def parse_mileage(text):
    return parse_int(text)


def parse_power(text):
    return parse_int(text)


def guess_fuel(text):
    if not text:
        return None
    t = text.lower()
    if "diesel" in t or "jtdm" in t:
        return "Diesel"
    if "hybrid" in t or "phev" in t:
        return "Hybride"
    if "elektr" in t or "ev" in t.split():
        return "Elektrisch"
    if "benzine" in t or "turbo" in t or "multiair" in t:
        return "Benzine"
    return None


def guess_trim(title):
    """Zoekt een bekende uitvoeringsnaam in de titel, op woordgrenzen (dus
    niet "Ti" laten matchen binnen "Edition"). Bij meerdere treffers wint de
    langste/specifiekste naam."""
    if not title:
        return None
    matches = [t for t in KNOWN_TRIMS if re.search(rf"\b{re.escape(t)}\b", title, re.IGNORECASE)]
    return max(matches, key=len) if matches else None


def guess_engine(title):
    """Haalt de motorinhoud (bv. '2.0L') uit de titel, in hetzelfde formaat als
    de motorinhoud die rechtstreeks uit de structured data komt, zodat beide
    bronnen in het dashboard in dezelfde categorie vallen."""
    if not title:
        return None
    match = re.search(r"\d\.\d", title)
    return f"{match.group(0)}L" if match else None


def clean(text):
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned or None
