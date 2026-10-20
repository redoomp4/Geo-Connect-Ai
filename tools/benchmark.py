"""Skrip benchmark performa GeoConnect-AI untuk skala 1k, 5k, dan 10k APP.

Menguji kecepatan pemrosesan topologi pada data besar:
- 1k: 1.000 APP, 500 segmen JTR, 5 Gardu
- 5k: 5.000 APP, 2.500 segmen JTR, 20 Gardu
- 10k: 10.000 APP, 5.000 segmen JTR, 40 Gardu
Target: 10.000 APP + 5.000 segmen JTR selesai dalam <= 60 detik.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from geoconnect_ai.core.config import PipelineConfig, ToleransiConfig
from geoconnect_ai.core.pipeline import jalankan_pipeline


def buat_jaringan_skala(jumlah_app: int, jumlah_jtr: int, jumlah_gardu: int):
    """Membuat jaringan distribusi sintetis realistis dalam skala besar."""
    base_x = 480000.0
    base_y = 9860000.0

    # 1. Layer Gardu
    lyr_g = QgsVectorLayer("Point?crs=EPSG:32750", "Gardu_Bench", "memory")
    pr_g = lyr_g.dataProvider()
    pr_g.addAttributes([QgsField("ID", QVariant.String, len=50)])
    lyr_g.updateFields()

    fitur_g = []
    gardu_coords = []
    for gi in range(jumlah_gardu):
        gx = base_x + (gi % 10) * 1000.0
        gy = base_y + (gi // 10) * 1000.0
        gardu_coords.append((gx, gy))

        f = QgsFeature(lyr_g.fields(), gi + 1)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(gx, gy)))
        f.setAttributes([f"G-{gi+1:03d}"])
        fitur_g.append(f)
    pr_g.addFeatures(fitur_g)
    lyr_g.updateExtents()

    # 2. Layer JTR (Pohon jaringan bercabang dari gardu)
    lyr_j = QgsVectorLayer("LineString?crs=EPSG:32750", "JTR_Bench", "memory")
    pr_j = lyr_j.dataProvider()
    pr_j.addAttributes([QgsField("ID", QVariant.String, len=50)])
    lyr_j.updateFields()

    fitur_j = []
    segmen_per_gardu = max(1, jumlah_jtr // jumlah_gardu)
    j_idx = 1
    endpoints = []

    for gi, (gx, gy) in enumerate(gardu_coords):
        curr_x, curr_y = gx, gy
        for si in range(segmen_per_gardu):
            dx = (si % 5) * 60.0
            dy = (si // 5) * 60.0
            next_x = gx + dx + 50.0
            next_y = gy + dy

            # Sengaja beri gap kecil (3.0 m) pada segmen awal untuk memicu snapping
            start_x = curr_x + (3.0 if si == 0 else 0.0)
            start_y = curr_y

            f = QgsFeature(lyr_j.fields(), j_idx)
            f.setGeometry(QgsGeometry.fromPolylineXY([
                QgsPointXY(start_x, start_y),
                QgsPointXY(next_x, next_y),
            ]))
            f.setAttributes([f"JTR-{j_idx:05d}"])
            fitur_j.append(f)
            endpoints.append((next_x, next_y))
            curr_x, curr_y = next_x, next_y
            j_idx += 1

    pr_j.addFeatures(fitur_j)
    lyr_j.updateExtents()

    # 3. Layer APP (Tersebar di sepanjang koridor segmen garis JTR)
    lyr_a = QgsVectorLayer("Point?crs=EPSG:32750", "APP_Bench", "memory")
    pr_a = lyr_a.dataProvider()
    pr_a.addAttributes([QgsField("ID", QVariant.String, len=50)])
    lyr_a.updateFields()

    fitur_a = []
    for ai in range(jumlah_app):
        # Pilih endpoint acak
        ep_x, ep_y = endpoints[ai % len(endpoints)]
        # Sebagian besar (80%) berada dalam jarak cover (0.2 m), 20% anomali (5.0 m s.d. 25.0 m)
        if ai % 5 != 0:
            offset_y = 0.2
        else:
            offset_y = 12.0

        f = QgsFeature(lyr_a.fields(), ai + 1)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(ep_x + 5.0, ep_y + offset_y)))
        f.setAttributes([f"APP-{ai+1:06d}"])
        fitur_a.append(f)

    pr_a.addFeatures(fitur_a)
    lyr_a.updateExtents()

    return lyr_g, lyr_j, lyr_a


def uji_skenario(label: str, n_app: int, n_jtr: int, n_gardu: int):
    """Menjalankan pengujian benchmark untuk satu skenario skala data."""
    print(f"\n{'='*65}")
    print(f" MENJALANKAN BENCHMARK: {label}")
    print(f" Parameter: {n_app:,} APP | {n_jtr:,} JTR | {n_gardu} Gardu")
    print(f"{'='*65}")

    t0_gen = time.time()
    lyr_g, lyr_j, lyr_a = buat_jaringan_skala(n_app, n_jtr, n_gardu)
    waktu_gen = time.time() - t0_gen
    print(f"Data sintetis dibuat dalam {waktu_gen:.2f} detik.")

    cfg = PipelineConfig(
        layer_gardu=lyr_g,
        layer_jtr=lyr_j,
        layer_app=lyr_a,
        field_id_gardu="ID",
        field_id_jtr="ID",
        field_id_app="ID",
        toleransi=ToleransiConfig(
            jtr_gardu_m=10.0,
            dangling_m=8.0,
            app_cover_m=0.5,
            app_usulan_maks_m=50.0,
        ),
        proses_snapping=True,
        proses_dangling=True,
        proses_anomali_app=True,
        proses_styling=False, # Nonaktifkan rendering UI untuk isolasi performa algoritma
        proses_layer_group=False,
    )

    t0_pipe = time.time()
    hasil = jalankan_pipeline(cfg)
    durasi = time.time() - t0_pipe

    r = hasil.ringkasan or {}
    print(f"Status           : {'SUKSES' if hasil.sukses else 'GAGAL'}")
    print(f"Waktu Pipeline   : {durasi:.2f} detik")
    print(f"JTR Snapped      : {r.get('jtr_snapped', 0):,} ujung")
    print(f"Dangling Sambung : {r.get('dangling_tersambung', 0):,} garis")
    print(f"APP ADA          : {r.get('app_ada', 0):,}")
    print(f"APP Anomali      : {r.get('app_tidak_ada', 0):,}")
    print(f"SLTR Usulan      : {r.get('sltr_usulan_dibuat', 0):,}")

    return {
        "skenario": label,
        "app": n_app,
        "jtr": n_jtr,
        "gardu": n_gardu,
        "durasi": durasi,
        "sukses": hasil.sukses,
    }


def main():
    app = QgsApplication.instance()
    owns_app = False
    if app is None:
        app = QgsApplication([], False)
        app.initQgis()
        owns_app = True

    try:
        skenario_list = [
            ("Skenario 1K", 1000, 500, 5),
            ("Skenario 5K", 5000, 2500, 20),
            ("Skenario 10K", 10000, 5000, 40),
        ]

        hasil_semua = []
        for label, na, nj, ng in skenario_list:
            res = uji_skenario(label, na, nj, ng)
            hasil_semua.append(res)

        print(f"\n{'='*75}")
        print(" TABEL RINGKASAN HASIL BENCHMARK PERFORMA AKTUAL")
        print(f"{'='*75}")
        print(f"{'Skenario':<15} | {'Jumlah APP':<12} | {'Jumlah JTR':<12} | {'Durasi (detik)':<15} | {'Status Target (<60s)':<15}")
        print(f"{'-'*75}")
        for h in hasil_semua:
            memenuhi = "MEMENUHI" if h["durasi"] <= 60.0 else "MELEBIHI"
            print(f"{h['skenario']:<15} | {h['app']:<12,} | {h['jtr']:<12,} | {h['durasi']:<15.2f} | {memenuhi:<15}")
        print(f"{'='*75}\n")

    finally:
        if owns_app:
            app.exitQgis()


if __name__ == "__main__":
    main()
