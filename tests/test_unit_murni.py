"""Unit test murni (pure Python) untuk GeoConnect-AI.

Dapat dijalankan secara mandiri tanpa memerlukan instalasi QGIS
menggunakan `python -m unittest tests/test_unit_murni.py`.
"""

import math
import unittest
from geoconnect_ai.core.config import ToleransiConfig, PipelineConfig, HasilValidasi
from geoconnect_ai.core.crs_utils import hitung_zona_utm, hitung_epsg_utm
from geoconnect_ai.core.graph_builder import (
    kunci_node,
    DisjointSet,
    bangun_graf,
    cari_connected_components,
    tandai_komponen_aktif,
)


class TestConfig(unittest.TestCase):
    """Pengujian konfigurasi default dan kustom."""

    def test_toleransi_default(self):
        cfg = ToleransiConfig()
        self.assertEqual(cfg.jtr_gardu_m, 10.0)
        self.assertEqual(cfg.dangling_m, 8.0)
        self.assertEqual(cfg.app_cover_m, 0.5)
        self.assertEqual(cfg.app_usulan_maks_m, 50.0)
        self.assertEqual(cfg.epsilon_node_m, 0.05)

    def test_pipeline_config_instansiasi(self):
        pcfg = PipelineConfig()
        self.assertTrue(pcfg.proses_snapping)
        self.assertTrue(pcfg.proses_dangling)
        self.assertTrue(pcfg.proses_anomali_app)
        self.assertTrue(pcfg.proses_styling)
        self.assertTrue(pcfg.proses_layer_group)
        self.assertIsInstance(pcfg.toleransi, ToleransiConfig)

    def test_hasil_validasi_default(self):
        hv = HasilValidasi()
        self.assertEqual(len(hv.valid), 0)
        self.assertEqual(len(hv.bermasalah), 0)


class TestCRSUtils(unittest.TestCase):
    """Pengujian perhitungan zona UTM dan EPSG otomatis."""

    def test_zona_utm_balikpapan(self):
        # Balikpapan bujur ~116.82 E -> UTM Zona 50
        zona = hitung_zona_utm(116.82)
        self.assertEqual(zona, 50)

    def test_zona_utm_jakarta(self):
        # Jakarta bujur ~106.82 E -> UTM Zona 48
        zona = hitung_zona_utm(106.82)
        self.assertEqual(zona, 48)

    def test_zona_utm_jayapura(self):
        # Jayapura bujur ~140.7 E -> UTM Zona 54
        zona = hitung_zona_utm(140.7)
        self.assertEqual(zona, 54)

    def test_zona_utm_batas(self):
        # Batas bujur -180 -> zona 1, +180 -> zona 60
        self.assertEqual(hitung_zona_utm(-179.9), 1)
        self.assertEqual(hitung_zona_utm(179.9), 60)
        self.assertEqual(hitung_zona_utm(0.0), 31)

    def test_epsg_utm_balikpapan(self):
        # Balikpapan: lintang selatan (-1.26), bujur 116.82 -> EPSG:32750
        epsg = hitung_epsg_utm(116.82, -1.26)
        self.assertEqual(epsg, 32750)

    def test_epsg_utm_tarakan(self):
        # Tarakan, Kaltara: lintang utara (+3.32), bujur 117.58 -> EPSG:32650
        epsg = hitung_epsg_utm(117.58, 3.32)
        self.assertEqual(epsg, 32650)


class TestKunciNode(unittest.TestCase):
    """Pengujian kuantisasi node pada grid epsilon."""

    def test_kunci_node_berimpit(self):
        p1 = kunci_node(500000.00, 9800000.00, epsilon=0.05)
        p2 = kunci_node(500000.02, 9800000.01, epsilon=0.05)
        self.assertEqual(p1, p2)

    def test_kunci_node_berbeda(self):
        p1 = kunci_node(500000.00, 9800000.00, epsilon=0.05)
        p2 = kunci_node(500000.20, 9800000.00, epsilon=0.05)
        self.assertNotEqual(p1, p2)


class TestUnionFindDanGraf(unittest.TestCase):
    """Pengujian struktur data Union-Find dan pembuatan graf topologi."""

    def test_disjoint_set_dasar(self):
        ds = DisjointSet()
        ds.make_set("A")
        ds.make_set("B")
        ds.make_set("C")

        self.assertFalse(ds.connected("A", "B"))
        ds.union("A", "B")
        self.assertTrue(ds.connected("A", "B"))
        self.assertFalse(ds.connected("A", "C"))

        ds.union("B", "C")
        self.assertTrue(ds.connected("A", "C"))

        comps = ds.get_components()
        self.assertEqual(len(comps), 1)

    def test_bangun_graf_dan_komponen(self):
        # Komponen 1: S1 (0,0)->(10,0), S2 (10,0)->(20,0) [Panjang 20]
        # Gardu G1 di (0,0)
        # Komponen 2: S3 (100,100)->(150,100) [Panjang 50, terisolasi tanpa gardu]
        segmen = [
            {"id": "S1", "start": (0.0, 0.0), "end": (10.0, 0.0), "length": 10.0},
            {"id": "S2", "start": (10.0, 0.0), "end": (20.0, 0.0), "length": 10.0},
            {"id": "S3", "start": (100.0, 100.0), "end": (150.0, 100.0), "length": 50.0},
        ]
        gardu = [
            {"id": "G1", "pos": (0.0, 0.0)},
        ]

        graf = bangun_graf(segmen, gardu, epsilon=0.05)
        komponen = cari_connected_components(graf)

        self.assertEqual(len(komponen), 2)

        # Cari komponen yang terhubung ke gardu
        aktif_comp_ids, aktif_segmen_ids = tandai_komponen_aktif(graf, komponen)

        self.assertEqual(len(aktif_comp_ids), 1)
        self.assertIn("S1", aktif_segmen_ids)
        self.assertIn("S2", aktif_segmen_ids)
        self.assertNotIn("S3", aktif_segmen_ids)

    def test_fallback_tanpa_gardu(self):
        # Jika tidak ada gardu yang menyentuh, fallback ke komponen terbesar
        segmen = [
            {"id": "S1", "start": (0.0, 0.0), "end": (10.0, 0.0), "length": 10.0},
            {"id": "S2", "start": (100.0, 100.0), "end": (160.0, 100.0), "length": 60.0},
        ]
        gardu = [] # Tidak ada gardu

        log_messages = []
        def catat_log(msg):
            log_messages.append(msg)

        graf = bangun_graf(segmen, gardu, epsilon=0.05)
        komponen = cari_connected_components(graf)
        aktif_comp_ids, aktif_segmen_ids = tandai_komponen_aktif(graf, komponen, log_cb=catat_log)

        # Komponen S2 (panjang 60) adalah komponen terbesar
        self.assertEqual(len(aktif_comp_ids), 1)
        self.assertIn("S2", aktif_segmen_ids)
        self.assertNotIn("S1", aktif_segmen_ids)
        self.assertTrue(len(log_messages) > 0)
        self.assertIn("PERINGATAN", log_messages[0])

    def test_graf_kosong(self):
        graf = bangun_graf([], [])
        komponen = cari_connected_components(graf)
        self.assertEqual(len(komponen), 0)
        aktif_comp_ids, aktif_segmen_ids = tandai_komponen_aktif(graf, komponen)
        self.assertEqual(len(aktif_comp_ids), 0)
        self.assertEqual(len(aktif_segmen_ids), 0)


if __name__ == "__main__":
    unittest.main()
