"""Modul styling visual untuk layer-layer hasil analisis GeoConnect-AI.

Menerapkan simbologi tematik (QgsCategorizedSymbolRenderer):
- APP ADA: Titik hijau kecil
- APP TIDAK ADA: Titik merah lebih besar (anomali)
- SLTR Usulan: Garis oranye putus-putus
- Penyambungan Dangling: Garis biru muda putus-putus
- JTR Snapping: Garis SNAPPED (cyan/emerald) dan UTUH (slate)
"""

from typing import Any, Optional

try:
    from qgis.core import (
        QgsCategorizedSymbolRenderer,
        QgsLineSymbol,
        QgsMarkerSymbol,
        QgsRendererCategory,
        QgsSimpleLineSymbolLayer,
        QgsSimpleMarkerSymbolLayer,
        QgsSymbol,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor
except ImportError:
    QgsCategorizedSymbolRenderer = None
    QgsLineSymbol = None
    QgsMarkerSymbol = None
    QgsRendererCategory = None
    QgsSimpleLineSymbolLayer = None
    QgsSimpleMarkerSymbolLayer = None
    QgsSymbol = None
    Qt = None
    QColor = None


def get_qt_dash_line():
    """Helper kompatibilitas Qt.DashLine antara PyQt5 dan PyQt6."""
    if Qt is None:
        return 2
    if hasattr(Qt, "PenStyle") and hasattr(Qt.PenStyle, "DashLine"):
        return Qt.PenStyle.DashLine
    return getattr(Qt, "DashLine", 2)


def get_qt_solid_line():
    """Helper kompatibilitas Qt.SolidLine antara PyQt5 dan PyQt6."""
    if Qt is None:
        return 1
    if hasattr(Qt, "PenStyle") and hasattr(Qt.PenStyle, "SolidLine"):
        return Qt.PenStyle.SolidLine
    return getattr(Qt, "SolidLine", 1)


def terapkan_style_app_anomali(layer_app: Any) -> bool:
    """Menerapkan simbologi kategorisasi pada layer APP Anomali.

    - ADA: Titik hijau kecil (diameter 2.0 mm)
    - TIDAK ADA: Titik merah mencolok (diameter 3.8 mm)
    """
    if layer_app is None or QgsCategorizedSymbolRenderer is None:
        return False

    categories = []

    # 1. Simbol ADA (Hijau)
    sym_ada = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": "#10B981", # Emerald green
        "outline_color": "#065F46",
        "outline_width": "0.4",
        "size": "2.2",
    })
    cat_ada = QgsRendererCategory("ADA", sym_ada, "ADA (Tersambung)")
    categories.append(cat_ada)

    # 2. Simbol TIDAK ADA (Merah anomali)
    sym_tidak_ada = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": "#EF4444", # Vibrant red
        "outline_color": "#7F1D1D",
        "outline_width": "0.8",
        "size": "3.8",
    })
    cat_tidak_ada = QgsRendererCategory("TIDAK ADA", sym_tidak_ada, "TIDAK ADA (Anomali Belum Tersambung)")
    categories.append(cat_tidak_ada)

    renderer = QgsCategorizedSymbolRenderer("STATUS", categories)
    layer_app.setRenderer(renderer)
    if hasattr(layer_app, "triggerRepaint"):
        layer_app.triggerRepaint()
    return True


def terapkan_style_sltr_usulan(layer_sltr: Any) -> bool:
    """Menerapkan garis oranye putus-putus untuk SLTR Usulan."""
    if layer_sltr is None or QgsLineSymbol is None:
        return False

    sym_usulan = QgsLineSymbol.createSimple({
        "color": "#F59E0B", # Amber / Orange
        "width": "0.7",
        "line_style": "dash",
    })
    if hasattr(layer_sltr, "setRenderer"):
        from qgis.core import QgsSingleSymbolRenderer
        layer_sltr.setRenderer(QgsSingleSymbolRenderer(sym_usulan))
        if hasattr(layer_sltr, "triggerRepaint"):
            layer_sltr.triggerRepaint()
    return True


def terapkan_style_dangling(layer_dangling: Any) -> bool:
    """Menerapkan garis biru muda putus-putus untuk Penyambungan Dangling."""
    if layer_dangling is None or QgsLineSymbol is None:
        return False

    sym_dangling = QgsLineSymbol.createSimple({
        "color": "#00B4D8", # Cyan / Blue
        "width": "0.7",
        "line_style": "dash",
    })
    if hasattr(layer_dangling, "setRenderer"):
        from qgis.core import QgsSingleSymbolRenderer
        layer_dangling.setRenderer(QgsSingleSymbolRenderer(sym_dangling))
        if hasattr(layer_dangling, "triggerRepaint"):
            layer_dangling.triggerRepaint()
    return True


def terapkan_style_jtr_snapping(layer_jtr: Any) -> bool:
    """Menerapkan simbologi kategorisasi untuk JTR Snapping (SNAPPED vs UTUH)."""
    if layer_jtr is None or QgsCategorizedSymbolRenderer is None:
        return False

    categories = []

    # SNAPPED: Garis hijau zamrud / cyan terang
    sym_snapped = QgsLineSymbol.createSimple({
        "color": "#06D6A0",
        "width": "0.8",
        "line_style": "solid",
    })
    cat_snapped = QgsRendererCategory("SNAPPED", sym_snapped, "SNAPPED (Bergeser ke Gardu)")
    categories.append(cat_snapped)

    # UTUH: Garis biru dongker / abu-abu solid
    sym_utuh = QgsLineSymbol.createSimple({
        "color": "#475569",
        "width": "0.5",
        "line_style": "solid",
    })
    cat_utuh = QgsRendererCategory("UTUH", sym_utuh, "UTUH (Tidak Berubah)")
    categories.append(cat_utuh)

    renderer = QgsCategorizedSymbolRenderer("STATUS", categories)
    layer_jtr.setRenderer(renderer)
    if hasattr(layer_jtr, "triggerRepaint"):
        layer_jtr.triggerRepaint()
    return True
