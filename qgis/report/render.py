"""Map rendering: project setup, styling, print layout and PDF export."""
from __future__ import annotations

import os
from datetime import date

from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    Qgis,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemManualTable,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutTableColumn,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
    QgsReadWriteContext,
    QgsRectangle,
    QgsTableCell,
    QgsVectorLayer,
)

from .analysis import BUFFERS_M, AnalysisResult
from .crs import utm_crs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_DIR = os.path.join(ROOT, "styles")
TEMPLATE = os.path.join(ROOT, "templates", "report_a4.qpt")

OSM_XYZ = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmin=0&zmax=19"
MAP_MARGIN = 1.15  # extent = largest buffer + 15 %


def _load_styled(uri: str, name: str, qml: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(uri, name, "ogr")
    if not layer.isValid():
        raise RuntimeError(f"Could not load layer {uri}")
    msg, ok = layer.loadNamedStyle(os.path.join(STYLE_DIR, qml))
    if not ok:
        raise RuntimeError(f"Could not apply style {qml}: {msg}")
    return layer


def build_project(result: AnalysisResult, gpkg_uris: dict, basemap: bool) -> dict:
    project = QgsProject.instance()
    project.clear()
    project.setCrs(utm_crs(result.lat, result.lon))

    layers = {
        "pois": _load_styled(gpkg_uris["pois"], "Points of interest", "pois.qml"),
        "property": _load_styled(gpkg_uris["property"], "Property", "property.qml"),
        "buffers": _load_styled(gpkg_uris["buffers"], "Straight-line radius", "buffers.qml"),
    }
    if basemap:
        osm = QgsRasterLayer(OSM_XYZ, "OpenStreetMap", "wms")
        if not osm.isValid():
            raise RuntimeError("Could not create the OpenStreetMap XYZ layer")
        layers["basemap"] = osm
    project.addMapLayers(list(layers.values()))
    return layers


def _item(layout, item_id, cls):
    item = layout.itemById(item_id)
    if item is None or not isinstance(item, cls):
        raise RuntimeError(f"Template item '{item_id}' ({cls.__name__}) not found in {TEMPLATE}")
    return item


def _fmt_distance(m):
    if m is None:
        return "–"
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m} m"


def _fill_table(layout, result: AnalysisResult):
    table = next((mf for mf in layout.multiFrames()
                  if isinstance(mf, QgsLayoutItemManualTable)), None)
    if table is None:
        raise RuntimeError(f"Distance table not found in {TEMPLATE}")
    headers = ["Category"] + [f"Within {r} m" if r < 1000 else f"Within {r // 1000} km"
                              for r in BUFFERS_M] + ["Nearest"]
    table.setHeaders([QgsLayoutTableColumn(h) for h in headers])
    table.setIncludeTableHeader(True)
    rows = []
    for s in result.categories.values():
        rows.append([QgsTableCell(s["label"])]
                    + [QgsTableCell(str(s[f"count_{r}"])) for r in BUFFERS_M]
                    + [QgsTableCell(_fmt_distance(s["nearest_m"]))])
    table.setTableContents(rows)


def build_layout(result: AnalysisResult, layers: dict, summary_text: str | None = None) -> QgsPrintLayout:
    project = QgsProject.instance()
    layout = QgsPrintLayout(project)
    doc = QDomDocument()
    with open(TEMPLATE, encoding="utf-8") as fh:
        doc.setContent(fh.read())
    _, ok = layout.loadFromTemplate(doc, QgsReadWriteContext())
    if not ok:
        raise RuntimeError(f"Could not load template {TEMPLATE}")

    _item(layout, "title", QgsLayoutItemLabel).setText(result.name)
    _item(layout, "subtitle", QgsLayoutItemLabel).setText(
        f"Location report · {result.lat:.5f}, {result.lon:.5f} · "
        f"EPSG:{result.epsg} · {date.today().isoformat()}"
    )

    # Map: draw order top → bottom
    map_item = _item(layout, "map", QgsLayoutItemMap)
    order = [layers[k] for k in ("property", "pois", "buffers", "basemap") if k in layers]
    map_item.setCrs(project.crs())
    map_item.setLayers(order)
    map_item.setKeepLayerSet(True)
    p = next(result.property_layer.getFeatures()).geometry().asPoint()
    half = max(BUFFERS_M) * MAP_MARGIN
    map_item.zoomToExtent(QgsRectangle(p.x() - half, p.y() - half, p.x() + half, p.y() + half))

    # Template links are stored by uuid; re-link explicitly to be safe.
    _item(layout, "north_arrow", QgsLayoutItemPicture).setLinkedMap(map_item)
    bar = _item(layout, "scalebar", QgsLayoutItemScaleBar)
    bar.setLinkedMap(map_item)
    bar.setUnits(Qgis.DistanceUnit.Meters)
    bar.update()

    legend = _item(layout, "legend", QgsLayoutItemLegend)
    legend.setLinkedMap(map_item)
    legend.setAutoUpdateModel(False)
    root = legend.model().rootGroup()  # owned by the legend item
    root.removeAllChildren()
    for k in ("property", "buffers", "pois"):
        root.addLayer(layers[k])
    legend.refresh()

    _fill_table(layout, result)

    summary = _item(layout, "summary", QgsLayoutItemLabel)
    if summary_text:
        summary.setText(summary_text)
        summary.setVisibility(True)

    source = result.poi_source or "none"
    _item(layout, "attribution", QgsLayoutItemLabel).setText(
        "Basemap and map data © OpenStreetMap contributors · "
        f"POI source: {source} · Generated with QGIS {Qgis.version().split('-')[0]}"
    )
    layout.refresh()
    return layout


def export_pdf(layout: QgsPrintLayout, path: str, dpi: int = 200) -> None:
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = dpi
    settings.rasterizeWholeImage = False
    res = exporter.exportToPdf(path, settings)
    if res != QgsLayoutExporter.ExportResult.Success:
        raise RuntimeError(f"PDF export failed ({res}): {exporter.errorMessage()}")
