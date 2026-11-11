"""Generate the layer styles (.qml) used by generate_report.py.

Run once inside the container and commit the output:
    docker compose run --rm qgis python3 tools/make_styles.py
The .qml files can afterwards be fine-tuned in QGIS Desktop.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsCategorizedSymbolRenderer,
    QgsField,
    QgsFillSymbol,
    QgsMarkerSymbol,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)

from report.analysis import CATEGORY_LABELS  # noqa: E402
from report.app import qgis_app  # noqa: E402

STYLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles")

POI_COLORS = {
    "beach": "#1f9ed1",
    "supermarket": "#2e9e44",
    "restaurant": "#e3711b",
    "cafe": "#8c5a3c",
    "pharmacy": "#d62f5f",
    "bus_stop": "#6a4fb3",
}
OTHER_COLOR = "#7f7f7f"


def _layer(geom, fields):
    layer = QgsVectorLayer(f"{geom}?crs=EPSG:4326", "tmp", "memory")
    layer.dataProvider().addAttributes(fields)
    layer.updateFields()
    return layer


def _save(layer, filename):
    path = os.path.join(STYLE_DIR, filename)
    msg, ok = layer.saveNamedStyle(path)
    if not ok:
        raise RuntimeError(f"Saving {path} failed: {msg}")
    print(f"wrote {path}")


def property_style():
    layer = _layer("Point", [QgsField("name", QMetaType.Type.QString)])
    sym = QgsMarkerSymbol.createSimple({
        "name": "star", "color": "#d7191c", "outline_color": "#ffffff",
        "outline_width": "0.6", "size": "7",
    })
    renderer = QgsSingleSymbolRenderer(sym)
    layer.setRenderer(renderer)
    _save(layer, "property.qml")


def buffer_style():
    layer = _layer("Polygon", [QgsField("radius_m", QMetaType.Type.Int)])
    cats = []
    for radius, color, label in ((500, "#08519c", "500 m radius"),
                                 (1000, "#4292c6", "1 km radius")):
        c = QColor(color)
        sym = QgsFillSymbol.createSimple({
            "color": f"{c.red()},{c.green()},{c.blue()},28",
            "outline_color": color,
            "outline_width": "0.6",
            "outline_style": "dash",
        })
        cats.append(QgsRendererCategory(radius, sym, label))
    layer.setRenderer(QgsCategorizedSymbolRenderer("radius_m", cats))
    _save(layer, "buffers.qml")


def poi_style():
    layer = _layer("Point", [QgsField("name", QMetaType.Type.QString),
                             QgsField("category", QMetaType.Type.QString)])
    cats = []
    for key, label in CATEGORY_LABELS.items():
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle", "color": POI_COLORS.get(key, OTHER_COLOR),
            "outline_color": "#ffffff", "outline_width": "0.4", "size": "3.2",
        })
        cats.append(QgsRendererCategory(key, sym, label))
    other = QgsMarkerSymbol.createSimple({
        "name": "circle", "color": OTHER_COLOR, "outline_color": "#ffffff",
        "outline_width": "0.4", "size": "2.6",
    })
    cats.append(QgsRendererCategory("", other, "Other"))  # "" = all other values
    layer.setRenderer(QgsCategorizedSymbolRenderer("category", cats))
    _save(layer, "pois.qml")


if __name__ == "__main__":
    os.makedirs(STYLE_DIR, exist_ok=True)
    with qgis_app():
        property_style()
        buffer_style()
        poi_style()
