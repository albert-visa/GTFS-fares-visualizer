import io
import zipfile
from typing import Dict, Optional

import folium
import pandas as pd
import streamlit as st
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


def read_gtfs_zip(uploaded_file) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(io.BytesIO(uploaded_file.getvalue())) as zf:
        members = {name.lower(): name for name in zf.namelist()}
        for table in REQUIRED_TABLES:
            filename = f"{table}.txt"
            if filename in members:
                with zf.open(members[filename]) as f:
                    data[table] = pd.read_csv(f, dtype=str)
    return data


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_areas_geometry(df_stops: pd.DataFrame, df_stop_areas: pd.DataFrame) -> pd.DataFrame:
    merged = df_stop_areas.merge(df_stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id", how="left")
    merged["stop_lat"] = to_float(merged["stop_lat"])
    merged["stop_lon"] = to_float(merged["stop_lon"])

    area_points = (
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

    return area_points


def detect_leg_rule_columns(df_fare_leg_rules: pd.DataFrame) -> tuple[Optional[str], Optional[str]]:
    source_candidates = ["from_area_id", "origin_area_id", "start_area_id", "area_id"]
    target_candidates = ["to_area_id", "destination_area_id", "end_area_id", "contains_area_id"]

    src = next((c for c in source_candidates if c in df_fare_leg_rules.columns), None)
    dst = next((c for c in target_candidates if c in df_fare_leg_rules.columns), None)
    return src, dst


def create_map(data: Dict[str, pd.DataFrame]) -> folium.Map:
    df_stops = data["stops"].copy()
    df_stops["stop_lat"] = to_float(df_stops["stop_lat"])
    df_stops["stop_lon"] = to_float(df_stops["stop_lon"])
    df_stops = df_stops.dropna(subset=["stop_lat", "stop_lon"])

    map_center = [df_stops["stop_lat"].mean(), df_stops["stop_lon"].mean()]
    m = folium.Map(location=map_center, zoom_start=11, tiles="cartodbpositron")

    if "stop_areas" in data and "area_id" in data["stop_areas"].columns:
        areas_geom = build_areas_geometry(df_stops, data["stop_areas"])

        areas_meta = data.get("areas", pd.DataFrame())
        if "area_id" in areas_meta.columns:
            areas_geom = areas_geom.merge(areas_meta, on="area_id", how="left")

        for _, row in areas_geom.iterrows():
            bounds = [[row["min_lat"], row["min_lon"]], [row["max_lat"], row["max_lon"]]]
            popup = f"""
            <b>area_id:</b> {row['area_id']}<br>
            <b>nom:</b> {row.get('area_name', '-') or '-'}<br>
            <b>stops:</b> {int(row['points'])}
            """
            folium.Rectangle(
                bounds=bounds,
                color="#0055AA",
                weight=2,
                fill=True,
                fill_opacity=0.15,
                popup=popup,
            ).add_to(m)

            folium.CircleMarker(
                location=[row["center_lat"], row["center_lon"]],
                radius=4,
                color="#0055AA",
                fill=True,
                fill_opacity=1,
                tooltip=f"Àrea {row['area_id']}",
            ).add_to(m)

        if "fare_leg_rules" in data:
            src_col, dst_col = detect_leg_rule_columns(data["fare_leg_rules"])
            if src_col and dst_col:
                centroids = areas_geom.set_index("area_id")[["center_lat", "center_lon"]].to_dict("index")
                links = data["fare_leg_rules"][[src_col, dst_col]].dropna().drop_duplicates()
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
                            opacity=0.8,
                            tooltip=f"{src} → {dst}",
                        ).add_to(m)

    stops_fg = folium.FeatureGroup(name="Stops")
    sample = df_stops.head(2000)
    for _, stop in sample.iterrows():
        folium.CircleMarker(
            location=[stop["stop_lat"], stop["stop_lon"]],
            radius=2,
            color="#222222",
            fill=True,
            fill_opacity=0.6,
            popup=f"{stop.get('stop_name', stop['stop_id'])}",
        ).add_to(stops_fg)

    stops_fg.add_to(m)
    folium.LayerControl().add_to(m)
    return m


def main() -> None:
    st.set_page_config(page_title="GTFS Fares v2 Map", layout="wide")
    st.title("Visualitzador GTFS Fares v2")
    st.write(
        "Puja un ZIP GTFS. L'app carrega les taules rellevants i dibuixa àrees (a partir de stop_areas + stops) i connexions entre àrees (fare_leg_rules)."
    )

    uploaded_file = st.file_uploader("ZIP GTFS", type=["zip"])
    if not uploaded_file:
        st.info("Selecciona un fitxer ZIP per començar.")
        return

    data = read_gtfs_zip(uploaded_file)
    loaded = sorted(data.keys())
    missing = [t for t in REQUIRED_TABLES if t not in data]

    st.subheader("Taules detectades")
    st.write(", ".join(loaded) if loaded else "Cap")
    if missing:
        st.warning(f"Falten taules: {', '.join(missing)}")

    if "stops" not in data:
        st.error("La taula stops.txt és necessària per pintar el mapa.")
        return

    map_object = create_map(data)
    st_folium(map_object, width=1400, height=760)

    with st.expander("Previsualització de dades"):
        for name in loaded:
            st.markdown(f"**{name}.txt** ({len(data[name])} files)")
            st.dataframe(data[name].head(20), use_container_width=True)


if __name__ == "__main__":
    main()
