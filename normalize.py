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
    if not title:
        return None
    for trim in KNOWN_TRIMS:
        if trim.lower() in title.lower():
            return trim
    return None


def guess_engine(title):
    """Probeert een motoraanduiding zoals '2.0 Turbo' uit de titel te halen."""
    if not title:
        return None
    match = re.search(r"\d\.\d\s?\w*", title)
    return match.group(0).strip() if match else None


def clean(text):
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned or None
