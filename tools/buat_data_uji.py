"""Skrip pembantu untuk membuat berkas GeoPackage data uji sintetis (Balikpapan).

Menghasilkan berkas `data_uji_balikpapan.gpkg` yang memuat layer Gardu, JTR, dan APP
dengan berbagai skenario kerusakan jaringan untuk pengujian fungsional dan demonstrasi.
"""

import os
import sys

# Tambahkan direktori root proyek ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qgis.core import QgsApplication
from geoconnect_ai.core.exporter import ekspor_layer
from tests.data_sintetis import buat_kumpulan_data_sintetis_balikpapan


def main():
    app = QgsApplication.instance()
    owns_app = False
    if app is None:
        app = QgsApplication([], False)
        app.initQgis()
        owns_app = True

    try:
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_gpkg = os.path.join(output_dir, "data_uji_balikpapan.gpkg")

        if os.path.exists(output_gpkg):
            os.remove(output_gpkg)

        print("Menghasilkan data sintetis jaringan Balikpapan (EPSG:32750)...")
        data = buat_kumpulan_data_sintetis_balikpapan()

        daftar_layer = [
            ("Gardu_Sintetis", data["gardu"]),
            ("JTR_Sintetis", data["jtr"]),
            ("APP_Sintetis", data["app"]),
        ]

        print(f"Menulis layer ke GeoPackage: {output_gpkg}")
        for nama, lyr in daftar_layer:
            if lyr is not None:
                sukses, pesan = ekspor_layer(lyr, output_gpkg, "GPKG")
                status_str = "BERHASIL" if sukses else "GAGAL"
                print(f"  [{status_str}] Layer '{nama}': {pesan}")

        print("\nSelesai! GeoPackage siap digunakan untuk pengujian:")
        print(f"Path: {output_gpkg}")

    finally:
        if owns_app:
            app.exitQgis()


if __name__ == "__main__":
    main()
