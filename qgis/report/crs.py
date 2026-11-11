"""CRS helpers: pick a metric (UTM) CRS for a WGS84 coordinate.

All distance and buffer calculations must run in a metric CRS,
never in EPSG:4326 degrees.
"""
import math

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)


def wgs84() -> QgsCoordinateReferenceSystem:
    # Created on demand: CRS objects must not be built before initQgis().
    return QgsCoordinateReferenceSystem("EPSG:4326")


def validate_lat_lon(lat: float, lon: float) -> None:
    if not -80.0 <= lat <= 84.0:
        raise ValueError(f"Latitude {lat} is outside the UTM range (-80..84).")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude {lon} is outside -180..180.")


def utm_epsg(lat: float, lon: float) -> int:
    """Return the WGS84 / UTM EPSG code for a coordinate (326xx north, 327xx south).

    Norway/Svalbard zone exceptions are intentionally ignored.
    """
    validate_lat_lon(lat, lon)
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = min(zone, 60)  # lon == 180 belongs to zone 60
    return (32600 if lat >= 0 else 32700) + zone


def utm_crs(lat: float, lon: float) -> QgsCoordinateReferenceSystem:
    crs = QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg(lat, lon)}")
    if not crs.isValid():
        raise RuntimeError(f"Invalid CRS EPSG:{utm_epsg(lat, lon)}")
    return crs


def transform(src: QgsCoordinateReferenceSystem,
              dst: QgsCoordinateReferenceSystem) -> QgsCoordinateTransform:
    return QgsCoordinateTransform(src, dst, QgsProject.instance())
