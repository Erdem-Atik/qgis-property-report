"""Generate the A4 print layout template (templates/report_a4.qpt).

Run once inside the container and commit the output:
    docker compose run --rm qgis python3 tools/make_template.py
Item ids used by report/render.py:
    title, subtitle, map, north_arrow, scalebar, legend,
    distance_table, summary_title, summary, attribution
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.PyQt.QtGui import QColor, QFont  # noqa: E402
from qgis.core import (  # noqa: E402
    Qgis,
    QgsLayoutFrame,
    QgsLegendStyle,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemManualTable,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsReadWriteContext,
    QgsTextFormat,
    QgsUnitTypes,
)

from report.app import FONT_FAMILY, qgis_app  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "templates", "report_a4.qpt")
MM = QgsUnitTypes.LayoutMillimeters
MARGIN = 12
WIDTH = 210 - 2 * MARGIN
DARK = QColor("#1f2a36")
MUTED = QColor("#5b6670")


def text_format(size, bold=False, color=DARK):
    font = QFont(FONT_FAMILY)
    font.setBold(bold)
    fmt = QgsTextFormat()
    fmt.setFont(font)
    fmt.setSize(size)
    fmt.setSizeUnit(Qgis.RenderUnit.Points)
    fmt.setColor(color)
    return fmt


def place(item, x, y, w, h):
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(w, h, MM))


def label(layout, item_id, text, x, y, w, h, fmt):
    lbl = QgsLayoutItemLabel(layout)
    lbl.setId(item_id)
    lbl.setText(text)
    lbl.setTextFormat(fmt)
    layout.addLayoutItem(lbl)
    place(lbl, x, y, w, h)
    return lbl


def build(layout):
    label(layout, "title", "[Property name]", MARGIN, 10, WIDTH, 11, text_format(20, bold=True))
    label(layout, "subtitle", "[Coordinates · date]", MARGIN, 21, WIDTH, 7, text_format(9.5, color=MUTED))

    map_item = QgsLayoutItemMap(layout)
    map_item.setId("map")
    map_item.setFrameEnabled(True)
    map_item.setFrameStrokeColor(QColor("#9aa5ad"))
    layout.addLayoutItem(map_item)
    place(map_item, MARGIN, 30, WIDTH, 150)

    arrow = QgsLayoutItemPicture(layout)
    arrow.setId("north_arrow")
    arrow.setPicturePath("/usr/share/qgis/svg/arrows/NorthArrow_02.svg")
    arrow.setLinkedMap(map_item)
    arrow.setBackgroundEnabled(True)
    arrow.setBackgroundColor(QColor(255, 255, 255, 200))
    layout.addLayoutItem(arrow)
    place(arrow, MARGIN + WIDTH - 15, 33, 12, 12)

    bar = QgsLayoutItemScaleBar(layout)
    bar.setId("scalebar")
    bar.setStyle("Single Box")
    bar.setLinkedMap(map_item)
    bar.setUnits(Qgis.DistanceUnit.Meters)
    bar.setUnitLabel("m")
    bar.setNumberOfSegments(2)
    bar.setNumberOfSegmentsLeft(0)
    bar.setUnitsPerSegment(250)
    bar.setTextFormat(text_format(7.5))
    bar.setBackgroundEnabled(True)
    bar.setBackgroundColor(QColor(255, 255, 255, 200))
    layout.addLayoutItem(bar)
    place(bar, MARGIN + 3, 168, 45, 9)

    legend = QgsLayoutItemLegend(layout)
    legend.setId("legend")
    legend.setTitle("Legend")
    legend.setLinkedMap(map_item)
    legend.setAutoUpdateModel(False)
    legend.setResizeToContents(False)
    legend.setFrameEnabled(False)
    legend.setColumnCount(2)
    legend.setSplitLayer(True)
    legend.setSymbolWidth(5)
    legend.setSymbolHeight(3.5)
    for style, size, bold in ((QgsLegendStyle.Style.Title, 10, True),
                              (QgsLegendStyle.Style.Group, 8, True),
                              (QgsLegendStyle.Style.Subgroup, 8, True),
                              (QgsLegendStyle.Style.SymbolLabel, 7.5, False)):
        legend.rstyle(style).setTextFormat(text_format(size, bold=bold))
    layout.addLayoutItem(legend)
    place(legend, MARGIN, 186, 84, 60)

    table = QgsLayoutItemManualTable.create(layout)
    frame = QgsLayoutFrame(layout, table)
    frame.setId("distance_table")
    place(frame, MARGIN + 88, 186, WIDTH - 88, 60)
    table.addFrame(frame)
    table.setHeaderTextFormat(text_format(8, bold=True))
    table.setContentTextFormat(text_format(8))
    table.setGridStrokeWidth(0.2)
    table.setGridColor(QColor("#c8cfd4"))
    table.setCellMargin(1.2)
    layout.addMultiFrame(table)

    title = label(layout, "summary_title", "Location summary (AI-generated from the table data only)",
                  MARGIN, 249, WIDTH, 6, text_format(9, bold=True))
    summary = label(layout, "summary", "[AI summary]", MARGIN, 255, WIDTH, 23, text_format(9.5))
    for item in (title, summary):
        item.setVisibility(False)  # shown by render.py when a summary is requested

    label(layout, "attribution", "Basemap and map data © OpenStreetMap contributors",
          MARGIN, 280, WIDTH, 8, text_format(7, color=MUTED))


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with qgis_app():
        layout = QgsPrintLayout(QgsProject.instance())
        layout.initializeDefaults()
        layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Orientation.Portrait)
        layout.setName("Property report A4")
        build(layout)
        if not layout.saveAsTemplate(OUT, QgsReadWriteContext()):
            raise SystemExit(f"Saving template failed: {OUT}")
        print(f"wrote {OUT}")
