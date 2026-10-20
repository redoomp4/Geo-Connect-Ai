"""Generator data sintetis jaringan distribusi listrik untuk pengujian topologi GeoConnect-AI.

Menghasilkan titik Gardu, segmen JTR, dan APP sintetis di sekitar Balikpapan (EPSG:32750)
dengan skenario kerusakan jaringan yang dirancang khusus:
1. Ujung JTR dekat Gardu (< 10 m toleransi) -> harus ter-snap
2. Ujung JTR jauh (> 10 m toleransi) -> tetap utuh
3. Ujung JTR tepat di batas toleransi (10.0 m) -> harus ter-snap
4. Dangling line dalam toleransi (< 8 m) -> harus tersambung
5. Dangling line luar toleransi (> 8 m) -> tidak tersambung
6. Komponen terisolasi tanpa gardu
7. APP tepat di garis (jarak <= 0.5 m) -> status ADA
8. APP jauh (jarak > 0.5 m) -> status TIDAK ADA
9. APP anomali yang lebih dekat ke komponen terisolasi daripada jaringan aktif -> harus tetap diusulkan ke jaringan aktif!
10. Data duplikat dan geometri null/kosong untuk pengujian validator
"""

import math
import random
from typing import Any, Dict, List, Tuple

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsPointXY,
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
    QgsVectorLayer = None
    QVariant = None


def buat_kumpulan_data_sintetis_balikpapan(base_x: float = 480000.0, base_y: float = 9860000.0) -> Dict[str, Any]:
    """Menghasilkan struktur data layer memory sintetis dengan berbagai anomali topologi.

    Koordinat berpusat di Balikpapan Selatan, Zona UTM 50S (EPSG:32750).
    """
    # 1. Layer Gardu
    lyr_gardu = QgsVectorLayer("Point?crs=EPSG:32750", "Gardu_Sintetis", "memory")
    pr_g = lyr_gardu.dataProvider()
    fields_g = QgsFields()
    fields_g.append(QgsField("ID_GARDU", QVariant.String, len=50))
    fields_g.append(QgsField("NAMA", QVariant.String, len=100))
    pr_g.addAttributes(fields_g)
    lyr_gardu.updateFields()

    # Gardu 1: Gardu Induk / Distribusi Utama
    # Gardu 2: Gardu Sekunder
    fitur_gardu = []
    g1 = QgsFeature(lyr_gardu.fields(), 1)
    g1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x, base_y)))
    g1.setAttributes(["GD-BPP-01", "Gardu Distribusi Sepinggan 01"])
    fitur_gardu.append(g1)

    g2 = QgsFeature(lyr_gardu.fields(), 2)
    g2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 500.0, base_y)))
    g2.setAttributes(["GD-BPP-02", "Gardu Distribusi Batakan 02"])
    fitur_gardu.append(g2)
    pr_g.addFeatures(fitur_gardu)
    lyr_gardu.updateExtents()

    # 2. Layer JTR (Garis)
    lyr_jtr = QgsVectorLayer("LineString?crs=EPSG:32750", "JTR_Sintetis", "memory")
    pr_j = lyr_jtr.dataProvider()
    fields_j = QgsFields()
    fields_j.append(QgsField("ID_JTR", QVariant.String, len=50))
    fields_j.append(QgsField("PENYULANG", QVariant.String, len=50))
    pr_j.addAttributes(fields_j)
    lyr_jtr.updateFields()

    fitur_jtr = []
    j_id = 1

    # Segmen 1: Dekat Gardu 1 (jarak 4.0 m < 10.0 m toleransi) -> SNAPPING
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 4.0, base_y),
        QgsPointXY(base_x + 100.0, base_y),
    ]))
    f.setAttributes(["JTR-001", "Penyulang Manggar"])
    fitur_jtr.append(f)
    j_id += 1

    # Segmen 2: Terhubung normal ke ujung Segmen 1 di (base_x + 100, base_y) s.d. (base_x + 200, base_y)
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 100.0, base_y),
        QgsPointXY(base_x + 200.0, base_y),
    ]))
    f.setAttributes(["JTR-002", "Penyulang Manggar"])
    fitur_jtr.append(f)
    j_id += 1

    # Segmen 3: Dangling line dalam toleransi (berjarak 5.0 m dari Segmen 2 di base_x + 205, base_y)
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 205.0, base_y),
        QgsPointXY(base_x + 300.0, base_y),
    ]))
    f.setAttributes(["JTR-003", "Penyulang Manggar"])
    fitur_jtr.append(f)
    j_id += 1

    # Segmen 4: Tepat di batas toleransi snapping ke Gardu 2 (jarak 10.0 m)
    # Gardu 2 di (base_x + 500, base_y). Segmen mulai di (base_x + 490, base_y)
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 490.0, base_y),
        QgsPointXY(base_x + 400.0, base_y),
    ]))
    f.setAttributes(["JTR-004", "Penyulang Batakan"])
    fitur_jtr.append(f)
    j_id += 1

    # Segmen 5: Jauh dari Gardu (> 10.0 m, misal 40 m) -> UTUH
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 540.0, base_y),
        QgsPointXY(base_x + 650.0, base_y),
    ]))
    f.setAttributes(["JTR-005", "Penyulang Batakan"])
    fitur_jtr.append(f)
    j_id += 1

    # Segmen 6: Komponen Terisolasi (jauh dari Gardu manapun, y = base_y + 1000)
    f = QgsFeature(lyr_jtr.fields(), j_id)
    f.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 100.0, base_y + 30.0),
        QgsPointXY(base_x + 200.0, base_y + 30.0),
    ]))
    f.setAttributes(["JTR-ISOLASI", "Penyulang Terputus"])
    fitur_jtr.append(f)
    j_id += 1

    # Data anomali validator:
    # Segmen garis panjang 0
    f_nol = QgsFeature(lyr_jtr.fields(), j_id)
    f_nol.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 10.0, base_y + 10.0),
        QgsPointXY(base_x + 10.0, base_y + 10.0),
    ]))
    f_nol.setAttributes(["JTR-NOL", "Anomali"])
    fitur_jtr.append(f_nol)
    j_id += 1

    # Segmen duplikat (ID sama dan geometri sama)
    f_dup = QgsFeature(lyr_jtr.fields(), j_id)
    f_dup.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(base_x + 100.0, base_y),
        QgsPointXY(base_x + 200.0, base_y),
    ]))
    f_dup.setAttributes(["JTR-002", "Penyulang Manggar"])
    fitur_jtr.append(f_dup)
    j_id += 1

    # Segmen geometri null
    f_null = QgsFeature(lyr_jtr.fields(), j_id)
    f_null.setAttributes(["JTR-NULL", "Anomali"])
    fitur_jtr.append(f_null)
    j_id += 1

    pr_j.addFeatures(fitur_jtr)
    lyr_jtr.updateExtents()

    # 3. Layer APP (Titik kWh Meter)
    lyr_app = QgsVectorLayer("Point?crs=EPSG:32750", "APP_Sintetis", "memory")
    pr_a = lyr_app.dataProvider()
    fields_a = QgsFields()
    fields_a.append(QgsField("ID_PELANGGAN", QVariant.String, len=50))
    fields_a.append(QgsField("TARIF_DAYA", QVariant.String, len=50))
    pr_a.addAttributes(fields_a)
    lyr_app.updateFields()

    fitur_app = []
    a_id = 1

    # APP 1 & 2: Tepat pada garis Segmen 1 (jarak 0.1 m <= 0.5 m) -> status "ADA"
    f = QgsFeature(lyr_app.fields(), a_id)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 50.0, base_y + 0.1)))
    f.setAttributes(["541100000001", "R1/900VA"])
    fitur_app.append(f)
    a_id += 1

    f = QgsFeature(lyr_app.fields(), a_id)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 80.0, base_y - 0.2)))
    f.setAttributes(["541100000002", "R1/1300VA"])
    fitur_app.append(f)
    a_id += 1

    # APP 3: Anomali normal (jarak 8.0 m ke jaringan aktif Segmen 1) -> "TIDAK ADA" -> USULAN SLTR
    f = QgsFeature(lyr_app.fields(), a_id)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 60.0, base_y + 8.0)))
    f.setAttributes(["541100000003", "B1/2200VA"])
    fitur_app.append(f)
    a_id += 1

    # APP 4: Kasus Kritis: Lebih dekat ke komponen terisolasi (y=base_y+30)!
    # Lokasi: (base_x + 150, base_y + 26) -> jarak ke terisolasi 4.0 m, jarak ke aktif 26.0 m.
    # Karena jaringan aktif saja yang boleh jadi target, SLTR HARUS mengarah ke jaringan aktif (y=base_y)!
    f = QgsFeature(lyr_app.fields(), a_id)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 150.0, base_y + 26.0)))
    f.setAttributes(["541100000004", "R2/3500VA"])
    fitur_app.append(f)
    a_id += 1

    # APP 5: Sangat jauh (> 50.0 m usulan maks, misal y = base_y + 120.0 m)
    # Status "TIDAK ADA", TANPA USULAN
    f = QgsFeature(lyr_app.fields(), a_id)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(base_x + 50.0, base_y + 120.0)))
    f.setAttributes(["541100000005", "I1/6600VA"])
    fitur_app.append(f)
    a_id += 1

    # Anomali validator: APP dengan geometri null
    f_null_app = QgsFeature(lyr_app.fields(), a_id)
    f_null_app.setAttributes(["541100009999", "NullGeom"])
    fitur_app.append(f_null_app)
    a_id += 1

    pr_a.addFeatures(fitur_app)
    lyr_app.updateExtents()

    return {
        "gardu": lyr_gardu,
        "jtr": lyr_jtr,
        "sltr": None,
        "app": lyr_app,
    }
