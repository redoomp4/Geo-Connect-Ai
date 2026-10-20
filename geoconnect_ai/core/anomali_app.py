"""Modul deteksi anomali keterhubungan APP (kWh meter pelanggan).

Mereplikasi aturan QGIS Topology Checker 'point not covered by segment':
Jika jarak APP ke garis jaringan terdekat <= app_cover_m (0.5 m), maka status 'ADA'.
Jika jarak > app_cover_m, maka status 'TIDAK ADA' (anomali).
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

from .nearest import cari_terdekat
from .validator import ambil_nilai_id


class HasilAnomaliAPP:
    """Hasil analisis status keterhubungan APP."""

    def __init__(self):
        self.layer_hasil: Optional[Any] = None
        self.fitur_hasil: List[Any] = []
        self.jumlah_total: int = 0
        self.jumlah_ada: int = 0
        self.jumlah_tidak_ada: int = 0
        self.detail_app: List[Dict[str, Any]] = []


def deteksi_anomali_app(
    daftar_app: List[Any],
    daftar_jaringan: List[Any],
    app_cover_m: float = 0.5,
    field_id_app: Optional[str] = None,
    field_id_jaringan: Optional[str] = None,
    crs: Optional[Any] = None,
) -> HasilAnomaliAPP:
    """Mendeteksi apakah tiap titik APP berada pada garis jaringan listrik."""
    hasil = HasilAnomaliAPP()
    hasil.jumlah_total = len(daftar_app)
    auth_id = crs.authid() if (crs and hasattr(crs, "authid")) else "EPSG:32750"

    layer_app_anomali = None
    if QgsVectorLayer is not None:
        layer_app_anomali = QgsVectorLayer(
            f"Point?crs={auth_id}", "APP Anomali", "memory"
        )
        pr = layer_app_anomali.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ID_APP", QVariant.String if QVariant else 10, len=50))
        fields.append(QgsField("STATUS", QVariant.String if QVariant else 10, len=15))
        fields.append(QgsField("JARAK_M", QVariant.Double if QVariant else 6, prec=3))
        fields.append(QgsField("ID_TERDEKAT", QVariant.String if QVariant else 10, len=50))
        pr.addAttributes(fields)
        layer_app_anomali.updateFields()

    index_jaringan = QgsSpatialIndex() if QgsSpatialIndex else None
    dict_geom_jaringan = {}
    dict_id_jaringan = {}

    # Gunakan idx_global sebagai ID unik untuk menghindari tabrakan FID lintas layer
    for idx_global, j in enumerate(daftar_jaringan, start=1):
        fid = idx_global
        jid_val = ambil_nilai_id(j, field_id_jaringan)
        geom = j.geometry() if hasattr(j, "geometry") else None
        if geom and not geom.isNull() and not geom.isEmpty():
            dict_geom_jaringan[fid] = geom
            dict_id_jaringan[fid] = jid_val
            if index_jaringan:
                feat_j = QgsFeature(j)
                feat_j.setId(fid)
                index_jaringan.addFeature(feat_j)

    daftar_fitur_hasil = []

    for a_idx, app_fitur in enumerate(daftar_app, start=1):
        app_id_val = ambil_nilai_id(app_fitur, field_id_app)
        geom_app = app_fitur.geometry() if hasattr(app_fitur, "geometry") else None
        if geom_app is None or geom_app.isNull() or geom_app.isEmpty():
            continue

        fid_terdekat, pt_terdekat, jarak = cari_terdekat(
            geom_app,
            index_jaringan,
            dict_geom_jaringan,
            k=8,
        )

        id_jaringan_terdekat = (
            dict_id_jaringan.get(fid_terdekat) if fid_terdekat is not None else None
        )

        is_ada = jarak <= (app_cover_m + 1e-9)
        status_str = "ADA" if is_ada else "TIDAK ADA"

        if is_ada:
            hasil.jumlah_ada += 1
        else:
            hasil.jumlah_tidak_ada += 1

        f_hasil = QgsFeature(a_idx) if QgsFeature else None
        if f_hasil is not None:
            f_hasil.setGeometry(geom_app)
            f_hasil.setAttributes([
                str(app_id_val),
                status_str,
                round(jarak, 3) if jarak != float("inf") else -1.0,
                str(id_jaringan_terdekat) if id_jaringan_terdekat is not None else "",
            ])
            daftar_fitur_hasil.append(f_hasil)

        hasil.detail_app.append({
            "id_app": app_id_val,
            "fid": a_idx,
            "feature": app_fitur,
            "geom": geom_app,
            "status": status_str,
            "jarak_m": round(jarak, 3) if jarak != float("inf") else -1.0,
            "id_terdekat": id_jaringan_terdekat,
            "pt_terdekat": pt_terdekat,
        })

    if layer_app_anomali is not None and daftar_fitur_hasil:
        layer_app_anomali.dataProvider().addFeatures(daftar_fitur_hasil)
        layer_app_anomali.updateExtents()
        hasil.fitur_hasil = list(layer_app_anomali.getFeatures())
    else:
        hasil.fitur_hasil = daftar_fitur_hasil

    hasil.layer_hasil = layer_app_anomali
    return hasil
