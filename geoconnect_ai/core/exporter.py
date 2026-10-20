"""Modul ekspor layer hasil analisis GeoConnect-AI ke berbagai format GIS.

Mendukung GeoPackage (.gpkg), ESRI Shapefile (.shp), GeoJSON (.geojson),
dan File Geodatabase (.gdb) dengan verifikasi runtime kemampuan tulis driver GDAL.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from osgeo import gdal
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
except ImportError:
    gdal = None
    QgsCoordinateReferenceSystem = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsVectorLayer = None


FORMAT_DRIVERS = {
    "GPKG": ("GPKG", ".gpkg"),
    "SHP": ("ESRI Shapefile", ".shp"),
    "GEOJSON": ("GeoJSON", ".geojson"),
    "GDB": ("OpenFileGDB", ".gdb"),
}


def cek_dukungan_tulis_gdb() -> Tuple[bool, str]:
    """Memeriksa apakah driver OpenFileGDB pada GDAL saat ini mendukung penulisan.

    Returns:
        Tuple[bool, str]: (Dukungan tulis True/False, Pesan status).
    """
    if gdal is None:
        return False, "GDAL tidak dapat dimuat."

    driver = gdal.GetDriverByName("OpenFileGDB")
    if driver is None:
        return (
            False,
            "Driver OpenFileGDB tidak ditemukan pada instalasi GDAL ini. "
            "Disarankan menggunakan format GeoPackage (.gpkg).",
        )

    # Cek kemampuan pembuatan dataset (DCAP_CREATE)
    dcap_create = driver.GetMetadataItem(gdal.DCAP_CREATE)
    if dcap_create == "YES":
        return True, "Driver OpenFileGDB mendukung operasi penulisan."

    return (
        False,
        "Driver OpenFileGDB pada versi GDAL ini bersifat read-only (butuh GDAL >= 3.6). "
        "Silakan pilih format GeoPackage (.gpkg) sebagai alternatif standar industri.",
    )


def ekspor_layer(
    layer: Any,
    output_path: str,
    format_nama: str = "GPKG",
    crs_target: Optional[Any] = None,
) -> Tuple[bool, str]:
    """Mengekspor layer QgsVectorLayer ke file pada format yang dipilih.

    Args:
        layer: Layer vektor sumber yang akan diekspor.
        output_path: Path file tujuan lengkap.
        format_nama: 'GPKG', 'SHP', 'GEOJSON', atau 'GDB'.
        crs_target: CRS target ekspor opsional (default CRS asli layer).

    Returns:
        Tuple[bool, str]: (Sukses True/False, Pesan status / error).
    """
    if layer is None or not hasattr(layer, "isValid") or not layer.isValid():
        return False, "Layer sumber tidak valid atau kosong."

    if QgsVectorFileWriter is None:
        return False, "QgsVectorFileWriter tidak tersedia."

    fmt_key = format_nama.upper()
    if fmt_key not in FORMAT_DRIVERS:
        return False, f"Format ekspor tidak dikenal: {format_nama}"

    driver_name, default_ext = FORMAT_DRIVERS[fmt_key]

    # Validasi khusus GDB
    if fmt_key == "GDB":
        bisa_gdb, pesan_gdb = cek_dukungan_tulis_gdb()
        if not bisa_gdb:
            return False, pesan_gdb

    # Pastikan folder tujuan ada
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    crs_ekspor = crs_target or layer.crs()
    transform_context = (
        QgsProject.instance().transformContext() if QgsProject else None
    )

    try:
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver_name
        options.fileEncoding = "UTF-8"
        if transform_context is not None:
            options.transformContext = transform_context

        # Untuk GPKG multi-layer atau single file
        if fmt_key == "GPKG" and os.path.exists(output_path):
            action_val = getattr(
                getattr(QgsVectorFileWriter, "ActionOnExistingFile", None),
                "CreateOrOverwriteLayer",
                1,
            )
            options.actionOnExistingFile = action_val
            options.layerName = layer.name()

        ret = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            output_path,
            transform_context,
            options,
        )

        err_code = ret[0] if isinstance(ret, (tuple, list)) else ret
        err_msg = ret[1] if isinstance(ret, (tuple, list)) and len(ret) > 1 else ""

        is_no_error = (err_code == 0) or (
            hasattr(QgsVectorFileWriter, "WriterError")
            and err_code == getattr(QgsVectorFileWriter.WriterError, "NoError", 0)
        )

        if is_no_error:
            return True, f"Berhasil mengekspor layer ke {output_path}"
        return False, f"Gagal mengekspor layer: {err_msg} (Kode: {err_code})"

    except Exception as e:
        # Fallback kompatibilitas QGIS versi lama
        try:
            options_v2 = QgsVectorFileWriter.SaveVectorOptions()
            options_v2.driverName = driver_name
            options_v2.fileEncoding = "UTF-8"
            ret_v2 = QgsVectorFileWriter.writeAsVectorFormatV2(
                layer,
                output_path,
                transform_context,
                options_v2,
            )
            err_code_v2 = ret_v2[0] if isinstance(ret_v2, (tuple, list)) else ret_v2
            if err_code_v2 == 0:
                return True, f"Berhasil mengekspor layer ke {output_path}"
            return False, f"Gagal mengekspor: Kode error {err_code_v2}"
        except Exception as e_fallback:
            return False, f"Pengecualian saat mengekspor layer: {str(e_fallback)}"


def ekspor_semua_hasil(
    hasil_pipeline: Any,
    folder_atau_file: str,
    format_nama: str = "GPKG",
    crs_target: Optional[Any] = None,
) -> Dict[str, Tuple[bool, str]]:
    """Mengekspor seluruh layer hasil analisis (4 layer) ke lokasi target.

    Untuk GPKG atau GDB, keempat layer dapat dimasukkan ke satu kontainer database.
    Untuk Shapefile atau GeoJSON, tiap layer ditulis ke file terpisah di dalam folder.

    Returns:
        Dict[str, Tuple[bool, str]]: Hasil ekspor per layer.
    """
    hasil_ekspor = {}
    daftar_layer = [
        ("JTR_Snapping", hasil_pipeline.layer_jtr_snapped),
        ("Penyambungan_Dangling", hasil_pipeline.layer_dangling),
        ("APP_Anomali", hasil_pipeline.layer_app_anomali),
        ("SLTR_Usulan", hasil_pipeline.layer_sltr_usulan),
    ]

    fmt_key = format_nama.upper()
    _, ext = FORMAT_DRIVERS.get(fmt_key, ("GPKG", ".gpkg"))

    # Jika kontainer GPKG tunggal
    if fmt_key == "GPKG" and folder_atau_file.lower().endswith(".gpkg"):
        gpkg_path = folder_atau_file
        for nama, lyr in daftar_layer:
            if lyr is not None:
                sukses, msg = ekspor_layer(lyr, gpkg_path, "GPKG", crs_target)
                hasil_ekspor[nama] = (sukses, msg)
        return hasil_ekspor

    # Jika kontainer GDB tunggal
    if fmt_key == "GDB" and folder_atau_file.lower().endswith(".gdb"):
        gdb_path = folder_atau_file
        for nama, lyr in daftar_layer:
            if lyr is not None:
                sukses, msg = ekspor_layer(lyr, gdb_path, "GDB", crs_target)
                hasil_ekspor[nama] = (sukses, msg)
        return hasil_ekspor

    # Folder tujuan untuk file individual
    folder_tujuan = folder_atau_file
    os.makedirs(folder_tujuan, exist_ok=True)

    for nama, lyr in daftar_layer:
        if lyr is not None:
            file_path = os.path.join(folder_tujuan, f"{nama}{ext}")
            sukses, msg = ekspor_layer(lyr, file_path, fmt_key, crs_target)
            hasil_ekspor[nama] = (sukses, msg)

    return hasil_ekspor
