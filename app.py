"""Streamlit-dashboard voor de Gaspedaal Stelvio Analyzer."""
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import config
import db
import geocode
import nieuwprijzen
import scraper

CURRENT_YEAR = date.today().year

# Vaste categorische kleurenreeks (CVD-gevalideerd, zie dataviz-richtlijnen).
CATEGORICAL = [
    "#2a78d6", "#1baf7a", "#eda100", "#008300",
    "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
]
FUEL_COLOR_MAP = {
    "Benzine": CATEGORICAL[0],
    "Diesel": CATEGORICAL[7],
    "Hybride": CATEGORICAL[1],
    "Elektrisch": CATEGORICAL[3],
}
SURFACE = "#fcfcfb"

APP_TITLE = "Alfa Romeo Stelvio Marktanalyse - by Sander"

st.set_page_config(page_title=APP_TITLE, page_icon="🚗", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    db.init_db()  # zorgt dat de tabellen bestaan, ook bij een verse/lege database
    return (
        db.fetch_listings_df(),
        db.fetch_price_history_df(),
        db.fetch_scrape_runs_df(),
        db.fetch_locations_df(),
    )


def format_euro(value):
    if value is None or pd.isna(value):
        return "–"
    return f"€ {value:,.0f}".replace(",", ".")


def format_km(value):
    if value is None or pd.isna(value):
        return "–"
    return f"{value:,.0f} km".replace(",", ".")


def style_chart(fig, x_title="", y_title=""):
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        margin=dict(t=10, l=10, r=10, b=10),
        font=dict(color="black"),
        legend=dict(font=dict(color="black")),
    )
    fig.update_xaxes(title_font=dict(color="black"), tickfont=dict(color="black"))
    fig.update_yaxes(title_font=dict(color="black"), tickfont=dict(color="black"))
    return fig


def counts_bar(df, column, title):
    st.subheader(title)
    counts = df[column].dropna().value_counts().reset_index()
    counts.columns = [column, "aantal"]
    if counts.empty:
        st.info("Geen data voor dit veld.")
        return
    fig = px.bar(counts, x=column, y="aantal", color_discrete_sequence=[CATEGORICAL[0]])
    fig.update_layout(xaxis=dict(type="category", categoryorder="total descending"))
    st.plotly_chart(style_chart(fig, y_title="Aantal advertenties"), use_container_width=True)


@st.dialog("Data verversen", width="large")
def refresh_data_dialog():
    log_lines = []
    log_box = st.empty()

    def on_log(message):
        log_lines.append(message)
        log_box.code("\n".join(log_lines), language=None)

    on_log("Bezig met scrapen van gaspedaal.nl...")
    try:
        result = scraper.run(max_pages=config.MAX_PAGES_SAFETY_CAP, debug=False, on_log=on_log)
    except Exception as exc:  # toon de fout in de popup i.p.v. hem stil te laten mislukken
        on_log(f"FOUT: {exc}")
        st.error(f"Verversen mislukt: {exc}")
        st.cache_data.clear()
        if st.button("Sluiten"):
            st.rerun()
        return

    st.cache_data.clear()
    if not result or not result.get("found"):
        st.warning(
            "Er zijn geen advertenties gevonden. Mogelijk blokkeert "
            "gaspedaal.nl dit verzoek (bv. omdat je vanaf een cloud-server "
            "draait), of is de paginastructuur gewijzigd. Bekijk de log "
            "hierboven voor details."
        )
    else:
        st.success(f"{result['found']} advertenties gevonden, waarvan {result['new']} nieuw.")

    if st.button("Sluiten en dashboard bijwerken"):
        st.rerun()


def main():
    st.title(f"🚗 {APP_TITLE}")
    st.caption("Marktanalyse op basis van advertenties van gaspedaal.nl")

    st.sidebar.header("Data")
    if st.sidebar.button("🔄 Data verversen"):
        refresh_data_dialog()
    st.sidebar.caption(
        "Haalt de actuele advertenties op van gaspedaal.nl en toont de "
        "voortgang in een popup. Zichtbaar voor iedereen die deze app "
        "bezoekt — beperk de toegang via de deel-instellingen van Streamlit "
        "als je dat niet wilt."
    )

    listings, history, runs, locations = load_data()

    if listings.empty:
        st.warning(
            "Nog geen data gevonden. Klik in de zijbalk op **'Data "
            "verversen'**, of draai lokaal in de terminal:\n\n"
            "`python scraper.py`\n\n"
            "en herlaad daarna deze pagina."
        )
        st.stop()

    st.sidebar.divider()
    st.sidebar.header("Filters")
    only_active = st.sidebar.checkbox("Alleen actieve advertenties", value=True)
    df = listings[listings["is_active"] == 1].copy() if only_active else listings.copy()

    if df["build_year"].notna().any():
        year_min, year_max = int(df["build_year"].min()), int(df["build_year"].max())
        if year_min < year_max:
            year_range = st.sidebar.slider("Bouwjaar", year_min, year_max, (year_min, year_max))
            df = df[df["build_year"].between(*year_range)]

    if df["price"].notna().any():
        price_min, price_max = int(df["price"].min()), int(df["price"].max())
        if price_min < price_max:
            price_range = st.sidebar.slider("Prijs (€)", price_min, price_max, (price_min, price_max), step=500)
            df = df[df["price"].between(*price_range)]

    for column, label in [
        ("fuel_type", "Brandstof"),
        ("engine", "Motorisering"),
        ("trim", "Uitvoering"),
        ("color", "Kleur"),
    ]:
        options = sorted(df[column].dropna().unique().tolist())
        if not options:
            continue
        selected = st.sidebar.multiselect(label, options)
        if selected:
            df = df[df[column].isin(selected)]

    if not df.empty:
        matches = df.apply(
            lambda r: nieuwprijzen.estimate_nieuwprijs(r["build_year"], r["fuel_type"], r["power_hp"], r["trim"]),
            axis=1, result_type="expand",
        )
        df["nieuwprijs"] = matches[0]
        df["nieuwprijs_referentie"] = matches[1]
        df["afschrijving_pct"] = 100 - (df["price"] / df["nieuwprijs"] * 100)
    else:
        df["nieuwprijs"] = None
        df["nieuwprijs_referentie"] = None
        df["afschrijving_pct"] = None

    st.caption(f"{len(df)} advertenties op basis van de huidige filters (van {len(listings)} totaal in de database).")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Aantal advertenties", len(df))
    col2.metric("Gemiddelde vraagprijs", format_euro(df["price"].mean()))
    col3.metric(
        "Mediaan bouwjaar",
        int(df["build_year"].median()) if df["build_year"].notna().any() else "–",
    )
    col4.metric("Gemiddelde km-stand", format_km(df["mileage_km"].mean()))

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("Prijsverdeling")
        price_df = df.dropna(subset=["price"])
        if price_df.empty:
            st.info("Geen prijsdata beschikbaar.")
        else:
            fig = px.histogram(price_df, x="price", nbins=30, color_discrete_sequence=[CATEGORICAL[0]])
            fig.update_layout(bargap=0.1)
            st.plotly_chart(style_chart(fig, "Vraagprijs (€)", "Aantal advertenties"), use_container_width=True)

    with right:
        st.subheader("Bouwjaar vs. vraagprijs")
        scatter_df = df.dropna(subset=["build_year", "price"])
        if scatter_df.empty:
            st.info("Geen data beschikbaar voor deze vergelijking.")
        else:
            fig = px.scatter(
                scatter_df, x="build_year", y="price", color="fuel_type",
                color_discrete_map=FUEL_COLOR_MAP,
                hover_data=["title", "mileage_km", "trim", "color"],
            )
            st.plotly_chart(style_chart(fig, "Bouwjaar", "Vraagprijs (€)"), use_container_width=True)

    st.divider()
    st.subheader("Waardebehoud: bouwjaar, km-stand en afschrijving")
    st.caption(
        "Afschrijving = huidige vraagprijs t.o.v. de oorspronkelijke "
        "nieuwprijs van die uitvoering/motorisering in het bouwjaar van de "
        "auto (bron: AutoWeek.nl Carbase, zie `nieuwprijzen.py`). Bij een "
        "onzekere uitvoering wordt de dichtstbijzijnde match op vermogen en "
        "bouwjaar gebruikt — zie kolom 'nieuwprijs (bron)' in de "
        "advertentietabel onderaan voor de gebruikte referentie."
    )

    dep_df = df.dropna(subset=["build_year", "price", "afschrijving_pct"]).copy()
    if dep_df.empty:
        st.info("Onvoldoende data voor deze analyse.")
    else:
        match_rate = len(dep_df) / len(df) * 100 if len(df) else 0
        dep_df["leeftijd"] = CURRENT_YEAR - dep_df["build_year"]
        gem_afschrijving = dep_df["afschrijving_pct"].mean()
        gem_leeftijd = dep_df["leeftijd"].mean()
        decline_per_year = gem_afschrijving / gem_leeftijd if gem_leeftijd > 0 else None

        kpi_a, kpi_b, kpi_c = st.columns(3)
        kpi_a.metric("Gem. afschrijving t.o.v. nieuwprijs", f"{gem_afschrijving:.0f}%")
        kpi_b.metric("Gem. waardedaling per jaar", f"{decline_per_year:.1f}%/jaar" if decline_per_year else "–")
        kpi_c.metric("Gem. leeftijd", f"{gem_leeftijd:.1f} jaar")
        st.caption(f"Nieuwprijs kon voor {len(dep_df)} van de {len(df)} advertenties ({match_rate:.0f}%) worden bepaald.")

        year_stats = (
            dep_df.groupby("build_year")
            .agg(
                gemiddelde_prijs=("price", "mean"),
                gem_afschrijving=("afschrijving_pct", "mean"),
                aantal=("price", "size"),
            )
            .reset_index()
        )

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Gemiddelde vraagprijs per bouwjaar**")
            fig = px.line(year_stats, x="build_year", y="gemiddelde_prijs", markers=True,
                          color_discrete_sequence=[CATEGORICAL[0]], hover_data={"aantal": True})
            st.plotly_chart(style_chart(fig, "Bouwjaar", "Gemiddelde vraagprijs (€)"), use_container_width=True)

        with col_b:
            st.markdown("**Gemiddelde afschrijving t.o.v. nieuwprijs, per bouwjaar**")
            fig = px.bar(year_stats, x="build_year", y="gem_afschrijving", text="gem_afschrijving",
                         color_discrete_sequence=[CATEGORICAL[5]])
            fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            fig.update_layout(
                xaxis=dict(type="category"),
                yaxis=dict(range=[0, year_stats["gem_afschrijving"].max() * 1.2]),
            )
            st.plotly_chart(style_chart(fig, "Bouwjaar", "Afschrijving (%)"), use_container_width=True)

        mileage_df = dep_df.dropna(subset=["mileage_km"]).copy()
        if not mileage_df.empty:
            km_bins = [0, 25_000, 50_000, 75_000, 100_000, 125_000, 150_000, 200_000, float("inf")]
            km_labels = ["0-25k", "25-50k", "50-75k", "75-100k", "100-125k", "125-150k", "150-200k", "200k+"]
            mileage_df["km_bucket"] = pd.cut(mileage_df["mileage_km"], bins=km_bins, labels=km_labels, right=False)

            col_c, col_d = st.columns(2)
            with col_c:
                st.markdown("**Gemiddelde afschrijving per km-stand**")
                km_stats = mileage_df.groupby("km_bucket", observed=True)["afschrijving_pct"].mean().reset_index()
                fig = px.bar(km_stats, x="km_bucket", y="afschrijving_pct", color_discrete_sequence=[CATEGORICAL[5]])
                fig.update_layout(xaxis=dict(type="category"))
                st.plotly_chart(style_chart(fig, "Km-stand", "Gemiddelde afschrijving (%)"), use_container_width=True)

            with col_d:
                st.markdown("**Afschrijving % naar bouwjaar × km-stand**")
                pivot = mileage_df.pivot_table(
                    index="build_year", columns="km_bucket", values="afschrijving_pct", aggfunc="mean", observed=True,
                )
                if pivot.empty:
                    st.info("Onvoldoende data voor deze matrix.")
                else:
                    fig = px.imshow(
                        pivot, aspect="auto", origin="lower",
                        color_continuous_scale=["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"],
                        labels=dict(x="Km-stand", y="Bouwjaar", color="Gem. afschrijving (%)"),
                    )
                    fig.update_layout(coloraxis_colorbar=dict(
                        tickfont=dict(color="black"), title_font=dict(color="black"),
                    ))
                    st.plotly_chart(style_chart(fig), use_container_width=True)

    left2, right2 = st.columns(2)
    with left2:
        counts_bar(df, "engine", "Aantal per motorisering")
    with right2:
        st.subheader("Gemiddelde prijs per motorisering")
        avg_df = df.dropna(subset=["price", "engine"])
        if avg_df.empty:
            st.info("Geen data beschikbaar.")
        else:
            avg_price = (
                avg_df.groupby("engine")["price"].mean().sort_values(ascending=False)
                .head(10).reset_index()
            )
            fig = px.bar(avg_price, x="engine", y="price", color_discrete_sequence=[CATEGORICAL[1]])
            fig.update_layout(xaxis=dict(type="category", categoryorder="total descending"))
            st.plotly_chart(style_chart(fig, y_title="Gemiddelde vraagprijs (€)"), use_container_width=True)

    left3, right3 = st.columns(2)
    with left3:
        counts_bar(df, "color", "Kleurverdeling")
    with right3:
        counts_bar(df, "trim", "Uitvoeringen")

    st.divider()
    st.subheader("Waar staan de advertenties te koop?")
    map_df = df.dropna(subset=["location"]).copy()
    map_df["city"] = map_df["location"].apply(geocode.extract_city)
    map_df = map_df.merge(locations, on="city", how="left").dropna(subset=["lat", "lon"])

    if map_df.empty:
        st.info(
            "Nog geen locaties op de kaart. Draai `python scraper.py` opnieuw "
            "-- nieuwe plaatsen worden dan automatisch eenmalig gegeocodeerd "
            "via OpenStreetMap/Nominatim en opgeslagen in de database."
        )
    else:
        city_stats = (
            map_df.groupby(["city", "lat", "lon"])
            .agg(aantal=("price", "size"), gemiddelde_prijs=("price", "mean"))
            .reset_index()
        )
        city_stats["gem_prijs_fmt"] = city_stats["gemiddelde_prijs"].apply(format_euro)
        fig = px.scatter_map(
            city_stats, lat="lat", lon="lon", size="aantal", color="gemiddelde_prijs",
            hover_name="city",
            hover_data={"aantal": True, "gem_prijs_fmt": True, "gemiddelde_prijs": False, "lat": False, "lon": False},
            color_continuous_scale=["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"],
            size_max=32, zoom=6, center={"lat": 52.2, "lon": 5.3}, map_style="open-street-map",
        )
        fig.update_layout(
            margin=dict(t=0, l=0, r=0, b=0),
            height=520,
            coloraxis_colorbar=dict(
                title="Gem. prijs (€)", tickfont=dict(color="black"), title_font=dict(color="black"),
            ),
        )
        st.plotly_chart(fig, use_container_width=True)
        matched_pct = len(map_df) / len(df) * 100 if len(df) else 0
        st.caption(
            f"{len(map_df)} van de {len(df)} advertenties ({matched_pct:.0f}%) konden op de "
            "kaart geplaatst worden. Bolgrootte = aantal advertenties, kleur = gemiddelde "
            "vraagprijs in die plaats."
        )

    if not history.empty:
        st.divider()
        st.subheader("Prijstrend over tijd (gemiddelde per scrape-moment)")
        trend = history.groupby("seen_at")["price"].mean().reset_index()
        fig = px.line(trend, x="seen_at", y="price", color_discrete_sequence=[CATEGORICAL[0]])
        fig.update_traces(mode="lines+markers")
        st.plotly_chart(style_chart(fig, "Scrape-moment", "Gemiddelde prijs (€)"), use_container_width=True)

    st.divider()
    st.subheader("Advertenties")
    show_cols = [
        c for c in [
            "title", "build_year", "price", "nieuwprijs", "afschrijving_pct", "mileage_km",
            "fuel_type", "engine", "power_hp", "transmission", "color", "trim", "location",
            "is_active", "nieuwprijs_referentie", "url",
        ] if c in df.columns
    ]
    st.dataframe(
        df[show_cols].sort_values("price", na_position="last"),
        column_config={
            "url": st.column_config.LinkColumn("Advertentie"),
            "price": st.column_config.NumberColumn("Vraagprijs", format="€ %d"),
            "nieuwprijs": st.column_config.NumberColumn("Nieuwprijs (schatting)", format="€ %d"),
            "afschrijving_pct": st.column_config.NumberColumn("Afschrijving", format="%.0f%%"),
            "nieuwprijs_referentie": st.column_config.TextColumn("Nieuwprijs (bron)"),
        },
        use_container_width=True,
        hide_index=True,
    )

    if not runs.empty:
        last_run = runs.iloc[-1]
        st.caption(f"Laatste scrape: {last_run['run_at']} — {last_run['listings_found']} advertenties gevonden.")


if __name__ == "__main__":
    main()
