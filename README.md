# Visualitzador GTFS Fares 
## Motivation
Provide an interactive viewer to inspect GTFS datasets (ZIP input) and specifically visualize GTFS Fares v2 constructs such as defined areas and area-to-area connections.
Make it easy to explore the relevant GTFS tables (areas, fare_leg_rules, stop_areas, stops, etc.) and preview their contents in a web UI.
## Description
Add a new Streamlit application app.py that loads a GTFS .zip, reads the requested tables listed in REQUIRED_TABLES, and exposes a file uploader and data preview UI.
Implement area geometry inference with build_areas_geometry by joining stop_areas to stops and computing bounding boxes and centroids per area_id for visualization.
Detect source/destination columns in fare_leg_rules with detect_leg_rule_columns and draw area-to-area links as folium.PolyLine between area centroids.
Add requirements.txt with required packages and replace README.md with setup/run instructions and notes on how areas are inferred.
## Testing
python -m py_compile app.py was run and succeeded.
streamlit run app.py could not be executed in this environment because streamlit was not available (command not found).
python -m pip install -r requirements.txt was attempted but failed due to network/proxy restrictions in the environment (package download blocked).
