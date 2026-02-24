# GTFS Fares v2 visualizer

Aplicació Streamlit per carregar un fitxer GTFS `.zip` i visualitzar en mapa:

- Àrees (`areas` + `stop_areas` + `stops`)
- Connexions entre àrees (`fare_leg_rules`)
- Stops (mostra de fins a 2000 punts)

## Requisits

```bash
pip install -r requirements.txt
```

## Execució

```bash
streamlit run app.py
```

## Notes de visualització

- Com que GTFS Fares v2 no defineix geometria d'àrees de forma directa, l'aplicació dibuixa un rectangle per àrea usant el bounding box dels stops assignats a cada `area_id`.
- Les connexions s'infereixen de `fare_leg_rules` detectant automàticament les columnes d'origen/destinació més habituals (`from_area_id` / `to_area_id`, etc.).
