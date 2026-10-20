"""GeoConnect-AI QGIS Plugin.

Plugin non-destruktif untuk otomatisasi snapping JTR ke Gardu,
penyambungan dangling line, deteksi anomali APP, dan usulan SLTR
untuk persiapan simulasi aliran daya PSS SINCAL.

Dikembangkan untuk PT PLN (Persero) UID Kalimantan Timur dan Utara.
"""


def classFactory(iface):
    """Fungsi factory yang dipanggil oleh QGIS saat plugin dimuat.

    Args:
        iface (QgisInterface): Antarmuka utama QGIS.

    Returns:
        GeoConnectAI: Objek instance plugin.
    """
    from .geoconnect_ai import GeoConnectAI
    return GeoConnectAI(iface)
