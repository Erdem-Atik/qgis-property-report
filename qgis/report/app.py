"""Headless QgsApplication lifecycle helper."""
import os
from contextlib import contextmanager

from qgis.core import QgsApplication, QgsSettings

FONT_FAMILY = "DejaVu Sans"  # available in the qgis/qgis image
USER_AGENT_SUFFIX = "qgis-property-report"


@contextmanager
def qgis_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QgsApplication([], False)
    app.setPrefixPath("/usr", True)
    app.initQgis()
    # Identify the app to tile servers (OSM tile usage policy).
    settings = QgsSettings()
    ua = settings.value("/qgis/networkAndProxy/userAgent", "Mozilla/5.0")
    if USER_AGENT_SUFFIX not in ua:
        settings.setValue("/qgis/networkAndProxy/userAgent", f"{ua} {USER_AGENT_SUFFIX}")
    try:
        yield app
    finally:
        app.exitQgis()
