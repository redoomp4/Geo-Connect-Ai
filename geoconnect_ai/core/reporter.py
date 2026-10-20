"""Modul pembuatan laporan analisis dan ringkasan eksekusi GeoConnect-AI.

Menyusun ringkasan metrik topologi dan mengekspor laporan tabel ke format Excel (.xlsx)
menggunakan driver bawaan QGIS OGR XLSX, dengan fallback otomatis ke format CSV.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from osgeo import gdal
    from qgis.core import (
        QgsFeature,
        QgsField,
        QgsFields,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError:
    gdal = None
    QgsFeature = None
    QgsField = None
    QgsFields = None
    QgsProject = None
    QgsVectorFileWriter = None
    QgsVectorLayer = None
    QVariant = None


def format_waktu(detik: float) -> str:
    """Memformat durasi detik ke format teks manusia."""
    if detik < 60:
        return f"{detik:.2f} detik"
    menit = int(detik // 60)
    sisa = detik % 60
    return f"{menit} menit {sisa:.1f} detik"


def buat_ringkasan_teks(hasil_pipeline: Any) -> str:
    """Membuat laporan ringkasan bertarget teks monospace untuk log proses UI.

    Args:
        hasil_pipeline: Objek HasilPipeline.

    Returns:
        str: Ringkasan terformat.
    """
    r = hasil_pipeline.ringkasan or {}
    waktu_str = format_waktu(hasil_pipeline.waktu_eksekusi_detik)

    garis = "=" * 65
    pemisah = "-" * 65

    lines = [
        garis,
        " RINGKASAN HASIL OTOMATISASI TOPOLOGI GEOCONNECT-AI ",
        " PT PLN (PERSERO) UID KALIMANTAN TIMUR DAN UTARA ",
        garis,
        f" Status Eksekusi       : {'SUKSES' if hasil_pipeline.sukses else 'GAGAL / SELESAI SEBAGIAN'}",
        f" Total Waktu Proses    : {waktu_str}",
        pemisah,
        " [1] VALIDASI DATA MASUKAN",
        f"   - Total Data Diproses   : {r.get('total_data_diproses', 0):,}",
        f"   - Data Valid            : {r.get('total_data_valid', 0):,}",
        f"   - Data Bermasalah       : {r.get('total_data_bermasalah', 0):,} (dikeluarkan dari proses)",
        pemisah,
        " [2] AUTO-SNAPPING JTR KE GARDU",
        f"   - Ujung JTR Ter-snap    : {r.get('jtr_snapped', 0):,}",
        f"   - Segmen JTR Utuh       : {r.get('jtr_utuh', 0):,}",
        pemisah,
        " [3] DETEKSI & PENYAMBUNGAN DANGLING LINE",
        f"   - Dangling Terdeteksi   : {r.get('dangling_terdeteksi', 0):,}",
        f"   - Dangling Tersambung   : {r.get('dangling_tersambung', 0):,} (garis penghubung diusulkan)",
        f"   - Dangling Tak Sambung  : {r.get('dangling_tak_tersambung', 0):,}",
        pemisah,
        " [4] ANALISIS KETERHUBUNGAN APP (KWH METER)",
        f"   - Total APP Dianalisis  : {r.get('app_total', 0):,}",
        f"   - APP Normal (ADA)      : {r.get('app_ada', 0):,} (titik hijau)",
        f"   - APP Anomali (TIDAK)   : {r.get('app_tidak_ada', 0):,} (titik merah)",
        pemisah,
        " [5] USULAN PENYAMBUNGAN SLTR",
        f"   - SLTR Usulan Dibuat    : {r.get('sltr_usulan_dibuat', 0):,} (garis oranye)",
        f"   - Anomali Tanpa Usulan  : {r.get('app_tanpa_usulan', 0):,} (jarak > batas maks)",
        garis,
        " Catatan: Seluruh hasil tersimpan di memory layer & grup hasil.",
        "          Data layer sumber asli 100% utuh tanpa perubahan.",
        garis,
    ]
    return "\n".join(lines)


def cek_driver_xlsx() -> bool:
    """Memeriksa apakah driver XLSX GDAL tersedia untuk penulisan."""
    if gdal is None:
        return False
    driver = gdal.GetDriverByName("XLSX")
    if driver is None:
        return False
    return driver.GetMetadataItem(gdal.DCAP_CREATE) == "YES"


def buat_laporan_excel(
    hasil_pipeline: Any,
    output_path: str,
) -> Tuple[bool, str]:
    """Mengekspor laporan analisis lengkap ke format Excel (.xlsx).

    Jika driver XLSX tidak didukung oleh lingkungan runtime GDAL,
    otomatis beralih (fallback) ke berkas format CSV standar.

    Args:
        hasil_pipeline: Objek HasilPipeline.
        output_path: Path tujuan file laporan (.xlsx atau .csv).

    Returns:
        Tuple[bool, str]: (Status sukses True/False, Pesan keterangan).
    """
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    r = hasil_pipeline.ringkasan or {}
    baris_ringkasan = [
        ("Status Eksekusi", "SUKSES" if hasil_pipeline.sukses else "GAGAL", ""),
        ("Waktu Eksekusi", f"{hasil_pipeline.waktu_eksekusi_detik:.2f}", "detik"),
        ("Total Data Diproses", str(r.get("total_data_diproses", 0)), "fitur"),
        ("Total Data Valid", str(r.get("total_data_valid", 0)), "fitur"),
        ("Total Data Bermasalah", str(r.get("total_data_bermasalah", 0)), "fitur"),
        ("JTR Snapped ke Gardu", str(r.get("jtr_snapped", 0)), "ujung"),
        ("JTR Utuh", str(r.get("jtr_utuh", 0)), "segmen"),
        ("Dangling Terdeteksi", str(r.get("dangling_terdeteksi", 0)), "ujung"),
        ("Dangling Tersambung", str(r.get("dangling_tersambung", 0)), "garis penghubung"),
        ("Dangling Tak Tersambung", str(r.get("dangling_tak_tersambung", 0)), "ujung"),
        ("Total APP", str(r.get("app_total", 0)), "titik"),
        ("APP Tersambung (ADA)", str(r.get("app_ada", 0)), "titik"),
        ("APP Anomali (TIDAK ADA)", str(r.get("app_tidak_ada", 0)), "titik"),
        ("SLTR Usulan Dibuat", str(r.get("sltr_usulan_dibuat", 0)), "garis usulan"),
        ("APP Anomali Tanpa Usulan", str(r.get("app_tanpa_usulan", 0)), "titik"),
    ]

    bisa_xlsx = cek_driver_xlsx()

    if bisa_xlsx and output_path.lower().endswith(".xlsx"):
        # Tulis ke XLSX via QgsVectorFileWriter OGR
        try:
            layer = QgsVectorLayer("None", "Ringkasan_GeoConnect", "memory")
            pr = layer.dataProvider()
            fields = QgsFields()
            fields.append(QgsField("METRIK", QVariant.String if QVariant else 10, len=100))
            fields.append(QgsField("NILAI", QVariant.String if QVariant else 10, len=100))
            fields.append(QgsField("SATUAN", QVariant.String if QVariant else 10, len=50))
            pr.addAttributes(fields)
            layer.updateFields()

            fitur_list = []
            for m, n, s in baris_ringkasan:
                f = QgsFeature(layer.fields())
                f.setAttributes([m, n, s])
                fitur_list.append(f)
            pr.addFeatures(fitur_list)

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "XLSX"
            options.fileEncoding = "UTF-8"
            t_ctx = QgsProject.instance().transformContext() if QgsProject else None

            ret = QgsVectorFileWriter.writeAsVectorFormatV3(layer, output_path, t_ctx, options)
            if isinstance(ret, tuple) and ret[0] == 0:
                return True, f"Laporan Excel berhasil ditulis ke: {output_path}"
        except Exception:
            pass # Fallback ke CSV jika terjadi kendala

    # Fallback ke CSV murni Python standard library
    csv_path = (
        output_path
        if output_path.lower().endswith(".csv")
        else os.path.splitext(output_path)[0] + ".csv"
    )

    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f_csv:
            writer = csv.writer(f_csv)
            writer.writerow(["METRIK", "NILAI", "SATUAN"])
            for row in baris_ringkasan:
                writer.writerow(list(row))

            # Tambahkan bagian data bermasalah jika ada
            if hasil_pipeline.data_bermasalah:
                writer.writerow([])
                writer.writerow(["DATA BERMASALAH TERSARING"])
                writer.writerow(["FID", "ID ASAL", "JENIS LAYER", "ALASAN"])
                for b in hasil_pipeline.data_bermasalah:
                    writer.writerow([
                        b.get("fid", ""),
                        b.get("id_asal", ""),
                        b.get("jenis", ""),
                        b.get("alasan", ""),
                    ])

        pesan_ret = f"Laporan CSV berhasil ditulis ke: {csv_path}"
        if not bisa_xlsx and output_path.lower().endswith(".xlsx"):
            pesan_ret += " (Driver XLSX tidak tersedia di GDAL, dialihkan otomatis ke format CSV)"
        return True, pesan_ret

    except Exception as e:
        return False, f"Gagal menulis file laporan: {str(e)}"
