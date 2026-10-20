"""Test integrasi QGIS untuk GeoConnect-AI.

Membutuhkan runtime PyQGIS (dijalankan via tools/run_qgis.bat).
Menguji komponen spasial: snapping, nearest neighbor, dangling, anomali APP,
keutuhan data asli, styling, layer group, ekspor, pembuatan laporan,
serta orkestrasi pipeline dan UI dialog.
"""

import os
import shutil
import tempfile
import unittest

from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from geoconnect_ai.core.anomali_app import deteksi_anomali_app
from geoconnect_ai.core.config import HasilPipeline, PipelineConfig, ToleransiConfig
from geoconnect_ai.core.dangling import deteksi_dangling, sambung_dangling
from geoconnect_ai.core.exporter import cek_dukungan_tulis_gdb, ekspor_layer
from geoconnect_ai.core.layer_group import kelompokkan_layer
from geoconnect_ai.core.nearest import cari_terdekat
from geoconnect_ai.core.pipeline import jalankan_pipeline
from geoconnect_ai.core.reporter import buat_laporan_excel, buat_ringkasan_teks
from geoconnect_ai.core.snapping import auto_snap_jtr_ke_gardu
from geoconnect_ai.core.styler import (
    terapkan_style_app_anomali,
    terapkan_style_dangling,
    terapkan_style_jtr_snapping,
    terapkan_style_sltr_usulan,
)
from geoconnect_ai.core.usulan import buat_sltr_usulan
from geoconnect_ai.ui.dialog import GeoConnectAIDialog


# Inisialisasi QgsApplication minimal untuk testing non-GUI
app = QgsApplication.instance()
if app is None:
    app = QgsApplication([], False)
    app.initQgis()


def buat_fitur_titik(fid: int, x: float, y: float, nama_id: str) -> QgsFeature:
    """Helper membuat QgsFeature titik dengan atribut ID."""
    fields = QgsFields()
    fields.append(QgsField("ID", QVariant.String, len=50))
    f = QgsFeature(fields, fid)
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
    f.setAttributes([nama_id])
    return f


def buat_fitur_garis(fid: int, pts: list, nama_id: str) -> QgsFeature:
    """Helper membuat QgsFeature garis dengan atribut ID."""
    fields = QgsFields()
    fields.append(QgsField("ID", QVariant.String, len=50))
    f = QgsFeature(fields, fid)
    f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in pts]))
    f.setAttributes([nama_id])
    return f


class TestNearestNeighbor(unittest.TestCase):
    """Pengujian fungsi nearest_neighbor (nearest.py)."""

    def test_nearest_tanpa_kandidat(self):
        sp_index = QgsSpatialIndex()
        dict_geom = {}
        pt = QgsPointXY(10.0, 10.0)

        fid, pt_near, jarak = cari_terdekat(pt, sp_index, dict_geom)
        self.assertIsNone(fid)
        self.assertIsNone(pt_near)
        self.assertEqual(jarak, float("inf"))

    def test_nearest_tie_break_id_terkecil(self):
        f1 = buat_fitur_garis(20, [(-10.0, -10.0), (10.0, -10.0)], "G-20")
        f2 = buat_fitur_garis(10, [(-10.0, 10.0), (10.0, 10.0)], "G-10")

        sp_index = QgsSpatialIndex()
        sp_index.addFeature(f1)
        sp_index.addFeature(f2)

        dict_geom = {10: f2.geometry(), 20: f1.geometry()}
        pt = QgsPointXY(0.0, 0.0)

        fid, pt_near, jarak = cari_terdekat(pt, sp_index, dict_geom)
        self.assertAlmostEqual(jarak, 10.0, places=3)
        self.assertEqual(fid, 10)


class TestSnapping(unittest.TestCase):
    """Pengujian modul auto_snap_jtr_ke_gardu (snapping.py)."""

    def setUp(self):
        self.crs = QgsCoordinateReferenceSystem("EPSG:32750")

    def test_snapping_dalam_luar_dan_batas_toleransi(self):
        gardu = [buat_fitur_titik(1, 100.0, 100.0, "G-01")]

        jtr_dekat = buat_fitur_garis(1, [(105.0, 100.0), (150.0, 100.0)], "JTR-01")
        jtr_jauh = buat_fitur_garis(2, [(150.0, 100.0), (200.0, 100.0)], "JTR-02")
        jtr_batas = buat_fitur_garis(3, [(110.0, 100.0), (180.0, 100.0)], "JTR-03")

        wkt_asli_1 = jtr_dekat.geometry().asWkt()
        wkt_asli_2 = jtr_jauh.geometry().asWkt()
        wkt_asli_3 = jtr_batas.geometry().asWkt()

        daftar_jtr = [jtr_dekat, jtr_jauh, jtr_batas]
        hasil = auto_snap_jtr_ke_gardu(
            daftar_jtr,
            gardu,
            toleransi_m=10.0,
            field_id_jtr="ID",
            field_id_gardu="ID",
            crs=self.crs,
        )

        self.assertEqual(hasil.jumlah_snapped, 2)
        self.assertEqual(hasil.jumlah_utuh, 1)

        detail = {d["id_jtr"]: d for d in hasil.detail_log}
        self.assertEqual(detail["JTR-01"]["status"], "SNAPPED")
        self.assertEqual(detail["JTR-02"]["status"], "UTUH")
        self.assertEqual(detail["JTR-03"]["status"], "SNAPPED")

        self.assertEqual(jtr_dekat.geometry().asWkt(), wkt_asli_1)
        self.assertEqual(jtr_jauh.geometry().asWkt(), wkt_asli_2)
        self.assertEqual(jtr_batas.geometry().asWkt(), wkt_asli_3)


class TestDangling(unittest.TestCase):
    """Pengujian deteksi dan penyambungan garis dangling (dangling.py)."""

    def setUp(self):
        self.crs = QgsCoordinateReferenceSystem("EPSG:32750")

    def test_deteksi_dan_penyambungan_dangling(self):
        gardu = [buat_fitur_titik(1, 0.0, 0.0, "G-01")]

        jtr1 = buat_fitur_garis(1, [(0.0, 0.0), (50.0, 0.0)], "JTR-01")
        jtr2 = buat_fitur_garis(2, [(54.0, 0.0), (100.0, 0.0)], "JTR-02")
        jtr3 = buat_fitur_garis(3, [(200.0, 200.0), (250.0, 200.0)], "JTR-03")

        daftar_jtr = [jtr1, jtr2, jtr3]

        dangling_list = deteksi_dangling(
            daftar_jtr,
            gardu,
            epsilon_m=0.05,
            field_id_jtr="ID",
            field_id_gardu="ID",
        )

        self.assertEqual(len(dangling_list), 5)

        hasil_sambung = sambung_dangling(
            dangling_list,
            daftar_jtr,
            toleransi_m=8.0,
            field_id_jtr="ID",
            crs=self.crs,
        )

        self.assertGreaterEqual(hasil_sambung.jumlah_tersambung, 2)
        self.assertGreater(hasil_sambung.jumlah_tidak_tersambung, 0)
        self.assertIsNotNone(hasil_sambung.layer_hasil)


class TestAnomaliAppDanUsulanSLTR(unittest.TestCase):
    """Pengujian deteksi anomali APP dan usulan SLTR ke jaringan aktif (anomali_app.py & usulan.py)."""

    def setUp(self):
        self.crs = QgsCoordinateReferenceSystem("EPSG:32750")

    def test_anomali_app_dan_usulan_hanya_ke_jaringan_aktif(self):
        jtr_aktif = buat_fitur_garis(1, [(0.0, 0.0), (50.0, 0.0)], "JTR-AKTIF")
        jtr_isolir = buat_fitur_garis(2, [(10.0, 10.0), (50.0, 10.0)], "JTR-ISOLIR")

        app_ada = buat_fitur_titik(1, 20.0, 0.2, "APP-01")
        app_dekat_isolir = buat_fitur_titik(2, 20.0, 12.0, "APP-02")
        app_jauh = buat_fitur_titik(3, 20.0, 80.0, "APP-03")

        daftar_app = [app_ada, app_dekat_isolir, app_jauh]
        gabungan_jaringan = [jtr_aktif, jtr_isolir]

        hasil_anomali = deteksi_anomali_app(
            daftar_app,
            gabungan_jaringan,
            app_cover_m=0.5,
            field_id_app="ID",
            field_id_jaringan="ID",
            crs=self.crs,
        )

        self.assertEqual(hasil_anomali.jumlah_ada, 1)
        self.assertEqual(hasil_anomali.jumlah_tidak_ada, 2)

        daftar_jaringan_aktif = [jtr_aktif]

        hasil_usulan = buat_sltr_usulan(
            hasil_anomali.detail_app,
            daftar_jaringan_aktif,
            app_usulan_maks_m=50.0,
            field_id_jaringan="ID",
            crs=self.crs,
        )

        self.assertEqual(hasil_usulan.jumlah_usulan, 1)
        self.assertEqual(hasil_usulan.jumlah_tanpa_usulan, 1)

        detail_usul = {u["id_app"]: u for u in hasil_usulan.detail_usulan}
        self.assertEqual(detail_usul["APP-02"]["id_target"], "JTR-AKTIF")
        self.assertAlmostEqual(detail_usul["APP-02"]["jarak_m"], 12.0, places=2)


class TestStylerDanLayerGroup(unittest.TestCase):
    """Pengujian penerapan style dan pengelompokan layer tree (styler.py & layer_group.py)."""

    def setUp(self):
        self.crs = QgsCoordinateReferenceSystem("EPSG:32750")

    def test_styling_dan_layer_group(self):
        lyr_jtr = QgsVectorLayer("LineString?crs=EPSG:32750", "JTR Snapping", "memory")
        lyr_dangling = QgsVectorLayer("LineString?crs=EPSG:32750", "Penyambungan Dangling", "memory")
        lyr_app = QgsVectorLayer("Point?crs=EPSG:32750", "APP Anomali", "memory")
        lyr_sltr = QgsVectorLayer("LineString?crs=EPSG:32750", "SLTR Usulan", "memory")

        self.assertTrue(terapkan_style_app_anomali(lyr_app))
        self.assertTrue(terapkan_style_sltr_usulan(lyr_sltr))
        self.assertTrue(terapkan_style_dangling(lyr_dangling))
        self.assertTrue(terapkan_style_jtr_snapping(lyr_jtr))

        renderer = lyr_app.renderer()
        self.assertIsInstance(renderer, QgsCategorizedSymbolRenderer)
        self.assertEqual(renderer.classAttribute(), "STATUS")
        cats = {c.value(): c for c in renderer.categories()}
        self.assertIn("ADA", cats)
        self.assertIn("TIDAK ADA", cats)
        warna_tidak_ada = cats["TIDAK ADA"].symbol().color().name()
        self.assertEqual(warna_tidak_ada.lower(), "#ef4444")

        project = QgsProject.instance()
        group = kelompokkan_layer(lyr_jtr, lyr_dangling, lyr_app, lyr_sltr, project=project)

        self.assertIsNotNone(group)
        self.assertTrue(group.name().startswith("GeoConnect-AI - Hasil"))
        self.assertEqual(len(group.children()), 4)

        child_layers = [child.layer() for child in group.children()]
        self.assertEqual(child_layers[0].name(), "APP Anomali")
        self.assertEqual(child_layers[1].name(), "SLTR Usulan")
        self.assertEqual(child_layers[2].name(), "Penyambungan Dangling")
        self.assertEqual(child_layers[3].name(), "JTR Snapping")


class TestExporterDanReporter(unittest.TestCase):
    """Pengujian modul ekspor layer dan pembuatan laporan (exporter.py & reporter.py)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ekspor_layer_dan_baca_ulang(self):
        lyr = QgsVectorLayer("Point?crs=EPSG:32750", "Uji_Ekspor", "memory")
        pr = lyr.dataProvider()
        pr.addAttributes([QgsField("ID", QVariant.String, len=10)])
        lyr.updateFields()

        f1 = buat_fitur_titik(1, 10.0, 10.0, "P-01")
        f2 = buat_fitur_titik(2, 20.0, 20.0, "P-02")
        f3 = buat_fitur_titik(3, 30.0, 30.0, "P-03")
        pr.addFeatures([f1, f2, f3])

        gpkg_file = os.path.join(self.temp_dir, "hasil_uji.gpkg")
        sukses_gpkg, msg_gpkg = ekspor_layer(lyr, gpkg_file, "GPKG")
        self.assertTrue(sukses_gpkg)
        self.assertTrue(os.path.exists(gpkg_file))

        lyr_gpkg = QgsVectorLayer(gpkg_file, "Baca_Ulang_GPKG", "ogr")
        self.assertTrue(lyr_gpkg.isValid())
        self.assertEqual(lyr_gpkg.featureCount(), 3)

        geojson_file = os.path.join(self.temp_dir, "hasil_uji.geojson")
        sukses_json, msg_json = ekspor_layer(lyr, geojson_file, "GEOJSON")
        self.assertTrue(sukses_json)
        self.assertTrue(os.path.exists(geojson_file))

        lyr_json = QgsVectorLayer(geojson_file, "Baca_Ulang_GeoJSON", "ogr")
        self.assertTrue(lyr_json.isValid())
        self.assertEqual(lyr_json.featureCount(), 3)

    def test_pembuatan_laporan(self):
        hp = HasilPipeline()
        hp.sukses = True
        hp.waktu_eksekusi_detik = 2.45
        hp.ringkasan = {
            "total_data_diproses": 100,
            "total_data_valid": 95,
            "total_data_bermasalah": 5,
            "jtr_snapped": 12,
            "jtr_utuh": 30,
            "dangling_terdeteksi": 8,
            "dangling_tersambung": 6,
            "dangling_tak_tersambung": 2,
            "app_total": 50,
            "app_ada": 42,
            "app_tidak_ada": 8,
            "sltr_usulan_dibuat": 7,
            "app_tanpa_usulan": 1,
        }

        teks = buat_ringkasan_teks(hp)
        self.assertIn("RINGKASAN HASIL OTOMATISASI TOPOLOGI", teks)
        self.assertIn("SUKSES", teks)
        self.assertIn("2.45 detik", teks)

        laporan_file = os.path.join(self.temp_dir, "laporan_hasil.xlsx")
        sukses_lap, msg_lap = buat_laporan_excel(hp, laporan_file)
        self.assertTrue(sukses_lap)
        self.assertTrue(
            os.path.exists(laporan_file) or os.path.exists(os.path.join(self.temp_dir, "laporan_hasil.csv"))
        )


class TestPipelineDanUI(unittest.TestCase):
    """Pengujian orkestrasi pipeline menyeluruh dan integrasi antarmuka UI."""

    def test_pipeline_end_to_end_dan_keutuhan_data_sumber(self):
        # 1. Buat data layer sumber lengkap
        lyr_gardu = QgsVectorLayer("Point?crs=EPSG:32750", "Gardu_Test", "memory")
        pr_g = lyr_gardu.dataProvider()
        pr_g.addAttributes([QgsField("ID", QVariant.String, len=50)])
        lyr_gardu.updateFields()
        pr_g.addFeatures([buat_fitur_titik(1, 0.0, 0.0, "G-01")])

        lyr_jtr = QgsVectorLayer("LineString?crs=EPSG:32750", "JTR_Test", "memory")
        pr_j = lyr_jtr.dataProvider()
        pr_j.addAttributes([QgsField("ID", QVariant.String, len=50)])
        lyr_jtr.updateFields()
        # JTR-01 dekat Gardu (jarak 4.0 m), JTR-02 dangling dekat JTR-01 (jarak 3.0 m)
        pr_j.addFeatures([
            buat_fitur_garis(1, [(4.0, 0.0), (50.0, 0.0)], "JTR-01"),
            buat_fitur_garis(2, [(53.0, 0.0), (100.0, 0.0)], "JTR-02"),
        ])

        lyr_app = QgsVectorLayer("Point?crs=EPSG:32750", "APP_Test", "memory")
        pr_a = lyr_app.dataProvider()
        pr_a.addAttributes([QgsField("ID", QVariant.String, len=50)])
        lyr_app.updateFields()
        pr_a.addFeatures([
            buat_fitur_titik(1, 20.0, 0.1, "APP-01"), # ADA (0.1 m <= 0.5 m)
            buat_fitur_titik(2, 20.0, 8.0, "APP-02"), # TIDAK ADA (8 m <= 50 m) -> USULAN
        ])

        wkt_gardu_asli = [f.geometry().asWkt() for f in lyr_gardu.getFeatures()]
        wkt_jtr_asli = [f.geometry().asWkt() for f in lyr_jtr.getFeatures()]
        wkt_app_asli = [f.geometry().asWkt() for f in lyr_app.getFeatures()]

        cfg = PipelineConfig(
            layer_gardu=lyr_gardu,
            layer_jtr=lyr_jtr,
            layer_app=lyr_app,
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
            proses_styling=True,
            proses_layer_group=True,
        )

        progress_calls = []
        def on_prog(p, t):
            progress_calls.append((p, t))

        # 2. Jalankan pipeline
        hasil = jalankan_pipeline(cfg, progress_cb=on_prog)

        self.assertTrue(hasil.sukses)
        self.assertGreaterEqual(len(progress_calls), 8)
        self.assertEqual(progress_calls[-1][0], 100)

        # 3. Verifikasi hasil pemrosesan
        self.assertEqual(hasil.ringkasan["jtr_snapped"], 1)
        self.assertEqual(hasil.ringkasan["app_ada"], 1)
        self.assertEqual(hasil.ringkasan["app_tidak_ada"], 1)
        self.assertEqual(hasil.ringkasan["sltr_usulan_dibuat"], 1)

        # 4. Verifikasi KEUTUHAN DATA SUMBER (Non-destruktif)
        wkt_gardu_sesudah = [f.geometry().asWkt() for f in lyr_gardu.getFeatures()]
        wkt_jtr_sesudah = [f.geometry().asWkt() for f in lyr_jtr.getFeatures()]
        wkt_app_sesudah = [f.geometry().asWkt() for f in lyr_app.getFeatures()]

        self.assertEqual(wkt_gardu_asli, wkt_gardu_sesudah)
        self.assertEqual(wkt_jtr_asli, wkt_jtr_sesudah)
        self.assertEqual(wkt_app_asli, wkt_app_sesudah)

    def test_ui_dialog_instansiasi_dan_validasi(self):
        # Bersihkan layer project sementara agar dialog mulai dari kondisi kosong
        QgsProject.instance().removeAllMapLayers()
        dlg = GeoConnectAIDialog()
        self.assertIsNotNone(dlg)
        self.assertIn("GeoConnect-AI", dlg.windowTitle())

        # Tombol jalankan default disable jika layer belum dipilih
        self.assertFalse(dlg.btn_jalankan.isEnabled())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
