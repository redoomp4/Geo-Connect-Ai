"""Modul pengelompokan layer hasil ke dalam QgsLayerTreeGroup.

Menyusun layer hasil ke dalam grup bernama 'GeoConnect-AI - Hasil (HH:MM:SS)'
di posisi teratas layer tree tanpa mengganggu layer atau grup lain milik pengguna.
"""

from datetime import datetime
from typing import Any, List, Optional

try:
    from qgis.core import (
        QgsLayerTreeGroup,
        QgsProject,
        QgsVectorLayer,
    )
except ImportError:
    QgsLayerTreeGroup = None
    QgsProject = None
    QgsVectorLayer = None


def kelompokkan_layer(
    layer_jtr_snapped: Optional[Any],
    layer_dangling: Optional[Any],
    layer_app_anomali: Optional[Any],
    layer_sltr_usulan: Optional[Any],
    project: Optional[Any] = None,
) -> Optional[Any]:
    """Mengelompokkan 4 layer hasil analisis ke grup teratas pada QGIS Layer Tree.

    Urutan layer di dalam grup (dari atas ke bawah):
    1. APP Anomali (Titik)
    2. SLTR Usulan (Garis putus-putus)
    3. Penyambungan Dangling (Garis putus-putus)
    4. JTR Snapping (Garis)

    Args:
        layer_jtr_snapped: Layer hasil snapping JTR.
        layer_dangling: Layer hasil penyambungan dangling.
        layer_app_anomali: Layer titik APP anomali.
        layer_sltr_usulan: Layer garis usulan SLTR.
        project: Instansiasi QgsProject (default QgsProject.instance()).

    Returns:
        QgsLayerTreeGroup: Objek grup pohon layer yang berhasil dibuat.
    """
    prj = project or (QgsProject.instance() if QgsProject else None)
    if prj is None:
        return None

    root = prj.layerTreeRoot()
    if root is None:
        return None

    waktu_str = datetime.now().strftime("%H:%M:%S")
    nama_group = f"GeoConnect-AI - Hasil ({waktu_str})"

    # Sisipkan grup baru di urutan teratas (index 0)
    group = root.insertGroup(0, nama_group)

    # Urutan penambahan: titik di atas garis
    urutan_layer = [
        layer_app_anomali,
        layer_sltr_usulan,
        layer_dangling,
        layer_jtr_snapped,
    ]

    for lyr in urutan_layer:
        if lyr is not None and hasattr(lyr, "isValid") and lyr.isValid():
            # Daftarkan layer ke project (False = jangan auto-add ke root tree)
            prj.addMapLayer(lyr, False)
            # Tambahkan ke dalam grup GeoConnect-AI
            group.addLayer(lyr)

    return group
