"""SQLite-opslag voor Stelvio-advertenties."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    price INTEGER,
    build_year INTEGER,
    mileage_km INTEGER,
    fuel_type TEXT,
    engine TEXT,
    power_hp INTEGER,
    transmission TEXT,
    color TEXT,
    trim TEXT,
    body_type TEXT,
    location TEXT,
    seller_type TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS price_history (
    listing_id TEXT NOT NULL,
    price INTEGER NOT NULL,
    seen_at TEXT NOT NULL,
    FOREIGN KEY (listing_id) REFERENCES listings (id)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_at TEXT PRIMARY KEY,
    listings_found INTEGER,
    listings_new INTEGER
);
"""

# Kolommen die bij een update overschreven mogen worden, maar alleen als de
# nieuwe scrape er daadwerkelijk een waarde voor heeft gevonden (COALESCE
# behoudt anders de oude waarde, bv. kleur uit een eerdere detail-scrape).
_UPDATABLE_FIELDS = [
    "title", "price", "build_year", "mileage_km", "fuel_type", "engine",
    "power_hp", "transmission", "color", "trim", "body_type", "location",
    "seller_type",
]


@contextmanager
def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_listing(conn, listing, now):
    """Voegt een advertentie toe of werkt hem bij. Geeft True terug als nieuw."""
    existing = conn.execute(
        "SELECT price, first_seen FROM listings WHERE id = ?", (listing["id"],)
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO listings (
                id, url, title, price, build_year, mileage_km, fuel_type,
                engine, power_hp, transmission, color, trim, body_type,
                location, seller_type, first_seen, last_seen, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                listing["id"], listing["url"], listing.get("title"),
                listing.get("price"), listing.get("build_year"),
                listing.get("mileage_km"), listing.get("fuel_type"),
                listing.get("engine"), listing.get("power_hp"),
                listing.get("transmission"), listing.get("color"),
                listing.get("trim"), listing.get("body_type"),
                listing.get("location"), listing.get("seller_type"),
                now, now,
            ),
        )
        if listing.get("price") is not None:
            conn.execute(
                "INSERT INTO price_history (listing_id, price, seen_at) VALUES (?, ?, ?)",
                (listing["id"], listing["price"], now),
            )
        return True

    set_clause = ", ".join(f"{f} = COALESCE(?, {f})" for f in _UPDATABLE_FIELDS)
    conn.execute(
        f"UPDATE listings SET {set_clause}, last_seen = ?, is_active = 1 WHERE id = ?",
        [listing.get(f) for f in _UPDATABLE_FIELDS] + [now, listing["id"]],
    )

    if listing.get("price") is not None and listing["price"] != existing["price"]:
        conn.execute(
            "INSERT INTO price_history (listing_id, price, seen_at) VALUES (?, ?, ?)",
            (listing["id"], listing["price"], now),
        )
    return False


def mark_inactive(conn, seen_ids, now):
    """Zet advertenties die niet meer gevonden zijn op inactief (verkocht/verwijderd)."""
    seen_ids = list(seen_ids)
    placeholders = ",".join("?" for _ in seen_ids) or "''"
    conn.execute(
        f"UPDATE listings SET is_active = 0 WHERE is_active = 1 AND id NOT IN ({placeholders})",
        seen_ids,
    )


def record_run(conn, now, found, new):
    conn.execute(
        "INSERT OR REPLACE INTO scrape_runs (run_at, listings_found, listings_new) VALUES (?, ?, ?)",
        (now, found, new),
    )


def fetch_listings_df():
    with connect() as conn:
        return pd.read_sql_query("SELECT * FROM listings", conn)


def fetch_price_history_df():
    with connect() as conn:
        return pd.read_sql_query("SELECT * FROM price_history", conn)


def fetch_scrape_runs_df():
    with connect() as conn:
        return pd.read_sql_query("SELECT * FROM scrape_runs ORDER BY run_at", conn)
