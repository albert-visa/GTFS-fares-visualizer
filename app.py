import io
import re
import zipfile
from typing import Dict, Optional

import folium
import pandas as pd
import streamlit as st
from folium.plugins import FastMarkerCluster, Fullscreen
from streamlit_folium import st_folium

REQUIRED_TABLES = [
    "areas",
    "fare_leg_rules",
    "fare_products",
    "fare_media",
    "rider_categories",
    "routes",
    "shapes",
    "stop_areas",
    "stop_times",
    "stops",
    "trips",
    "fare_transfer_rules",
    "fare_leg_join_rules",
    "networks",
    "route_networks",
]

CATEGORY_FERROVIARIES = "Estacions ferroviàries"
CATEGORY_MUNICIPIS_BUS = "Municipis d'excepcions de bus"
CATEGORY_SECTORS = "Sectors tarifaris"
CATEGORY_TJOVE = "T-JOVE"

CATEGORY_COLORS = {
    CATEGORY_FERROVIARIES: "#F08C00",  # taronja
    CATEGORY_MUNICIPIS_BUS: "#8E44AD",  # lila
    CATEGORY_SECTORS: "#1E88E5",  # blau
    CATEGORY_TJOVE: "#2E7D32",  # verd
}


@st.cache_data(show_spinner=False)
def read_gtfs_zip_bytes(file_bytes: bytes) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        members = {name.lower(): name for name in zf.namelist()}
        for table in REQUIRED_TABLES:
            filename = f"{table}.txt"
            if filename in members:
                with zf.open(members[filename]) as f:
                    data[table] = pd.read_csv(f, dtype=str)
    return data


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


@st.cache_data(show_spinner=False)
def build_areas_geometry(df_stops: pd.DataFrame, df_stop_areas: pd.DataFrame) -> pd.DataFrame:
    merged = df_stop_areas.merge(df_stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id", how="left")
    merged["stop_lat"] = to_float(merged["stop_lat"])
    merged["stop_lon"] = to_float(merged["stop_lon"])

    return (
        merged.dropna(subset=["stop_lat", "stop_lon"])
        .groupby("area_id")
        .agg(
            center_lat=("stop_lat", "mean"),
            center_lon=("stop_lon", "mean"),
            points=("stop_id", "count"),
            min_lat=("stop_lat", "min"),
            max_lat=("stop_lat", "max"),
            min_lon=("stop_lon", "min"),
            max_lon=("stop_lon", "max"),
        )
        .reset_index()
    )


def detect_leg_rule_columns(df_fare_leg_rules: pd.DataFrame) -> tuple[Optional[str], Optional[str]]:
    source_candidates = ["from_area_id", "origin_area_id", "start_area_id", "area_id"]
    target_candidates = ["to_area_id", "destination_area_id", "end_area_id", "contains_area_id"]

    src = next((c for c in source_candidates if c in df_fare_leg_rules.columns), None)
    dst = next((c for c in target_candidates if c in df_fare_leg_rules.columns), None)
    return src, dst


def normalize_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def classify_area(area_id: str, area_name: str) -> str:
    norm_id = normalize_text(area_id)
    norm_name = normalize_text(area_name)

    if "TJOVE" in norm_id or "TJOVE" in norm_name:
        return CATEGORY_TJOVE

    if "FGC" in norm_id or "ROD" in norm_id:
        return CATEGORY_FERROVIARIES

    if re.fullmatch(r"\d{5,}", str(area_id).strip()):
        return CATEGORY_MUNICIPIS_BUS

    return CATEGORY_SECTORS


def apply_area_categories(areas_geom: pd.DataFrame) -> pd.DataFrame:
    if areas_geom.empty:
        return areas_geom

    area_names = areas_geom["area_name"] if "area_name" in areas_geom.columns else pd.Series([""] * len(areas_geom))
    categories = [
        classify_area(area_id=row_area_id, area_name=row_area_name)
        for row_area_id, row_area_name in zip(areas_geom["area_id"], area_names)
    ]
    out = areas_geom.copy()
    out["area_category"] = categories
    return out


def filter_areas_by_category(
    areas_geom: pd.DataFrame,
    show_sectors: bool,
    show_municipis_bus: bool,
    show_ferroviaries: bool,
    show_tjove: bool,
) -> pd.DataFrame:
    if areas_geom.empty:
        return areas_geom

    allowed = set()
    if show_sectors:
        allowed.add(CATEGORY_SECTORS)
    if show_municipis_bus:
        allowed.add(CATEGORY_MUNICIPIS_BUS)
    if show_ferroviaries:
        allowed.add(CATEGORY_FERROVIARIES)
    if show_tjove:
        allowed.add(CATEGORY_TJOVE)

    return areas_geom[areas_geom["area_category"].isin(allowed)].copy()


def create_map(
    data: Dict[str, pd.DataFrame],
    show_connections: bool,
    show_stops: bool,
    max_stops: int,
    show_sectors: bool,
    show_municipis_bus: bool,
    show_ferroviaries: bool,
    show_tjove: bool,
) -> folium.Map:
    df_stops = data["stops"].copy()
    df_stops["stop_lat"] = to_float(df_stops["stop_lat"])
    df_stops["stop_lon"] = to_float(df_stops["stop_lon"])
    df_stops = df_stops.dropna(subset=["stop_lat", "stop_lon"])

    map_center = [df_stops["stop_lat"].mean(), df_stops["stop_lon"].mean()]
    m = folium.Map(location=map_center, zoom_start=11, tiles="cartodbpositron", prefer_canvas=True)
    Fullscreen(
        position="topright",
        title="Maximitzar",
        title_cancel="Sortir pantalla completa",
        force_separate_button=True,
    ).add_to(m)

    areas_geom = pd.DataFrame()
    if "stop_areas" in data and "area_id" in data["stop_areas"].columns:
        areas_geom = build_areas_geometry(df_stops, data["stop_areas"])

        areas_meta = data.get("areas", pd.DataFrame())
        if "area_id" in areas_meta.columns:
            areas_geom = areas_geom.merge(areas_meta, on="area_id", how="left")

        areas_geom = apply_area_categories(areas_geom)
        areas_geom = filter_areas_by_category(
            areas_geom=areas_geom,
            show_sectors=show_sectors,
            show_municipis_bus=show_municipis_bus,
            show_ferroviaries=show_ferroviaries,
            show_tjove=show_tjove,
        )

        area_fg = folium.FeatureGroup(name="Àrees", show=True)
        for _, row in areas_geom.iterrows():
            category = row.get("area_category", CATEGORY_SECTORS)
            area_color = CATEGORY_COLORS.get(category, "#0055AA")
            bounds = [[row["min_lat"], row["min_lon"]], [row["max_lat"], row["max_lon"]]]
            popup = (
                f"<b>area_id:</b> {row['area_id']}<br>"
                f"<b>nom:</b> {row.get('area_name', '-') or '-'}<br>"
                f"<b>categoria:</b> {category}<br>"
                f"<b>stops:</b> {int(row['points'])}"
            )
            folium.Rectangle(
                bounds=bounds,
                color=area_color,
                weight=1,
                fill=True,
                fill_opacity=0.15,
                popup=popup,
            ).add_to(area_fg)

            folium.CircleMarker(
                location=[row["center_lat"], row["center_lon"]],
                radius=3,
                color=area_color,
                fill=True,
                fill_opacity=0.9,
                tooltip=f"Àrea {row['area_id']} ({category})",
            ).add_to(area_fg)
        area_fg.add_to(m)

    if show_connections and "fare_leg_rules" in data and not areas_geom.empty:
        src_col, dst_col = detect_leg_rule_columns(data["fare_leg_rules"])
        if src_col and dst_col:
            centroids = areas_geom.set_index("area_id")[["center_lat", "center_lon"]].to_dict("index")
            links = data["fare_leg_rules"][[src_col, dst_col]].dropna().drop_duplicates()
            links_fg = folium.FeatureGroup(name="Connexions entre àrees", show=True)
            for _, link in links.iterrows():
                src, dst = link[src_col], link[dst_col]
                if src in centroids and dst in centroids:
                    folium.PolyLine(
                        [
                            [centroids[src]["center_lat"], centroids[src]["center_lon"]],
                            [centroids[dst]["center_lat"], centroids[dst]["center_lon"]],
                        ],
                        color="#D9480F",
                        weight=2,
                        opacity=0.75,
                    ).add_to(links_fg)
            links_fg.add_to(m)

    if show_stops:
        sample = df_stops.head(max_stops)
        coords = sample[["stop_lat", "stop_lon"]].values.tolist()
        fg_stops = folium.FeatureGroup(name=f"Stops (max {max_stops})", show=False)
        FastMarkerCluster(data=coords).add_to(fg_stops)
        fg_stops.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def main() -> None:
    st.set_page_config(page_title="GTFS Fares v2 Map", layout="wide")
    st.title("Visualitzador GTFS Fares v2")
    st.write("Puja un ZIP GTFS. L'app carrega les taules rellevants i dibuixa àrees (stop_areas + stops).")

    uploaded_file = st.file_uploader("ZIP GTFS", type=["zip"])
    if not uploaded_file:
        st.info("Selecciona un fitxer ZIP per començar.")
        return

    data = read_gtfs_zip_bytes(uploaded_file.getvalue())
    loaded = sorted(data.keys())
    missing = [t for t in REQUIRED_TABLES if t not in data]

    st.subheader("Taules detectades")
    st.write(", ".join(loaded) if loaded else "Cap")
    if missing:
        st.warning(f"Falten taules: {', '.join(missing)}")

    if "stops" not in data:
        st.error("La taula stops.txt és necessària per pintar el mapa.")
        return

    st.subheader("Filtres de visualització")
    col1, col2, col3 = st.columns(3)
    with col1:
        show_connections = st.checkbox("Mostrar connexions entre zones", value=True)
        show_stops = st.checkbox("Mostrar stops", value=False)
    with col2:
        show_sectors = st.checkbox("Mostrar Sectors tarifaris", value=True)
        show_municipis_bus = st.checkbox("Mostrar Municipis d'excepcions de bus", value=True)
    with col3:
        show_ferroviaries = st.checkbox("Mostrar Estacions ferroviàries", value=True)
        show_tjove = st.checkbox("Mostrar T-JOVE", value=False)

    max_stops = st.slider("Màxim de stops a dibuixar", min_value=500, max_value=10000, step=500, value=2500)

    map_object = create_map(
        data=data,
        show_connections=show_connections,
        show_stops=show_stops,
        max_stops=max_stops,
        show_sectors=show_sectors,
        show_municipis_bus=show_municipis_bus,
        show_ferroviaries=show_ferroviaries,
        show_tjove=show_tjove,
    )
    st_folium(map_object, width=1400, height=760)

    with st.expander("Previsualització de dades"):
        hidden_tables = {"routes", "shapes", "trips"}
        for name in loaded:
            if name in hidden_tables:
                continue
            st.markdown(f"**{name}.txt** ({len(data[name])} files)")
            st.dataframe(data[name], use_container_width=True, height=320)


if __name__ == "__main__":
    main()
