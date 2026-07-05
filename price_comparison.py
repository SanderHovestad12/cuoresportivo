"""Vergelijkt de vraagprijs van elke advertentie met vergelijkbare
advertenties (zelfde brandstof en uitvoering, dichtbij in bouwjaar en
km-stand) om te bepalen of een auto relatief laag, gemiddeld of hoog
geprijsd is.

Aanpak: voor elke advertentie wordt een "verwachte prijs" berekend als het
gewogen gemiddelde van vergelijkbare advertenties, waarbij advertenties die
qua bouwjaar en km-stand dichterbij zitten zwaarder meewegen. Is de
werkelijke vraagprijs meer dan 5% onder die verwachte prijs, dan is de auto
relatief "laag" geprijsd (mogelijk een koopje); meer dan 5% erboven is
"hoog"; daartussen is "neutraal".
"""
import math

import pandas as pd

MIN_COHORT_SIZE = 5
MARGIN_PCT = 5.0
YEAR_SCALE = 2.0       # een verschil van dit aantal jaar weegt even zwaar als...
MILEAGE_SCALE = 30_000.0  # ...dit aantal km verschil

LABELS = {"laag": "🟢 Laag", "neutraal": "⚪ Gemiddeld", "hoog": "🔴 Hoog"}


def _distance_weight(target, other):
    year_diff = 0.0
    if pd.notna(target["build_year"]) and pd.notna(other["build_year"]):
        year_diff = (target["build_year"] - other["build_year"]) / YEAR_SCALE

    km_diff = 0.0
    if pd.notna(target["mileage_km"]) and pd.notna(other["mileage_km"]):
        km_diff = (target["mileage_km"] - other["mileage_km"]) / MILEAGE_SCALE

    distance = math.sqrt(year_diff ** 2 + km_diff ** 2)
    return 1.0 / (1.0 + distance)


def _expected_price(target, cohort):
    if cohort.empty:
        return None
    weights = cohort.apply(lambda other: _distance_weight(target, other), axis=1)
    total_weight = weights.sum()
    if total_weight == 0:
        return None
    return (cohort["price"] * weights).sum() / total_weight


def _cohort_for(row, priced, self_index):
    """Kiest de meest specifieke groep vergelijkbare advertenties die groot
    genoeg is: eerst zelfde brandstof + uitvoering, anders alleen brandstof,
    anders alle geprijsde advertenties."""
    others = priced.drop(index=self_index)

    same_fuel = others[others["fuel_type"] == row["fuel_type"]] if pd.notna(row["fuel_type"]) else others.iloc[0:0]
    same_fuel_trim = same_fuel[same_fuel["trim"] == row["trim"]] if pd.notna(row["trim"]) else same_fuel.iloc[0:0]

    if len(same_fuel_trim) >= MIN_COHORT_SIZE:
        return same_fuel_trim
    if len(same_fuel) >= MIN_COHORT_SIZE:
        return same_fuel
    return others


def add_price_indicators(df):
    """Voegt 'expected_price', 'price_diff_pct' en 'price_indicator' (+ het
    bijbehorende leesbare 'price_indicator_label') toe aan een kopie van df."""
    df = df.copy()
    df["expected_price"] = pd.NA
    df["price_diff_pct"] = pd.NA
    df["price_indicator"] = pd.NA

    priced = df.dropna(subset=["price"])
    for idx, row in priced.iterrows():
        cohort = _cohort_for(row, priced, idx)
        expected = _expected_price(row, cohort[["price", "build_year", "mileage_km"]])
        if not expected:
            continue

        diff_pct = (row["price"] - expected) / expected * 100
        df.loc[idx, "expected_price"] = round(expected)
        df.loc[idx, "price_diff_pct"] = round(diff_pct, 1)
        if diff_pct <= -MARGIN_PCT:
            df.loc[idx, "price_indicator"] = "laag"
        elif diff_pct >= MARGIN_PCT:
            df.loc[idx, "price_indicator"] = "hoog"
        else:
            df.loc[idx, "price_indicator"] = "neutraal"

    df["price_indicator_label"] = df["price_indicator"].map(LABELS).fillna("–")
    return df
