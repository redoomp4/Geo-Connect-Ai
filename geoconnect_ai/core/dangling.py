"""Modul deteksi dan penyambungan dangling line pada Jaringan Tegangan Rendah (JTR).

Mendeteksi ujung garis yang menggantung (tanpa sambungan ke segmen lain atau Gardu)
dan mengusulkan garis penghubung baru ke segmen terdekat dalam batas toleransi.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsPointXY,
        QgsRectangle,
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
    QgsRectangle = None
    QgsSpatialIndex = None
    QgsVectorLayer = None
    QVariant = None

from .nearest import cari_terdekat
from .validator import ambil_nilai_id


class HasilDangling:
    """Hasil deteksi dan penyambungan garis dangling."""

    def __init__(self):
        self.layer_hasil: Optional[Any] = None
        self.fitur_penghubung: List[Any] = []
        self.jumlah_terdeteksi: int = 0
        self.jumlah_tersambung: int = 0
        self.jumlah_tidak_tersambung: int = 0
        self.detail_dangling: List[Dict[str, Any]] = []


def deteksi_dangling(
    daftar_jtr: List[Any],
    daftar_gardu: List[Any],
    epsilon_m: float = 0.05,
    field_id_jtr: Optional[str] = None,
    field_id_gardu: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mendeteksi seluruh ujung dangling pada kumpulan segmen JTR."""
    if not daftar_jtr:
        return []

    index_gardu = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_geom_gardu = {}
    if daftar_gardu:
        for g_idx, g in enumerate(daftar_gardu, start=1):
            fid_g = g.id() if hasattr(g, "id") and g.id() > 0 else g_idx
            geom_g = g.geometry() if hasattr(g, "geometry") else None
            if geom_g and not geom_g.isNull() and not geom_g.isEmpty():
                dict_geom_gardu[fid_g] = geom_g
                if index_gardu:
                    feat_g = QgsFeature(g)
                    feat_g.setId(fid_g)
                    index_gardu.addFeature(feat_g)

    index_jtr = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_geom_jtr = {}
    for j_idx, j in enumerate(daftar_jtr, start=1):
        fid_j = j.id() if hasattr(j, "id") and j.id() > 0 else j_idx
        geom_j = j.geometry() if hasattr(j, "geometry") else None
        if geom_j and not geom_j.isNull() and not geom_j.isEmpty():
            dict_geom_jtr[fid_j] = geom_j
            if index_jtr:
                feat_j = QgsFeature(j)
                feat_j.setId(fid_j)
                index_jtr.addFeature(feat_j)

    dangling_list = []

    for j_idx, j in enumerate(daftar_jtr, start=1):
        fid_j = j.id() if hasattr(j, "id") and j.id() > 0 else j_idx
        jid_val = ambil_nilai_id(j, field_id_jtr)
        geom_j = j.geometry() if hasattr(j, "geometry") else None
        if geom_j is None or geom_j.isNull() or geom_j.isEmpty():
            continue

        pts = geom_j.asPolyline() if hasattr(geom_j, "asPolyline") else []
        if not pts:
            multi = geom_j.asMultiPolyline() if hasattr(geom_j, "asMultiPolyline") else []
            if multi and len(multi) > 0:
                pts = list(multi[0])

        if len(pts) < 2:
            continue

        for idx_ujung, pt_ujung in ((0, pts[0]), (-1, pts[-1])):
            geom_pt = QgsGeometry.fromPointXY(pt_ujung) if QgsGeometry else None
            if geom_pt is None:
                continue

            di_gardu = False
            if index_gardu:
                rect_g = QgsRectangle(
                    pt_ujung.x() - epsilon_m,
                    pt_ujung.y() - epsilon_m,
                    pt_ujung.x() + epsilon_m,
                    pt_ujung.y() + epsilon_m,
                )
                kandidat_g = index_gardu.intersects(rect_g)
                for g_id in kandidat_g:
                    g_geom = dict_geom_gardu.get(g_id)
                    if g_geom and geom_pt.distance(g_geom) <= (epsilon_m + 1e-9):
                        di_gardu = True
                        break

            if di_gardu:
                continue

            tersambung_jtr_lain = False
            if index_jtr:
                rect_j = QgsRectangle(
                    pt_ujung.x() - epsilon_m,
                    pt_ujung.y() - epsilon_m,
                    pt_ujung.x() + epsilon_m,
                    pt_ujung.y() + epsilon_m,
                )
                kandidat_j = index_jtr.intersects(rect_j)
                for other_fid in kandidat_j:
                    if other_fid == fid_j:
                        continue
                    other_geom = dict_geom_jtr.get(other_fid)
                    if other_geom and geom_pt.distance(other_geom) <= (epsilon_m + 1e-9):
                        tersambung_jtr_lain = True
                        break

            if tersambung_jtr_lain:
                continue

            dangling_list.append({
                "id_jtr": jid_val,
                "fid_jtr": fid_j,
                "pt": pt_ujung,
                "geom_pt": geom_pt,
                "idx_ujung": idx_ujung,
            })

    return dangling_list


def sambung_dangling(
    daftar_dangling: List[Dict[str, Any]],
    daftar_jtr: List[Any],
    toleransi_m: float = 8.0,
    field_id_jtr: Optional[str] = None,
    crs: Optional[Any] = None,
    graf: Optional[Dict[str, Any]] = None,
) -> HasilDangling:
    """Menyambungkan ujung-ujung dangling ke segmen JTR lain terdekat dalam toleransi."""
    hasil = HasilDangling()
    hasil.jumlah_terdeteksi = len(daftar_dangling)
    auth_id = crs.authid() if (crs and hasattr(crs, "authid")) else "EPSG:32750"

    layer_dangling = None
    if QgsVectorLayer is not None:
        layer_dangling = QgsVectorLayer(
            f"LineString?crs={auth_id}", "Penyambungan Dangling", "memory"
        )
        pr = layer_dangling.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ID_JTR", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("ID_TARGET", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("JARAK_M", QVariant.Double if QVariant else 6, prec=3))
        fields.append(QgsField("STATUS", QVariant.String if QVariant else 10, len=15))
        pr.addAttributes(fields)
        layer_dangling.updateFields()

    index_jtr = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_geom_jtr = {}
    dict_jtr_id = {}
    for j_idx, j in enumerate(daftar_jtr, start=1):
        fid = j.id() if hasattr(j, "id") and j.id() > 0 else j_idx
        jid_val = ambil_nilai_id(j, field_id_jtr)
        geom = j.geometry() if hasattr(j, "geometry") else None
        if geom and not geom.isNull() and not geom.isEmpty():
            dict_geom_jtr[fid] = geom
            dict_jtr_id[fid] = jid_val
            if index_jtr:
                feat_j = QgsFeature(j)
                feat_j.setId(fid)
                index_jtr.addFeature(feat_j)

    daftar_fitur_baru = []

    for idx_dang, dang in enumerate(daftar_dangling, start=1):
        jid_asal = dang["id_jtr"]
        fid_asal = dang["fid_jtr"]
        pt_dangling = dang["pt"]
        geom_pt = dang["geom_pt"]

        target_fid, pt_target, jarak = cari_terdekat(
            geom_pt,
            index_jtr,
            dict_geom_jtr,
            k=8,
            kecualikan_id=fid_asal,
        )

        target_id_val = None

        if target_fid is not None and jarak <= (toleransi_m + 1e-9) and pt_target is not None:
            target_id_val = dict_jtr_id.get(target_fid)

            geom_penghubung = QgsGeometry.fromPolylineXY([
                QgsPointXY(pt_dangling.x(), pt_dangling.y()),
                QgsPointXY(pt_target.x(), pt_target.y()),
            ]) if QgsGeometry else None

            f_penghubung = QgsFeature(idx_dang) if QgsFeature else None
            if f_penghubung is not None:
                f_penghubung.setGeometry(geom_penghubung)
                f_penghubung.setAttributes([
                    str(jid_asal),
                    str(target_id_val) if target_id_val is not None else "",
                    round(jarak, 3),
                    "TERSAMBUNG",
                ])
                daftar_fitur_baru.append(f_penghubung)

            hasil.jumlah_tersambung += 1
            hasil.detail_dangling.append({
                "id_jtr": jid_asal,
                "id_target": target_id_val,
                "jarak_m": round(jarak, 3),
                "status": "TERSAMBUNG",
                "geom_penghubung": geom_penghubung,
            })
        else:
            hasil.jumlah_tidak_tersambung += 1
            hasil.detail_dangling.append({
                "id_jtr": jid_asal,
                "id_target": None,
                "jarak_m": round(jarak, 3) if jarak != float("inf") else -1.0,
                "status": "TIDAK",
                "geom_penghubung": None,
            })

    if layer_dangling is not None and daftar_fitur_baru:
        layer_dangling.dataProvider().addFeatures(daftar_fitur_baru)
        layer_dangling.updateExtents()
        hasil.fitur_penghubung = list(layer_dangling.getFeatures())
    else:
        hasil.fitur_penghubung = daftar_fitur_baru

    hasil.layer_hasil = layer_dangling
    return hasil
