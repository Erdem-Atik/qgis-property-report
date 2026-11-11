"""Generate a property location report (PDF + GeoPackage + summary JSON).

Examples (inside the container):
    # Address -> Nominatim geocode -> Overpass POIs -> PDF
    python3 generate_report.py --address "Kaleici, Antalya, Turkey" --name "Old Town Apartment" --out /out/kaleici

    # Coordinates + a local POI file (no network for POIs)
    python3 generate_report.py --lat 36.2018 --lon 29.6377 --name "Kas Harbour Villa" \
        --poi /samples/poi/kas_demo.geojson --out /out/kas

Exit codes: 0 ok, 1 processing error, 2 invalid input, 3 external service error.
"""
import argparse
import json
import logging
import os
import sys
import time


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Property location report generator (PyQGIS).")
    loc = p.add_argument_group("location (use --address OR --lat/--lon)")
    loc.add_argument("--address", help="Free-text address, geocoded with Nominatim")
    loc.add_argument("--lat", type=float, help="Latitude (WGS84)")
    loc.add_argument("--lon", type=float, help="Longitude (WGS84)")
    p.add_argument("--name", help="Report title (default: address or coordinates)")
    p.add_argument("--out", help="Output directory (required unless --print-query)")
    p.add_argument("--print-query", metavar="LOCATION",
                   help="Print the Overpass QL query used for LOCATION ('lat,lon' or an address) "
                        "and exit. Run it manually (e.g. overpass-turbo.eu), then import the raw "
                        "JSON with scripts/import_overpass.py.")
    p.add_argument("--poi", help="Local POI GeoJSON ('name' and 'category' properties). "
                                 "If omitted, POIs are fetched from OpenStreetMap (Overpass).")
    p.add_argument("--no-basemap", action="store_true", help="Skip the OSM basemap (offline)")
    p.add_argument("--no-summary", action="store_true",
                   help="Skip the AI location summary (no LLM call)")
    p.add_argument("--dpi", type=int, default=200, help="PDF raster resolution (default 200)")
    args = p.parse_args(argv)
    if args.print_query:
        return args
    if not args.out:
        p.error("--out is required")

    has_coords = args.lat is not None or args.lon is not None
    if args.address and has_coords:
        p.error("use either --address or --lat/--lon, not both")
    if not args.address and (args.lat is None or args.lon is None):
        p.error("--address or both --lat and --lon are required")
    return args


def fail(msg: str, code: int) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)s %(name)s: %(message)s")

    from report import llm, osm, overpass_cache

    if args.print_query:
        try:
            plat, plon, display = osm.resolve_location(args.print_query)
        except osm.OsmError as exc:
            return fail(str(exc), 3)
        query = osm.build_overpass_query(plat, plon)
        if display:
            print(f"Geocoded: {display} -> {plat:.6f}, {plon:.6f}", file=sys.stderr)
        print(f"Cache file: {overpass_cache.cache_path(query)}", file=sys.stderr)
        print(query)  # stdout: only the query, so it can be piped or copied
        return 0

    # 1. Location
    lat, lon, address = args.lat, args.lon, None
    if args.address:
        try:
            hit = osm.geocode(args.address)
        except osm.OsmError as exc:
            return fail(str(exc), 3)
        lat, lon, address = hit["lat"], hit["lon"], hit["display_name"]
        print(f"Geocoded: {address} -> {lat:.5f}, {lon:.5f}")
    name = args.name or args.address or f"{lat:.5f}, {lon:.5f}"

    # Import PyQGIS lazily so --help and input errors are fast.
    from qgis.core import QgsProject
    from report.app import qgis_app
    from report.analysis import run_analysis, write_geopackage
    from report.crs import validate_lat_lon
    from report.render import build_layout, build_project, export_pdf

    try:
        validate_lat_lon(lat, lon)
    except ValueError as exc:
        return fail(str(exc), 2)

    os.makedirs(args.out, exist_ok=True)
    gpkg = os.path.join(args.out, "analysis.gpkg")
    pdf = os.path.join(args.out, "report.pdf")
    summary_path = os.path.join(args.out, "summary.json")
    ai_path = os.path.join(args.out, "ai_summary.json")
    if os.path.exists(ai_path):
        os.remove(ai_path)  # never leave a stale summary from an earlier run

    # 2. POIs: local file or OpenStreetMap
    poi_meta, poi_source = {}, None
    if args.poi:
        if not os.path.isfile(args.poi):
            return fail(f"POI file not found: {args.poi}", 2)
        poi_path = args.poi
    else:
        try:
            fc = osm.fetch_pois(lat, lon)
        except osm.OsmError as exc:
            return fail(str(exc), 3)
        poi_meta = fc.pop("metadata")
        poi_source = "OpenStreetMap (Overpass API)"
        poi_path = os.path.join(args.out, "pois.geojson")
        with open(poi_path, "w", encoding="utf-8") as fh:
            json.dump(fc, fh, ensure_ascii=False)
        origin = "local cache" if poi_meta["from_cache"] else "Overpass API"
        print(f"Loaded {len(fc['features'])} POIs from {origin} "
              f"(radius {poi_meta['radius_m']} m, OSM data snapshot {poi_meta['osm_base']})")

    def run() -> dict:
        # Kept in its own scope so every QGIS object is released before exitQgis().
        result = run_analysis(lat, lon, name, poi_path, poi_source=poi_source,
                              poi_meta=poi_meta, address=address)
        uris = write_geopackage(result, gpkg)
        summary = result.summary()
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)

        # AI summary: based only on summary.json; a failure never blocks the PDF.
        summary_text = None
        if not args.no_summary:
            ai = llm.try_summarize(summary)
            with open(ai_path, "w", encoding="utf-8") as fh:
                json.dump(ai, fh, indent=2, ensure_ascii=False)
            summary_text = ai["text"]
            summary["_ai_status"] = ai["status"]

        layers = build_project(result, uris, basemap=not args.no_basemap)
        layout = build_layout(result, layers, summary_text=summary_text)
        export_pdf(layout, pdf, dpi=args.dpi)
        return summary

    # 3. Analysis + map
    t0 = time.time()
    with qgis_app():
        try:
            summary = run()
        except Exception as exc:  # report and exit non-zero for automation (n8n)
            return fail(str(exc), 1)
        finally:
            QgsProject.instance().clear()

    print(f"UTM CRS:  EPSG:{summary['utm_epsg']}")
    for s in summary["categories"].values():
        print(f"  {s['label']:<12} 500m={s['count_500']:<3} 1km={s['count_1000']:<3} "
              f"nearest={s['nearest_m']} m ({s['nearest_name']})")
    if "_ai_status" in summary:
        print(f"AI summary: {summary['_ai_status']} (see {ai_path})")
    print(f"Wrote {pdf}\n      {gpkg}\n      {summary_path}  ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
