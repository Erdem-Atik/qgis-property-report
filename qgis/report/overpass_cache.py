"""Disk cache for Overpass API responses.

Key   = SHA-256 of the Overpass QL query text (independent of which server answered).
File  = $OVERPASS_CACHE_DIR/<sha256>.json  (default: <repo>/cache/overpass/)
Only valid responses (a JSON object with an "elements" list) are ever stored,
and files are written atomically (temp file + rename).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile

log = logging.getLogger(__name__)

# qgis/report/overpass_cache.py -> repo root. Inside the container the repo's
# qgis/ folder is /app, so this resolves to /cache (mounted from ./cache).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DIR = os.path.join(_REPO_ROOT, "cache", "overpass")


def cache_dir() -> str:
    return os.environ.get("OVERPASS_CACHE_DIR") or DEFAULT_DIR


def query_key(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def cache_path(query: str) -> str:
    return os.path.join(cache_dir(), f"{query_key(query)}.json")


def is_valid_response(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("elements"), list)


def load(query: str) -> dict | None:
    """Return the cached response for a query, or None on a miss.

    A corrupt or invalid file is treated as a miss (and logged), never returned.
    """
    path = cache_path(query)
    if not os.path.isfile(path):
        log.info("Overpass cache miss: %s", os.path.basename(path))
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        log.warning("Ignoring unreadable cache file %s: %s", path, exc)
        return None
    if not is_valid_response(data):
        log.warning("Ignoring invalid cache file %s (no 'elements' list)", path)
        return None
    log.info("Overpass cache hit: %s", path)
    return data


def save(query: str, data: dict) -> str:
    """Atomically store a valid response. Raises ValueError for invalid data."""
    if not is_valid_response(data):
        raise ValueError("Refusing to cache an Overpass response without an 'elements' list")
    path = cache_path(query)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)  # atomic on the same filesystem
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    log.info("Overpass response cached: %s", path)
    return path
