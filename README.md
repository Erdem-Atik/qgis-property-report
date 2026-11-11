# Property Location Report Generator

Turns an address or coordinate into a map-based PDF location report (nearby amenities,
straight-line distances, 500 m / 1 km radius analysis) using headless QGIS (PyQGIS)
and OpenStreetMap data.

> Work in progress. Full documentation follows in a later phase.

## Data sources and limitations

- Map data and basemap © OpenStreetMap contributors.
- POIs are queried from the Overpass API. Public Overpass instances are rate-limited and
  occasionally unavailable; responses are cached locally. Sample responses are bundled for
  offline demos. Data snapshot date: 2026-11-11 (OSM base timestamps 05:30–05:34 UTC,
  bundled responses in `samples/overpass_cache/`).
- Distances are straight-line, not walking routes.
