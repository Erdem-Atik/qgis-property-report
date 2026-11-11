"""Import a manually exported Overpass response into the cache.

Use when public Overpass servers are unavailable:
  1. python3 generate_report.py --print-query "36.2018,29.6377"
  2. Run the printed query on https://overpass-turbo.eu and export the raw JSON
     ("Export" -> "raw OSM data").
  3. python3 scripts/import_overpass.py "36.2018,29.6377" /path/to/export.json

LOCATION must be given exactly as the report will be run ('lat,lon' or the same
address string), so the cache key matches the query the app builds.
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report import osm, overpass_cache  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("location", help="'lat,lon' or an address (as passed to generate_report.py)")
    p.add_argument("json_file", help="Raw Overpass JSON exported from overpass-turbo")
    p.add_argument("--cache-dir", help="Target cache dir (default: $OVERPASS_CACHE_DIR or cache/overpass)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cache_dir:
        os.environ["OVERPASS_CACHE_DIR"] = args.cache_dir

    try:
        with open(args.json_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read JSON from {args.json_file}: {exc}", file=sys.stderr)
        return 2
    if not overpass_cache.is_valid_response(data):
        print("ERROR: not an Overpass JSON response (no 'elements' list). "
              "Export the raw data, not GeoJSON.", file=sys.stderr)
        return 2
    remark = data.get("remark") or ""
    if "runtime error" in remark or "timed out" in remark:
        print(f"ERROR: response is incomplete (remark: {remark})", file=sys.stderr)
        return 2

    try:
        lat, lon, display = osm.resolve_location(args.location)
    except osm.OsmError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    query = osm.build_overpass_query(lat, lon)
    path = overpass_cache.save(query, data)

    n_pois = len(osm.overpass_to_geojson(data)["features"])
    osm_base = (data.get("osm3s") or {}).get("timestamp_osm_base", "unknown")
    where = display or f"{lat:.6f}, {lon:.6f}"
    print(f"Imported {len(data['elements'])} elements ({n_pois} usable POIs) for {where}")
    print(f"OSM data snapshot: {osm_base}")
    print(f"Cache file: {path}")
    if not data["elements"]:
        print("WARNING: response has 0 elements - check that you ran the printed query unchanged.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
