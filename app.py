"""Streamlit-dashboard voor de Gaspedaal Stelvio Analyzer."""
import pandas as pd
import plotly.express as px
import streamlit as st

import db

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

st.set_page_config(page_title="Alfa Romeo Stelvio Analyzer", page_icon="🚗", layout="wide")


@st.cache_data(ttl=300)
def load_data():
    return db.fetch_listings_df(), db.fetch_price_history_df(), db.fetch_scrape_runs_df()


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


def main():
    st.title("🚗 Alfa Romeo Stelvio – marktanalyse (gaspedaal.nl)")

    listings, history, runs = load_data()

    if listings.empty:
        st.warning(
            "Nog geen data gevonden. Draai eerst in de terminal:\n\n"
            "`python scraper.py --details`\n\n"
            "en herlaad daarna deze pagina."
        )
        st.stop()

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
        "Gebaseerd op de huidige vraagprijzen van advertenties, niet op de "
        "oorspronkelijke nieuwprijs — dit is een marktindicatie van "
        "waardebehoud, geen exacte afschrijvingsberekening. Filter in de "
        "zijbalk op één motorisering voor een eerlijkere vergelijking, "
        "anders vertekent de mix van motoren per bouwjaar het beeld."
    )

    dep_df = df.dropna(subset=["build_year", "price"]).copy()
    if dep_df.empty:
        st.info("Onvoldoende data voor deze analyse.")
    else:
        year_stats = (
            dep_df.groupby("build_year")
            .agg(gemiddelde_prijs=("price", "mean"), aantal=("price", "size"))
            .reset_index()
        )
        newest_year = year_stats["build_year"].max()
        oldest_year = year_stats["build_year"].min()
        newest_price = year_stats.loc[year_stats["build_year"] == newest_year, "gemiddelde_prijs"].iloc[0]
        year_stats["restwaarde_pct"] = year_stats["gemiddelde_prijs"] / newest_price * 100
        oldest_restwaarde = year_stats.loc[year_stats["build_year"] == oldest_year, "restwaarde_pct"].iloc[0]

        kpi_a, kpi_b, kpi_c = st.columns(3)
        kpi_a.metric(f"Restwaarde bouwjaar {int(oldest_year)}", f"{oldest_restwaarde:.0f}%",
                     help=f"T.o.v. de gemiddelde vraagprijs van bouwjaar {int(newest_year)} (= 100%) in de huidige selectie.")
        years_span = newest_year - oldest_year
        if years_span > 0:
            avg_decline = (100 - oldest_restwaarde) / years_span
            kpi_b.metric("Gem. waardedaling per jaar", f"{avg_decline:.1f}%/jaar")
        else:
            kpi_b.metric("Gem. waardedaling per jaar", "–")
        kpi_c.metric("Nieuwste bouwjaar in selectie", int(newest_year))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Gemiddelde vraagprijs per bouwjaar**")
            fig = px.line(year_stats, x="build_year", y="gemiddelde_prijs", markers=True,
                          color_discrete_sequence=[CATEGORICAL[0]], hover_data={"aantal": True})
            st.plotly_chart(style_chart(fig, "Bouwjaar", "Gemiddelde vraagprijs (€)"), use_container_width=True)

        with col_b:
            st.markdown(f"**Restwaarde t.o.v. bouwjaar {int(newest_year)} (%)**")
            fig = px.bar(year_stats, x="build_year", y="restwaarde_pct", text="restwaarde_pct",
                         color_discrete_sequence=[CATEGORICAL[5]])
            fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            fig.update_layout(
                xaxis=dict(type="category"),
                yaxis=dict(range=[0, max(110, year_stats["restwaarde_pct"].max() * 1.15)]),
            )
            st.plotly_chart(style_chart(fig, "Bouwjaar", "Restwaarde (%)"), use_container_width=True)

        mileage_df = dep_df.dropna(subset=["mileage_km"]).copy()
        if not mileage_df.empty:
            km_bins = [0, 25_000, 50_000, 75_000, 100_000, 125_000, 150_000, 200_000, float("inf")]
            km_labels = ["0-25k", "25-50k", "50-75k", "75-100k", "100-125k", "125-150k", "150-200k", "200k+"]
            mileage_df["km_bucket"] = pd.cut(mileage_df["mileage_km"], bins=km_bins, labels=km_labels, right=False)

            col_c, col_d = st.columns(2)
            with col_c:
                st.markdown("**Gemiddelde vraagprijs per km-stand**")
                km_stats = mileage_df.groupby("km_bucket", observed=True)["price"].mean().reset_index()
                fig = px.bar(km_stats, x="km_bucket", y="price", color_discrete_sequence=[CATEGORICAL[0]])
                fig.update_layout(xaxis=dict(type="category"))
                st.plotly_chart(style_chart(fig, "Km-stand", "Gemiddelde vraagprijs (€)"), use_container_width=True)

            with col_d:
                st.markdown("**Prijs naar bouwjaar × km-stand**")
                pivot = mileage_df.pivot_table(
                    index="build_year", columns="km_bucket", values="price", aggfunc="mean", observed=True,
                )
                if pivot.empty:
                    st.info("Onvoldoende data voor deze matrix.")
                else:
                    fig = px.imshow(
                        pivot, aspect="auto", origin="lower",
                        color_continuous_scale=["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"],
                        labels=dict(x="Km-stand", y="Bouwjaar", color="Gem. prijs (€)"),
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
            "title", "build_year", "price", "mileage_km", "fuel_type", "engine",
            "power_hp", "transmission", "color", "trim", "location", "is_active", "url",
        ] if c in df.columns
    ]
    st.dataframe(
        df[show_cols].sort_values("price", na_position="last"),
        column_config={"url": st.column_config.LinkColumn("Advertentie")},
        use_container_width=True,
        hide_index=True,
    )

    if not runs.empty:
        last_run = runs.iloc[-1]
        st.caption(f"Laatste scrape: {last_run['run_at']} — {last_run['listings_found']} advertenties gevonden.")


if __name__ == "__main__":
    main()
