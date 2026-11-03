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


def ambil_nilai_id(feature: Any, field_id: Optional[str] = None, jenis: Optional[str] = None) -> Any:
    """Mengambil nilai identifier fitur dengan fallback ke kandidat nama kolom PLN atau fid jika kosong.

    Args:
        feature: Fitur QgsFeature.
        field_id: Nama atribut identifier opsional.
        jenis: Kategori layer ('GARDU', 'JTR', 'SLTR', 'APP') untuk prioritas kolom ID yang tepat.

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

        jenis_upper = (jenis or "").upper()
        if jenis_upper == "APP":
            kandidat_pln = [
                "idpelanggan", "id_pelanggan", "idpel", "kwh_serialnum", "no_meter",
                "nomor_meter", "app_id", "id_app", "gid", "objectid", "id"
            ]
        elif jenis_upper == "JTR":
            kandidat_pln = [
                "id_jtr", "kode_jtr", "segment_id", "description", "assetnum",
                "kode_hantaran", "tujdnumber", "objectid", "id"
            ]
        elif jenis_upper == "SLTR":
            kandidat_pln = [
                "id_sltr", "id_stltr", "kode_sltr", "description", "assetnum",
                "idpelanggan", "kode_hantaran", "objectid", "id"
            ]
        elif jenis_upper == "GARDU":
            kandidat_pln = [
                "kode_gardu", "nama_gardu", "gardu_id", "id_gardu", "no_gardu",
                "location_gardu", "description_gardu", "assetnum", "location", "objectid", "id"
            ]
        elif jenis_upper == "TIANG":
            kandidat_pln = [
                "id_tiang", "kode_tiang", "no_tiang", "description", "assetnum",
                "tujdnumber", "location", "objectid", "id"
            ]
        else:
            # Auto-detect berdasarkan keberadaan kolom khas masing-masing layer
            if "idpelanggan" in f_names_lower and "kwh_serialnum" in f_names_lower:
                kandidat_pln = [
                    "idpelanggan", "id_pelanggan", "idpel", "kwh_serialnum",
                    "app_id", "id_app", "gid", "objectid", "id"
                ]
            elif "id_stltr" in f_names_lower or "deret_sr" in f_names_lower:
                kandidat_pln = [
                    "id_sltr", "id_stltr", "description", "assetnum",
                    "idpelanggan", "objectid", "id"
                ]
            elif "type_jtr" in f_names_lower or "ukuran_penghantar_tr" in f_names_lower:
                kandidat_pln = [
                    "id_jtr", "kode_jtr", "description", "assetnum",
                    "tujdnumber", "objectid", "id"
                ]
            else:
                kandidat_pln = [
                    "id_gardu", "id_jtr", "id_sltr", "id_app", "idpelanggan", "id_pelanggan",
                    "idpel", "no_meter", "nomor_meter", "app_id", "kode_jtr", "segment_id",
                    "id_stltr", "kode_sltr", "description", "assetnum",
                    "kode_gardu", "nama_gardu", "location_gardu", "gardu_id", "location_g",
                    "location", "no_gardu", "objectid", "id"
                ]

        for k in kandidat_pln:
            if k in f_names_lower:
                idx = f_names_lower.index(k)
                val = feature[f_names[idx]]
                if val is not None and str(val).strip() != "" and str(val).strip().upper() != "NULL":
                    return str(val).strip() if isinstance(val, str) else val

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
    tipe_diharapkan_point = jenis_upper in ("GARDU", "APP", "TIANG")
    tipe_diharapkan_line = jenis_upper in ("JTR", "SLTR")

    kumpulan_kunci_unik: Set[Tuple[Any, str]] = set()
    fitur_iter = layer.getFeatures() if hasattr(layer, "getFeatures") else []

    for f in fitur_iter:
        fid = f.id()
        val_id = ambil_nilai_id(f, field_id, jenis=jenis_upper)
        geom = f.geometry()

        if geom is None or geom.isNull() or geom.isEmpty():
            hasil.bermasalah.append({
                "fid": fid,
                "id_asal": val_id,
                "jenis": jenis,
                "alasan": "Geometri null atau kosong",
            })
            continue

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

        if hasattr(geom, "isGeosValid") and not geom.isGeosValid():
            hasil.bermasalah.append({
                "fid": fid,
                "id_asal": val_id,
                "jenis": jenis,
                "alasan": "Geometri tidak valid menurut aturan GEOS",
            })
            continue

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
