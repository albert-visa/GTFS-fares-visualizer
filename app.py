import io
import zipfile
from typing import Dict, Optional

import folium
import pandas as pd
import streamlit as st
from folium.plugins import FastMarkerCluster
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
]


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


def create_map(
    data: Dict[str, pd.DataFrame],
    show_connections: bool,
    show_stops: bool,
    max_stops: int,
) -> folium.Map:
    df_stops = data["stops"].copy()
    df_stops["stop_lat"] = to_float(df_stops["stop_lat"])
    df_stops["stop_lon"] = to_float(df_stops["stop_lon"])
    df_stops = df_stops.dropna(subset=["stop_lat", "stop_lon"])

    map_center = [df_stops["stop_lat"].mean(), df_stops["stop_lon"].mean()]
    m = folium.Map(location=map_center, zoom_start=11, tiles="cartodbpositron", prefer_canvas=True)

    areas_geom = pd.DataFrame()
    if "stop_areas" in data and "area_id" in data["stop_areas"].columns:
        areas_geom = build_areas_geometry(df_stops, data["stop_areas"])

        areas_meta = data.get("areas", pd.DataFrame())
        if "area_id" in areas_meta.columns:
            areas_geom = areas_geom.merge(areas_meta, on="area_id", how="left")

        area_fg = folium.FeatureGroup(name="Àrees", show=True)
        for _, row in areas_geom.iterrows():
            bounds = [[row["min_lat"], row["min_lon"]], [row["max_lat"], row["max_lon"]]]
            popup = (
                f"<b>area_id:</b> {row['area_id']}<br>"
                f"<b>nom:</b> {row.get('area_name', '-') or '-'}<br>"
                f"<b>stops:</b> {int(row['points'])}"
            )
            folium.Rectangle(
                bounds=bounds,
                color="#0055AA",
                weight=1,
                fill=True,
                fill_opacity=0.12,
                popup=popup,
            ).add_to(area_fg)

            folium.CircleMarker(
                location=[row["center_lat"], row["center_lon"]],
                radius=3,
                color="#0055AA",
                fill=True,
                fill_opacity=0.9,
                tooltip=f"Àrea {row['area_id']}",
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
    st.write(
        "Puja un ZIP GTFS. L'app carrega les taules rellevants i dibuixa àrees (stop_areas + stops)."
    )

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
    with col2:
        show_stops = st.checkbox("Mostrar stops", value=False)
    with col3:
        max_stops = st.slider("Màxim de stops a dibuixar", min_value=500, max_value=10000, step=500, value=2500)

    map_object = create_map(
        data=data,
        show_connections=show_connections,
        show_stops=show_stops,
        max_stops=max_stops,
    )
    st_folium(map_object, width=1400, height=760)

    with st.expander("Previsualització de dades"):
        for name in loaded:
            st.markdown(f"**{name}.txt** ({len(data[name])} files)")
            st.dataframe(data[name].head(20), use_container_width=True)


if __name__ == "__main__":
    main()
