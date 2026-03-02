# GTFS Fares v2 visualizer

Aplicació Streamlit per carregar un fitxer GTFS `.zip` i visualitzar en mapa:

- Àrees (`areas` + `stop_areas` + `stops`)
- Connexions entre àrees (`fare_leg_rules`) amb filtre on/off
- Stops (opcional, amb límit configurable i clustering)
- Visualització completa de taules (incloent `fare_transfer_rules`)

## Requisits

```bash
pip install -r requirements.txt
```

## Execució

```bash
streamlit run app.py
```

## Filtres i opcions

- `Mostrar connexions entre zones`: activa/desactiva les línies entre àrees.
- `Amagar àrea TJOVE`: exclou de la visualització del mapa qualsevol àrea amb `area_name = TJOVE` (o `area_id = TJOVE` com a fallback).
- Botó de pantalla completa al mapa (icona de maximitzar).

## Millores de rendiment aplicades

- Càrrega de ZIP i càlcul de geometries amb cache (`st.cache_data`).
- Layer de stops desactivat per defecte.
- Stops dibuixats amb `FastMarkerCluster` i límit configurable.
- Canvas preferit a Leaflet per render més fluid (`prefer_canvas=True`).

## Notes de visualització

- Com que GTFS Fares v2 no defineix geometria d'àrees de forma directa, l'aplicació dibuixa un rectangle per àrea usant el bounding box dels stops assignats a cada `area_id`.
- Les connexions s'infereixen de `fare_leg_rules` detectant automàticament les columnes d'origen/destinació més habituals (`from_area_id` / `to_area_id`, etc.).
- En la secció de taules **no** es mostren `routes`, `shapes` ni `trips`.
