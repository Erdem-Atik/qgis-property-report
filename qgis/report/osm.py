"""OpenStreetMap data access: Nominatim geocoding and Overpass POI queries.

Usage policies respected here:
- Nominatim: max 1 request/second, identifying User-Agent, results cached.
- Overpass: small radius, server-side timeout, retry with backoff on 429/5xx,
  mirror failover, and a disk cache keyed by query hash (see overpass_cache.py).
No PyQGIS imports: this module is plain Python.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import requests

from . import overpass_cache

log = logging.getLogger(__name__)

CACHE_DIR = os.environ.get("REPORT_CACHE_DIR", "/cache")
USER_AGENT = os.environ.get(
    "OSM_USER_AGENT",
    "qgis-property-report/0.2 (PyQGIS location report demo)",
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Tried in order; OVERPASS_URL (comma-separated) overrides the defaults.
OVERPASS_URLS = [u.strip() for u in os.environ.get(
    "OVERPASS_URL",
    "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter",
).split(",") if u.strip()]
SEARCH_RADIUS_M = 1500  # a bit beyond the 1 km buffer so "nearest" is meaningful

# category -> list of Overpass tag filters
CATEGORY_TAGS = {
    "beach": ['["natural"="beach"]'],
    "supermarket": ['["shop"="supermarket"]'],
    "restaurant": ['["amenity"="restaurant"]'],
    "cafe": ['["amenity"="cafe"]'],
    "pharmacy": ['["amenity"="pharmacy"]'],
    "bus_stop": ['["highway"="bus_stop"]', '["public_transport"="platform"]["bus"="yes"]'],
}


class OsmError(RuntimeError):
    pass


# ---------------------------------------------------------------- cache helpers
def _cache_path(kind: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, kind, f"{digest}.json")


def _cache_get(kind: str, key: str, max_age_s: float | None):
    path = _cache_path(kind, key)
    if not os.path.exists(path):
        return None
    if max_age_s is not None and time.time() - os.path.getmtime(path) > max_age_s:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cache_put(kind: str, key: str, value) -> None:
    path = _cache_path(kind, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


# ------------------------------------------------------------------- Nominatim
_last_nominatim_call = 0.0


def _nominatim_throttle() -> None:
    """Enforce >= 1 s between Nominatim requests (also across processes via a stamp file)."""
    global _last_nominatim_call
    stamp = os.path.join(CACHE_DIR, "nominatim.last")
    last = _last_nominatim_call
    try:
        last = max(last, os.path.getmtime(stamp))
    except OSError:
        pass
    wait = 1.1 - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _last_nominatim_call = time.time()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(stamp, "w"):
        pass


def geocode(address: str) -> dict:
    """Return {'lat', 'lon', 'display_name'} for an address. Cached indefinitely."""
    key = " ".join(address.lower().split())
    cached = _cache_get("nominatim", key, max_age_s=None)
    if cached is not None:
        return cached

    _nominatim_throttle()
    try:
        r = _session().get(
            NOMINATIM_URL,
            params={"q": address, "format": "jsonv2", "limit": 1},
            timeout=20,
        )
        r.raise_for_status()
        hits = r.json()
    except requests.RequestException as exc:
        raise OsmError(f"Nominatim request failed: {exc}") from exc
    if not hits:
        raise OsmError(f"Address not found: {address!r}")
    hit = hits[0]
    result = {
        "lat": float(hit["lat"]),
        "lon": float(hit["lon"]),
        "display_name": hit.get("display_name", address),
    }
    _cache_put("nominatim", key, result)
    return result


# -------------------------------------------------------------------- Overpass
def build_overpass_query(lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M,
                         timeout_s: int = 25) -> str:
    around = f"(around:{radius_m},{lat:.6f},{lon:.6f})"
    parts = []
    for filters in CATEGORY_TAGS.values():
        for f in filters:
            parts.append(f"  nwr{f}{around};")
    body = "\n".join(parts)
    return f"[out:json][timeout:{timeout_s}];\n(\n{body}\n);\nout tags geom;"


RETRYABLE_STATUS = (429, 502, 503, 504)


def _post_overpass(query: str, retries: int = 3) -> dict:
    """POST a query, falling back across endpoints.

    Busy/timeout errors (429, 5xx, network) are retried with backoff.
    Other client errors (e.g. 400, 403, 406) are not retried on the same
    endpoint: repeating them will not help and may look abusive.
    """
    session = _session()
    errors = {}
    endpoints = list(OVERPASS_URLS)
    for attempt in range(retries):
        for url in list(endpoints):
            try:
                r = session.post(url, data={"data": query}, timeout=(10, 60))
            except requests.RequestException as exc:
                errors[url] = f"{type(exc).__name__}"
                continue
            if r.status_code in RETRYABLE_STATUS:
                errors[url] = f"HTTP {r.status_code} (busy)"
                continue
            if r.status_code != 200:
                errors[url] = f"HTTP {r.status_code}: {r.text[:120].strip()!r}"
                endpoints.remove(url)  # permanent for this run
                continue
            try:
                data = r.json()
            except ValueError:
                errors[url] = "non-JSON response"
                continue
            if not overpass_cache.is_valid_response(data):
                errors[url] = "response has no 'elements' list"
                continue
            remark = data.get("remark") or ""
            if "runtime error" in remark or "timed out" in remark:
                errors[url] = f"remark: {remark}"
                continue
            return data
        if not endpoints:
            break
        if attempt < retries - 1:
            time.sleep(5 * (attempt + 1))  # 5 s, 10 s
    detail = "; ".join(f"{u} -> {e}" for u, e in errors.items())
    raise OsmError(f"Overpass failed on all endpoints: {detail}")


def _category(tags: dict) -> str | None:
    if tags.get("natural") == "beach":
        return "beach"
    if tags.get("shop") == "supermarket":
        return "supermarket"
    if tags.get("amenity") in ("restaurant", "cafe", "pharmacy"):
        return tags["amenity"]
    if tags.get("highway") == "bus_stop" or (
            tags.get("public_transport") == "platform" and tags.get("bus") == "yes"):
        return "bus_stop"
    return None


def _geometry(el: dict) -> dict | None:
    if el["type"] == "node":
        return {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
    if el["type"] == "way" and el.get("geometry"):
        coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            return {"type": "Polygon", "coordinates": [coords]}
        return {"type": "LineString", "coordinates": coords}
    if el["type"] == "relation" and el.get("bounds"):
        b = el["bounds"]  # relation: use bbox centre (good enough for amenities)
        return {"type": "Point", "coordinates": [(b["minlon"] + b["maxlon"]) / 2,
                                                 (b["minlat"] + b["maxlat"]) / 2]}
    return None


def overpass_to_geojson(data: dict) -> dict:
    features, seen = [], set()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        cat = _category(tags)
        geom = _geometry(el)
        if cat is None or geom is None:
            continue
        osm_id = f"{el['type']}/{el['id']}"
        if osm_id in seen:
            continue
        seen.add(osm_id)
        name = tags.get("name:en") or tags.get("name") or ""
        features.append({
            "type": "Feature",
            "properties": {"name": name, "category": cat, "osm_id": osm_id},
            "geometry": geom,
        })
    return {"type": "FeatureCollection", "features": features}


def fetch_overpass(query: str) -> tuple[dict, bool]:
    """Return (response, from_cache). Cache first; network (with failover) on a miss."""
    data = overpass_cache.load(query)
    if data is not None:
        return data, True
    data = _post_overpass(query)
    try:
        overpass_cache.save(query, data)
    except OSError as exc:  # e.g. read-only cache dir: still usable, just not cached
        log.warning("Could not write Overpass cache: %s", exc)
    return data, False


def fetch_pois(lat: float, lon: float, radius_m: int = SEARCH_RADIUS_M) -> dict:
    """Fetch POIs around a point as a GeoJSON FeatureCollection."""
    query = build_overpass_query(lat, lon, radius_m)
    data, from_cache = fetch_overpass(query)
    fc = overpass_to_geojson(data)
    fc["metadata"] = {
        "source": "OpenStreetMap via Overpass API",
        "osm_base": (data.get("osm3s") or {}).get("timestamp_osm_base"),
        "radius_m": radius_m,
        "from_cache": from_cache,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return fc


# -------------------------------------------------------------------- location
_LATLON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def resolve_location(text: str) -> tuple[float, float, str | None]:
    """'lat,lon' -> (lat, lon, None); anything else is geocoded -> (lat, lon, display_name)."""
    m = _LATLON.match(text)
    if m:
        return float(m.group(1)), float(m.group(2)), None
    hit = geocode(text)
    return hit["lat"], hit["lon"], hit["display_name"]
