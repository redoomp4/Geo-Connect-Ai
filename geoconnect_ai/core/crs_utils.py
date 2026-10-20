"""Utilitas penentuan dan transformasi CRS (Sistem Referensi Koordinat).

Memastikan seluruh analisis metrik (snapping, toleransi dangling, jarak APP)
dilakukan dalam sistem koordinat terproyeksi berbasis meter (UTM otomatis).
"""

import math
from typing import Optional

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRectangle,
    )
except ImportError:
    # Fallback untuk pengujian murni tanpa QGIS
    QgsCoordinateReferenceSystem = None
    QgsCoordinateTransform = None
    QgsProject = None
    QgsRectangle = None


def hitung_zona_utm(lon: float) -> int:
    """Menghitung nomor zona UTM (1 - 60) berdasarkan derajat bujur (longitude).

    Args:
        lon (float): Derajat bujur (-180.0 s.d. 180.0).

    Returns:
        int: Nomor zona UTM (1 - 60).

    Example:
        >>> hitung_zona_utm(116.8) # Balikpapan
        50
    """
    zona = int(math.floor((lon + 180.0) / 6.0)) + 1
    if zona < 1:
        return 1
    if zona > 60:
        return 60
    return zona


def hitung_epsg_utm(lon: float, lat: float) -> int:
    """Menghitung kode EPSG UTM WGS 84 berdasarkan bujur dan lintang.

    Args:
        lon (float): Derajat bujur (-180.0 s.d. 180.0).
        lat (float): Derajat lintang (-90.0 s.d. 90.0).

    Returns:
        int: Kode EPSG (326xx untuk Lintang Utara, 327xx untuk Lintang Selatan).

    Example:
        >>> hitung_epsg_utm(116.82, -1.26) # Balikpapan, Kaltim
        32750
    """
    zona = hitung_zona_utm(lon)
    return 32600 + zona if lat >= 0.0 else 32700 + zona


def tentukan_crs_kerja(
    layer_jtr=None,
    layer_gardu=None,
    layer_app=None,
    override_crs_auth_id: Optional[str] = None,
):
    """Menentukan CRS kerja berbasis meter untuk pipeline analisis.

    Jika override_crs_auth_id diberikan, gunakan CRS tersebut.
    Jika layer memiliki CRS geografis (derajat, e.g. EPSG:4326),
    otomatis proyeksikan ke zona UTM yang sesuai.
    Jika sudah terproyeksi, pertahankan CRS layer JTR.

    Args:
        layer_jtr: Layer garis JTR (utama).
        layer_gardu: Layer titik Gardu (opsional fallback).
        layer_app: Layer titik APP (opsional fallback).
        override_crs_auth_id: Kode auth CRS manual (mis. 'EPSG:32750').

    Returns:
        QgsCoordinateReferenceSystem: CRS kerja yang valid.
    """
    if QgsCoordinateReferenceSystem is None:
        raise RuntimeError("QGIS core library tidak tersedia.")

    if override_crs_auth_id:
        crs_override = QgsCoordinateReferenceSystem(override_crs_auth_id)
        if crs_override.isValid():
            return crs_override

    # Pilih layer referensi acuan
    layer_ref = layer_jtr or layer_gardu or layer_app
    if layer_ref is None or not hasattr(layer_ref, "crs"):
        # Default fallback Balikpapan UTM 50S
        return QgsCoordinateReferenceSystem("EPSG:32750")

    crs_sumber = layer_ref.crs()
    if not crs_sumber.isValid():
        return QgsCoordinateReferenceSystem("EPSG:32750")

    # Jika sudah terproyeksi (bukan derajat/geografis), gunakan langsung
    if not crs_sumber.isGeographic():
        return crs_sumber

    # Hitung titik tengah extent layer untuk mencari zona UTM
    extent = layer_ref.extent()
    if extent.isNull() or extent.isEmpty():
        return QgsCoordinateReferenceSystem("EPSG:32750")

    lon_tengah = (extent.xMinimum() + extent.xMaximum()) / 2.0
    lat_tengah = (extent.yMinimum() + extent.yMaximum()) / 2.0
    epsg_utm = hitung_epsg_utm(lon_tengah, lat_tengah)

    crs_target = QgsCoordinateReferenceSystem(f"EPSG:{epsg_utm}")
    if crs_target.isValid():
        return crs_target

    return crs_sumber


def buat_transformasi(crs_sumber, crs_target, transform_context=None):
    """Membuat objek QgsCoordinateTransform jika kedua CRS berbeda.

    Args:
        crs_sumber: CRS asal data.
        crs_target: CRS target operasi.
        transform_context: Konteks transformasi proyek QGIS.

    Returns:
        Optional[QgsCoordinateTransform]: Objek transform atau None jika sama.
    """
    if QgsCoordinateTransform is None:
        return None

    if crs_sumber == crs_target or crs_sumber.authid() == crs_target.authid():
        return None

    ctx = transform_context or (QgsProject.instance().transformContext() if QgsProject else None)
    if ctx is not None:
        return QgsCoordinateTransform(crs_sumber, crs_target, ctx)
    return QgsCoordinateTransform(crs_sumber, crs_target)
