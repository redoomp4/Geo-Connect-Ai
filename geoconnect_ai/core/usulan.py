"""Modul pembuatan usulan Saluran Luar Tegangan Rendah (SLTR) untuk APP anomali.

Menentukan titik penyambungan terdekat HANYA ke segmen jaringan aktif (menyentuh Gardu).
Menerapkan batas toleransi maksimum `app_usulan_maks_m` (default 50 meter).
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

from .nearest import cari_terdekat
from .validator import ambil_nilai_id


class HasilUsulanSLTR:
    """Hasil pembentukan garis SLTR usulan untuk APP anomali."""

    def __init__(self):
        self.layer_hasil: Optional[Any] = None
        self.fitur_hasil: List[Any] = []
        self.jumlah_usulan: int = 0
        self.jumlah_tanpa_usulan: int = 0
        self.detail_usulan: List[Dict[str, Any]] = []


def buat_sltr_usulan(
    daftar_app_anomali: List[Dict[str, Any]],
    daftar_jaringan_aktif: List[Any],
    app_usulan_maks_m: float = 50.0,
    field_id_jaringan: Optional[str] = None,
    crs: Optional[Any] = None,
) -> HasilUsulanSLTR:
    """Membuat garis SLTR Usulan dari APP berstatus TIDAK ADA ke jaringan aktif terdekat."""
    hasil = HasilUsulanSLTR()
    auth_id = crs.authid() if (crs and hasattr(crs, "authid")) else "EPSG:32750"

    layer_usulan = None
    if QgsVectorLayer is not None:
        layer_usulan = QgsVectorLayer(
            f"LineString?crs={auth_id}", "SLTR Usulan", "memory"
        )
        pr = layer_usulan.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ID_APP", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("ID_TARGET", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("JARAK_M", QVariant.Double if QVariant else 6, prec=3))
        fields.append(QgsField("STATUS", QVariant.String if QVariant else 10, len=15))
        pr.addAttributes(fields)
        layer_usulan.updateFields()

    if not daftar_jaringan_aktif:
        hasil.jumlah_tanpa_usulan = len(daftar_app_anomali)
        hasil.layer_hasil = layer_usulan
        return hasil

    index_aktif = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_geom_aktif = {}
    dict_id_aktif = {}

    for idx_global, line in enumerate(daftar_jaringan_aktif, start=1):
        fid = idx_global
        lid_val = ambil_nilai_id(line, field_id_jaringan)
        geom = line.geometry() if hasattr(line, "geometry") else None
        if geom and not geom.isNull() and not geom.isEmpty():
            dict_geom_aktif[fid] = geom
            dict_id_aktif[fid] = lid_val
            if index_aktif:
                feat_l = QgsFeature(line)
                feat_l.setId(fid)
                index_aktif.addFeature(feat_l)

    daftar_fitur_baru = []

    for u_idx, app_item in enumerate(daftar_app_anomali, start=1):
        if app_item.get("status") != "TIDAK ADA":
            continue

        id_app = app_item["id_app"]
        geom_app = app_item["geom"]

        fid_target, pt_target, jarak = cari_terdekat(
            geom_app,
            index_aktif,
            dict_geom_aktif,
            k=8,
        )

        if (
            fid_target is not None
            and jarak <= (app_usulan_maks_m + 1e-9)
            and pt_target is not None
        ):
            target_id_val = dict_id_aktif.get(fid_target)
            pt_app = geom_app.asPoint() if hasattr(geom_app, "asPoint") else None
            if pt_app is None:
                continue

            geom_line = QgsGeometry.fromPolylineXY([
                QgsPointXY(pt_app.x(), pt_app.y()),
                QgsPointXY(pt_target.x(), pt_target.y()),
            ]) if QgsGeometry else None

            f_usulan = QgsFeature(u_idx) if QgsFeature else None
            if f_usulan is not None:
                f_usulan.setGeometry(geom_line)
                f_usulan.setAttributes([
                    str(id_app),
                    str(target_id_val) if target_id_val is not None else "",
                    round(jarak, 3),
                    "USULAN",
                ])
                daftar_fitur_baru.append(f_usulan)

            hasil.jumlah_usulan += 1
            hasil.detail_usulan.append({
                "id_app": id_app,
                "id_target": target_id_val,
                "jarak_m": round(jarak, 3),
                "status": "USULAN",
                "geom": geom_line,
            })
        else:
            hasil.jumlah_tanpa_usulan += 1
            hasil.detail_usulan.append({
                "id_app": id_app,
                "id_target": None,
                "jarak_m": round(jarak, 3) if jarak != float("inf") else -1.0,
                "status": "TANPA USULAN",
                "geom": None,
            })

    if layer_usulan is not None and daftar_fitur_baru:
        layer_usulan.dataProvider().addFeatures(daftar_fitur_baru)
        layer_usulan.updateExtents()
        hasil.fitur_hasil = list(layer_usulan.getFeatures())
    else:
        hasil.fitur_hasil = daftar_fitur_baru

    hasil.layer_hasil = layer_usulan
    return hasil
