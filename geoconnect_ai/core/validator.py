"""Modul validasi data input topologi jaringan listrik.

Memeriksa anomali geometri (null, kosong, tidak valid, panjang nol, tipe tidak sesuai)
dan duplikasi tanpa pernah mengubah data pada layer sumber.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from .config import HasilValidasi

try:
    from qgis.core import (
        QgsFeature,
        QgsGeometry,
        QgsVectorLayer,
        QgsWkbTypes,
    )
except ImportError:
    QgsFeature = None
    QgsGeometry = None
    QgsVectorLayer = None
    QgsWkbTypes = None


def ambil_nilai_id(feature: Any, field_id: Optional[str] = None) -> Any:
    """Mengambil nilai identifier fitur dengan fallback ke kandidat nama kolom PLN atau fid jika kosong.

    Args:
        feature: Fitur QgsFeature.
        field_id: Nama atribut identifier opsional.

    Returns:
        Nilai ID (string/int) atau fid jika field_id tidak valid.
    """
    if field_id and hasattr(feature, "fields") and feature.fields().indexOf(field_id) != -1:
        val = feature[field_id]
        if val is not None and str(val).strip() != "":
            return val

    # Kandidat field otomatis berdasarkan pola atribut data PLN (Gardu, APP, JTR, SLTR)
    if hasattr(feature, "fields"):
        f_names = [f.name() for f in feature.fields()]
        f_names_lower = [n.lower() for n in f_names]
        kandidat_pln = [
            "kode_gardu", "location_gardu", "gardu_id", "location_g", "location", "id_gardu", "no_gardu",
            "idpel", "id_pelanggan", "no_meter", "nomor_meter", "app_id", "id_app", "id_stltr",
            "id_jtr", "kode_jtr", "segment_id", "id_sltr", "kode_sltr"
        ]
        for k in kandidat_pln:
            if k in f_names_lower:
                idx = f_names_lower.index(k)
                val = feature[f_names[idx]]
                if val is not None and str(val).strip() != "":
                    return val

    return feature.id() if hasattr(feature, "id") else None


def validasi_data(
    layer: Any,
    jenis: str,
    field_id: Optional[str] = None,
) -> HasilValidasi:
    """Memvalidasi layer vektor input dan menyaring data bermasalah.

    Args:
        layer: Layer vektor QGIS (QgsVectorLayer).
        jenis: Kategori layer ('GARDU', 'JTR', 'SLTR', 'APP').
        field_id: Nama kolom ID opsional pada layer.

    Returns:
        HasilValidasi: Berisi list fitur valid dan list dict informasi data bermasalah.
    """
    hasil = HasilValidasi()
    if layer is None:
        hasil.bermasalah.append({
            "fid": None,
            "id_asal": None,
            "jenis": jenis,
            "alasan": "Layer tidak diberikan (None)",
        })
        return hasil

    if hasattr(layer, "isValid") and not layer.isValid():
        hasil.bermasalah.append({
            "fid": None,
            "id_asal": None,
            "jenis": jenis,
            "alasan": "Layer tidak valid atau tidak dapat diakses",
        })
        return hasil

    jenis_upper = jenis.upper()
    tipe_diharapkan_point = jenis_upper in ("GARDU", "APP")
    tipe_diharapkan_line = jenis_upper in ("JTR", "SLTR")

    kumpulan_kunci_unik: Set[Tuple[Any, str]] = set()

    # Iterasi fitur pada layer sumber (tanpa modifikasi)
    fitur_iter = layer.getFeatures() if hasattr(layer, "getFeatures") else []

    for f in fitur_iter:
        fid = f.id()
        val_id = ambil_nilai_id(f, field_id)
        geom = f.geometry()

        # 1. Periksa geometri null atau kosong
        if geom is None or geom.isNull() or geom.isEmpty():
            hasil.bermasalah.append({
                "fid": fid,
                "id_asal": val_id,
                "jenis": jenis,
                "alasan": "Geometri null atau kosong",
            })
            continue

        # 2. Periksa kesesuaian tipe geometri
        if QgsWkbTypes is not None:
            tipe_geom = geom.type()
            if tipe_diharapkan_point and tipe_geom != QgsWkbTypes.PointGeometry:
                hasil.bermasalah.append({
                    "fid": fid,
                    "id_asal": val_id,
                    "jenis": jenis,
                    "alasan": f"Tipe geometri bukan titik (tipe WKB: {geom.wkbType()})",
                })
                continue

            if tipe_diharapkan_line and tipe_geom != QgsWkbTypes.LineGeometry:
                hasil.bermasalah.append({
                    "fid": fid,
                    "id_asal": val_id,
                    "jenis": jenis,
                    "alasan": f"Tipe geometri bukan garis (tipe WKB: {geom.wkbType()})",
                })
                continue

        # 3. Periksa kevalidan geometri (GEOS)
        if hasattr(geom, "isGeosValid") and not geom.isGeosValid():
            hasil.bermasalah.append({
                "fid": fid,
                "id_asal": val_id,
                "jenis": jenis,
                "alasan": "Geometri tidak valid menurut aturan GEOS",
            })
            continue

        # 4. Periksa panjang garis nol untuk layer garis
        if tipe_diharapkan_line and hasattr(geom, "length"):
            panjang = geom.length()
            if panjang <= 1e-7:
                hasil.bermasalah.append({
                    "fid": fid,
                    "id_asal": val_id,
                    "jenis": jenis,
                    "alasan": f"Garis berpanjang nol atau mendekati nol ({panjang:.6f} m)",
                })
                continue

        # 5. Periksa duplikat (ID sama + geometri sama)
        wkt_singkat = geom.asWkt(4) if hasattr(geom, "asWkt") else ""
        kunci = (val_id, wkt_singkat)
        if kunci in kumpulan_kunci_unik:
            hasil.bermasalah.append({
                "fid": fid,
                "id_asal": val_id,
                "jenis": jenis,
                "alasan": "Duplikat (ID dan geometri identik dengan fitur sebelumnya)",
            })
            continue

        kumpulan_kunci_unik.add(kunci)
        hasil.valid.append(f)

    return hasil
