"""Modul pencarian spasial tetangga terdekat (Nearest Neighbor).

Mengatasi limitasi bounding-box QgsSpatialIndex dengan mengambil k>=8 kandidat,
menghitung jarak eksak ke geometri, dan menerapkan tie-break ID terkecil.
"""

from typing import Any, Dict, Optional, Set, Tuple

try:
    from qgis.core import (
        QgsGeometry,
        QgsPointXY,
        QgsSpatialIndex,
    )
except ImportError:
    QgsGeometry = None
    QgsPointXY = None
    QgsSpatialIndex = None


def cari_terdekat(
    geom_sumber: Any,
    spatial_index: Any,
    dict_geometri: Dict[Any, Any],
    k: int = 8,
    filter_ids: Optional[Set[Any]] = None,
    kecualikan_id: Optional[Any] = None,
) -> Tuple[Optional[Any], Optional[Any], float]:
    """Mencari geometri terdekat dalam indeks spasial dengan jarak eksak.

    Args:
        geom_sumber: Titik atau geometri acuan (QgsGeometry atau QgsPointXY).
        spatial_index: Indeks spasial QgsSpatialIndex.
        dict_geometri: Pemetaan ID -> QgsGeometry eksak.
        k: Jumlah kandidat awal dari indeks spasial (default 8).
        filter_ids: Himpunan ID yang diizinkan (misal hanya jaringan aktif).
        kecualikan_id: ID yang tidak boleh dipilih (misal fitur dirinya sendiri).

    Returns:
        Tuple[Optional[Any], Optional[Any], float]:
            (ID fitur terdekat, QgsPointXY titik terdekat pada target, jarak eksak dalam meter).
            Jika tidak ada kandidat, mengembalikan (None, None, float('inf')).
    """
    if spatial_index is None or not dict_geometri or geom_sumber is None:
        return None, None, float("inf")

    # Pastikan geom_sumber berupa objek QgsGeometry agar dapat menghitung distance ke QgsGeometry lain
    if QgsPointXY is not None and isinstance(geom_sumber, QgsPointXY):
        geom_qgs = QgsGeometry.fromPointXY(geom_sumber)
    elif QgsGeometry is not None and isinstance(geom_sumber, QgsGeometry):
        geom_qgs = geom_sumber
    elif hasattr(geom_sumber, "x") and hasattr(geom_sumber, "y"):
        if QgsGeometry is not None and QgsPointXY is not None:
            geom_qgs = QgsGeometry.fromPointXY(QgsPointXY(geom_sumber.x(), geom_sumber.y()))
        else:
            geom_qgs = None
    else:
        geom_qgs = geom_sumber

    if geom_qgs is None:
        return None, None, float("inf")

    # Ambil kandidat dari spatial index
    kandidat_ids = spatial_index.nearestNeighbor(geom_qgs, max(k, 8))
    if not kandidat_ids:
        return None, None, float("inf")

    terdekat_id = None
    jarak_terkecil = float("inf")
    titik_terdekat = None

    for fid in kandidat_ids:
        if kecualikan_id is not None and fid == kecualikan_id:
            continue
        if filter_ids is not None and fid not in filter_ids:
            continue

        geom_target = dict_geometri.get(fid)
        if geom_target is None or geom_target.isNull() or geom_target.isEmpty():
            continue

        jarak = geom_qgs.distance(geom_target)

        # Cek apakah lebih dekat atau tie-break dengan ID terkecil
        is_closer = jarak < (jarak_terkecil - 1e-9)
        is_tie = abs(jarak - jarak_terkecil) <= 1e-9
        tie_break_wins = is_tie and (terdekat_id is None or str(fid) < str(terdekat_id))

        if is_closer or tie_break_wins:
            jarak_terkecil = jarak
            terdekat_id = fid
            if hasattr(geom_target, "nearestPoint"):
                titik_terdekat = geom_target.nearestPoint(geom_qgs)

    if terdekat_id is None:
        return None, None, float("inf")

    # Ambil titik terdekat sebagai QgsPointXY
    pt_xy = None
    if titik_terdekat is not None:
        if hasattr(titik_terdekat, "asPoint"):
            pt_xy = titik_terdekat.asPoint()
        elif hasattr(titik_terdekat, "x") and hasattr(titik_terdekat, "y"):
            pt_xy = titik_terdekat

    return terdekat_id, pt_xy, jarak_terkecil
