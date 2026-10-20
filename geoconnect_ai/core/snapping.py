"""Modul auto-snapping non-destruktif segmen JTR ke Gardu distribusi.

Menggeser vertex ujung JTR ke koordinat Gardu jika jarak <= toleransi_m.
Mempertahankan integritas layer sumber dan mencatat seluruh modifikasi usulan.
"""

from typing import Any, Dict, List, Optional, Tuple

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsPointXY,
        QgsSpatialIndex,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError:
    QgsCoordinateReferenceSystem = None
    QgsFeature = None
    QgsField = None
    QgsFields = None
    QgsGeometry = None
    QgsPointXY = None
    QgsSpatialIndex = None
    QgsVectorLayer = None
    QVariant = None

from .validator import ambil_nilai_id


class HasilSnapping:
    """Hasil pemrosesan auto-snapping JTR ke Gardu."""

    def __init__(self):
        self.layer_hasil: Optional[Any] = None
        self.fitur_hasil: List[Any] = []
        self.jumlah_snapped: int = 0
        self.jumlah_utuh: int = 0
        self.detail_log: List[Dict[str, Any]] = []


def auto_snap_jtr_ke_gardu(
    daftar_jtr: List[Any],
    daftar_gardu: List[Any],
    toleransi_m: float = 10.0,
    field_id_jtr: Optional[str] = None,
    field_id_gardu: Optional[str] = None,
    crs: Optional[Any] = None,
) -> HasilSnapping:
    """Melakukan auto-snapping ujung segmen JTR ke Gardu distribusi terdekat.

    Aturan batas: Jarak <= toleransi_m dianggap memenuhi toleransi dan di-snap.
    Layer sumber tidak disentuh; geometri baru ditulis ke layer hasil memory.

    Args:
        daftar_jtr: Kumpulan fitur JTR valid.
        daftar_gardu: Kumpulan fitur Gardu valid.
        toleransi_m: Jarak snapping maksimum dalam meter (default 10.0 m).
        field_id_jtr: Nama kolom ID untuk JTR.
        field_id_gardu: Nama kolom ID untuk Gardu.
        crs: CRS kerja terproyeksi (meter).

    Returns:
        HasilSnapping: Objek berisi layer hasil memory dan statistik snapping.
    """
    hasil = HasilSnapping()
    auth_id = crs.authid() if (crs and hasattr(crs, "authid")) else "EPSG:32750"

    # 1. Bangun spatial index titik Gardu
    index_gardu = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_gardu_pt: Dict[Any, QgsPointXY] = {}
    dict_gardu_id: Dict[Any, Any] = {}

    for g_idx, g in enumerate(daftar_gardu, start=1):
        gid_val = ambil_nilai_id(g, field_id_gardu)
        fid = g.id() if hasattr(g, "id") and g.id() > 0 else g_idx
        geom = g.geometry() if hasattr(g, "geometry") else None
        if geom is None or geom.isNull() or geom.isEmpty():
            continue

        pt = geom.asPoint() if hasattr(geom, "asPoint") else None
        if pt is None:
            continue

        dict_gardu_pt[fid] = pt
        dict_gardu_id[fid] = gid_val
        if index_gardu is not None:
            g_feature = QgsFeature(g)
            g_feature.setId(fid)
            index_gardu.addFeature(g_feature)

    # Buat layer memori untuk hasil JTR Snapping
    layer_snapped = None
    if QgsVectorLayer is not None:
        layer_snapped = QgsVectorLayer(
            f"LineString?crs={auth_id}", "JTR Snapping", "memory"
        )
        pr = layer_snapped.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ID_JTR", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("STATUS", QVariant.String if QVariant else 10, len=10))
        fields.append(QgsField("ID_GARDU", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("JARAK_M", QVariant.Double if QVariant else 6, prec=3))
        pr.addAttributes(fields)
        layer_snapped.updateFields()

    daftar_fitur_baru = []

    # 2. Proses tiap segmen JTR
    for idx_jtr, jtr in enumerate(daftar_jtr, start=1):
        jid_val = ambil_nilai_id(jtr, field_id_jtr)
        geom = jtr.geometry() if hasattr(jtr, "geometry") else None
        if geom is None or geom.isNull() or geom.isEmpty():
            continue

        pts = geom.asPolyline() if hasattr(geom, "asPolyline") else []
        if not pts or len(pts) < 2:
            multi = geom.asMultiPolyline() if hasattr(geom, "asMultiPolyline") else []
            if multi and len(multi) > 0:
                pts = list(multi[0])

        if len(pts) < 2:
            continue

        pts_baru = [QgsPointXY(p.x(), p.y()) for p in pts]
        ter_snap = False
        id_gardu_terpilih = None
        jarak_snap_terpilih = 0.0

        for idx_ujung in (0, -1):
            pt_ujung = pts_baru[idx_ujung]
            geom_ujung = QgsGeometry.fromPointXY(pt_ujung) if QgsGeometry else None

            kandidat = (
                index_gardu.nearestNeighbor(geom_ujung, 8)
                if (index_gardu and geom_ujung)
                else list(dict_gardu_pt.keys())
            )

            terdekat_fid = None
            min_jarak = float("inf")

            for g_fid in kandidat:
                pt_g = dict_gardu_pt.get(g_fid)
                if pt_g is None:
                    continue
                jarak = pt_ujung.distance(pt_g) if hasattr(pt_ujung, "distance") else (
                    ((pt_ujung.x() - pt_g.x()) ** 2 + (pt_ujung.y() - pt_g.y()) ** 2) ** 0.5
                )

                if jarak <= (toleransi_m + 1e-9):
                    is_closer = jarak < (min_jarak - 1e-9)
                    is_tie = abs(jarak - min_jarak) <= 1e-9
                    tie_wins = is_tie and (
                        terdekat_fid is None or str(g_fid) < str(terdekat_fid)
                    )
                    if is_closer or tie_wins:
                        min_jarak = jarak
                        terdekat_fid = g_fid

            if terdekat_fid is not None:
                pt_gardu = dict_gardu_pt[terdekat_fid]
                pts_baru[idx_ujung] = QgsPointXY(pt_gardu.x(), pt_gardu.y())
                ter_snap = True
                id_gardu_terpilih = dict_gardu_id[terdekat_fid]
                jarak_snap_terpilih = min_jarak

        status_str = "SNAPPED" if ter_snap else "UTUH"
        geom_baru = QgsGeometry.fromPolylineXY(pts_baru) if QgsGeometry else None

        f_baru = QgsFeature(idx_jtr) if QgsFeature else None
        if f_baru is not None:
            f_baru.setGeometry(geom_baru)
            f_baru.setAttributes([
                str(jid_val),
                status_str,
                str(id_gardu_terpilih) if id_gardu_terpilih is not None else "",
                round(jarak_snap_terpilih, 3),
            ])
            daftar_fitur_baru.append(f_baru)

        if ter_snap:
            hasil.jumlah_snapped += 1
        else:
            hasil.jumlah_utuh += 1

        hasil.detail_log.append({
            "id_jtr": jid_val,
            "status": status_str,
            "id_gardu": id_gardu_terpilih,
            "jarak_m": round(jarak_snap_terpilih, 3),
            "geom_baru": geom_baru,
        })

    if layer_snapped is not None and daftar_fitur_baru:
        layer_snapped.dataProvider().addFeatures(daftar_fitur_baru)
        layer_snapped.updateExtents()
        hasil.fitur_hasil = list(layer_snapped.getFeatures())
    else:
        hasil.fitur_hasil = daftar_fitur_baru

    hasil.layer_hasil = layer_snapped
    return hasil
