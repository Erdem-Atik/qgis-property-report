"""Spatial analysis: buffers, POI distances and per-category statistics.

Everything here runs in the local UTM CRS (metres).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .crs import transform, utm_crs, utm_epsg, wgs84

BUFFERS_M = (500, 1000)
BUFFER_SEGMENTS = 36

# Display order and labels for known categories. Unknown categories are kept as-is.
CATEGORY_LABELS = {
    "beach": "Beach",
    "supermarket": "Supermarket",
    "restaurant": "Restaurant",
    "cafe": "Cafe",
    "pharmacy": "Pharmacy",
    "bus_stop": "Bus stop",
}


@dataclass
class AnalysisResult:
    name: str
    lat: float
    lon: float
    epsg: int
    property_layer: QgsVectorLayer
    buffer_layer: QgsVectorLayer
    poi_layer: QgsVectorLayer
    categories: dict = field(default_factory=dict)
    poi_source: str | None = None
    poi_meta: dict = field(default_factory=dict)
    address: str | None = None

    def summary(self) -> dict:
        return {
            "name": self.name,
            "address": self.address,
            "lat": self.lat,
            "lon": self.lon,
            "utm_epsg": self.epsg,
            "buffers_m": list(BUFFERS_M),
            "poi_search_radius_m": self.poi_meta.get("radius_m"),
            "categories": self.categories,
            "poi_source": self.poi_source,
            "poi_source_details": self.poi_meta or None,
            "notes": "Distances are straight-line (not walking routes). "
                     "nearest_m = null means none found in the POI data / search radius.",
            "qgis_version": Qgis.version(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


def _memory_layer(geom: str, epsg: int, name: str, fields: list[QgsField]) -> QgsVectorLayer:
    layer = QgsVectorLayer(f"{geom}?crs=EPSG:{epsg}", name, "memory")
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    return layer


def _load_pois(path: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(path, "poi_source", "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Could not read POI file: {path}")
    names = layer.fields().names()
    for required in ("name", "category"):
        if required not in names:
            raise RuntimeError(f"POI file is missing the '{required}' property: {path}")
    return layer


def run_analysis(lat: float, lon: float, name: str, poi_path: str | None,
                 poi_source: str | None = None, poi_meta: dict | None = None,
                 address: str | None = None) -> AnalysisResult:
    epsg = utm_epsg(lat, lon)
    utm = utm_crs(lat, lon)
    to_utm = transform(wgs84(), utm)

    # 1. Property point in UTM
    origin = to_utm.transform(QgsPointXY(lon, lat))
    origin_geom = QgsGeometry.fromPointXY(origin)

    prop = _memory_layer("Point", epsg, "Property", [QgsField("name", QMetaType.Type.QString)])
    f = QgsFeature(prop.fields())
    f.setGeometry(origin_geom)
    f["name"] = name
    prop.dataProvider().addFeatures([f])

    # 2. Buffers (largest first so smaller rings draw on top)
    buffers = _memory_layer("Polygon", epsg, "Buffers", [QgsField("radius_m", QMetaType.Type.Int)])
    buffer_geoms = {}
    feats = []
    for radius in sorted(BUFFERS_M, reverse=True):
        g = origin_geom.buffer(radius, BUFFER_SEGMENTS)
        buffer_geoms[radius] = g
        bf = QgsFeature(buffers.fields())
        bf.setGeometry(g)
        bf["radius_m"] = radius
        feats.append(bf)
    buffers.dataProvider().addFeatures(feats)

    # 3-4. POIs: reproject, measure, count
    poi_fields = [
        QgsField("name", QMetaType.Type.QString),
        QgsField("category", QMetaType.Type.QString),
        QgsField("distance_m", QMetaType.Type.Double),
    ] + [QgsField(f"in_{r}", QMetaType.Type.Int) for r in BUFFERS_M]
    pois = _memory_layer("Point", epsg, "Points of interest", poi_fields)

    stats = {cat: _empty_stats() for cat in CATEGORY_LABELS}
    if poi_path:
        src = _load_pois(poi_path)
        src_to_utm = transform(src.crs(), utm)
        out = []
        for sf in src.getFeatures():
            if not sf.hasGeometry():
                continue
            g = QgsGeometry(sf.geometry())
            g.transform(src_to_utm)
            category = str(sf["category"] or "other").strip().lower()
            dist = g.distance(origin_geom)  # metres (UTM); 0 if inside a polygon
            if g.type() != Qgis.GeometryType.Point:
                # Beaches etc. are areas/lines: keep the point closest to the property.
                g = g.nearestPoint(origin_geom)
            label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
            pf = QgsFeature(pois.fields())
            pf.setGeometry(g)
            pf["name"] = str(sf["name"] or "").strip() or f"Unnamed {label.lower()}"
            pf["category"] = category
            pf["distance_m"] = round(dist, 1)
            for r in BUFFERS_M:
                pf[f"in_{r}"] = int(buffer_geoms[r].intersects(g))
            out.append(pf)

            s = stats.setdefault(category, _empty_stats())
            for r in BUFFERS_M:
                if dist <= r:
                    s[f"count_{r}"] += 1
            if s["nearest_m"] is None or dist < s["nearest_m"]:
                s["nearest_m"] = round(dist)
                s["nearest_name"] = pf["name"]
        pois.dataProvider().addFeatures(out)

    for cat, s in stats.items():
        s["label"] = CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())

    return AnalysisResult(
        name=name, lat=lat, lon=lon, epsg=epsg,
        property_layer=prop, buffer_layer=buffers, poi_layer=pois,
        categories=stats,
        poi_source=poi_source or (os.path.basename(poi_path) if poi_path else None),
        poi_meta=poi_meta or {},
        address=address,
    )


def _empty_stats() -> dict:
    s = {f"count_{r}": 0 for r in BUFFERS_M}
    s.update({"nearest_m": None, "nearest_name": None})
    return s


def write_geopackage(result: AnalysisResult, path: str) -> dict[str, str]:
    """Write the analysis layers to one GeoPackage. Returns {layer_name: uri}."""
    if os.path.exists(path):
        os.remove(path)
    ctx = QgsProject.instance().transformContext()
    uris = {}
    layers = [("property", result.property_layer),
              ("buffers", result.buffer_layer),
              ("pois", result.poi_layer)]
    for i, (layer_name, layer) in enumerate(layers):
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = layer_name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile if i == 0
            else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
        )
        err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, ctx, opts)
        if err != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(f"Writing layer '{layer_name}' to {path} failed: {msg}")
        uris[layer_name] = f"{path}|layername={layer_name}"
    return uris
