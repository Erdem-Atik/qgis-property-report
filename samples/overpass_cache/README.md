# Bundled Overpass responses (offline demo)

Raw Overpass API responses for the three locations in `samples/input.csv`.
File name = SHA-256 of the Overpass QL query the app builds for that location.

| Location | `lat,lon` | Expected file |
|---|---|---|
| Kas Harbour Villa | `36.2018,29.6377` | `081c1a6bdaeecaeee9c3f6d5ca41468cbcbbb90a45e286c7d241e2a7e9d1ad4b.json` |
| Antalya Kaleici Apartment | `36.8841,30.7056` | `d80e649fcbd723390cd2b510d44b08e797d46421b36c4aef09dd8c53a38205a8.json` |
| Elmali Countryside House | `36.7375,29.9172` | `9f683d627c9c92d461c3fbbb65ff5ccca950b06e43b407fabeeac3957e4eefbd.json` |

## Adding / refreshing a response

```powershell
# 1. Print the exact query
docker compose run --rm qgis python3 generate_report.py --print-query "36.2018,29.6377"
# 2. Run it unchanged on https://overpass-turbo.eu, export the raw JSON,
#    and save it into this folder (e.g. samples/overpass_cache/kas.json)
# 3. Validate and store it under the right hash name
docker compose run --rm qgis python3 scripts/import_overpass.py "36.2018,29.6377" `
  /samples/overpass_cache/kas.json --cache-dir /samples/overpass_cache
# 4. Delete the original export file (kas.json)
```

## Using them

Set `OVERPASS_CACHE_DIR=/samples/overpass_cache` in `.env`, then run a report with
the same coordinates, e.g. `--lat 36.2018 --lon 29.6377`.
