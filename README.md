# GTFS Fares v2 visualizer

Aplicació Streamlit per carregar un fitxer GTFS `.zip` i visualitzar en mapa:

- Àrees (`areas` + `stop_areas` + `stops`) amb categories i colors
- Connexions entre àrees (`fare_leg_rules`) amb filtre on/off
- Stops (opcional, amb límit configurable i clustering)
- Visualització completa de taules (incloent `fare_transfer_rules`)

<img width="1436" height="921" alt="aplicatiu_streamlit" src="https://github.com/user-attachments/assets/5773841d-d1c8-4dd8-8a40-0cd224ebad1e" />

## Requisits
Crear una carpeta amb els arxius app.py, requirements.txt i README. Obrir la consola de windows (W+r; cmd).
A la consola, establir el directori i instal·lar requeriments:
```bash
cd gtfs
```

```bash
pip install -r requirements.txt
```

## Execució

```bash
streamlit run app.py
```
Alternativament:

```bash
py -m streamlit run app.py
```

## Filtres i opcions

- `Mostrar connexions entre zones`: activa/desactiva les línies entre àrees.
- `Mostrar Sectors tarifaris`: activa/desactiva la categoria d'àrees de sector.
- `Mostrar Municipis d'excepcions de bus`: activa/desactiva aquesta categoria.
- `Mostrar Estacions ferroviàries`: activa/desactiva les àrees amb `FGC` o `ROD` a `area_id`.
- `Mostrar T-JOVE`: activa/desactiva específicament les àrees T-JOVE.
- Botó de pantalla completa al mapa (icona de maximitzar).

## Categories i colors de les àrees

- **Estacions ferroviàries** (`area_id` conté `FGC` o `ROD`): taronja.
- **Municipis d'excepcions de bus** (`area_id` només dígits i 5 o més): lila.
- **Sectors tarifaris** (resta de casos): blau.
- **T-JOVE** (`area_id` o `area_name` conté `TJOVE` / `T-JOVE`): verd.

## Millores de rendiment aplicades

- Càrrega de ZIP i càlcul de geometries amb cache (`st.cache_data`).
- Layer de stops desactivat per defecte.
- Stops dibuixats amb `FastMarkerCluster` i límit configurable.
- Canvas preferit a Leaflet per render més fluid (`prefer_canvas=True`).

## Notes de visualització

- Com que GTFS Fares v2 no defineix geometria d'àrees de forma directa, l'aplicació dibuixa un rectangle per àrea usant el bounding box dels stops assignats a cada `area_id`.
- Les connexions s'infereixen de `fare_leg_rules` detectant automàticament les columnes d'origen/destinació més habituals (`from_area_id` / `to_area_id`, etc.).
- En la secció de taules **no** es mostren `routes`, `shapes` ni `trips`.
