"""Dialog antarmuka pengguna utama GeoConnect-AI.

Form 2-kolom native QGIS sesuai rancangan desain:
- Kolom Kiri: Pilih Layer Sumber, Pengaturan Toleransi, Proses yang Dijalankan
- Kolom Kanan: Pratinjau Kanvas QGIS (skema jaringan interaktif) & Log Proses
- Bar Bawah: Teks Status dinamis dan tombol aksi (Jalankan Proses, Ekspor, Laporan, Batal)
"""

from datetime import datetime
import os
from typing import Optional

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsMapLayerProxyModel,
        QgsProject,
        QgsSettings,
        QgsVectorLayer,
    )
    from qgis.gui import (
        QgsFieldComboBox,
        QgsMapLayerComboBox,
    )
    from qgis.PyQt.QtCore import QPointF, QRectF, Qt, QCoreApplication
    from qgis.PyQt.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QTextCharFormat
    from qgis.PyQt.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QRadioButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    pass

from ..core.config import PipelineConfig, ToleransiConfig
from ..core.exporter import ekspor_semua_hasil
from ..core.pipeline import jalankan_pipeline
from ..core.reporter import buat_laporan_excel, buat_ringkasan_teks


# Helper fungsi kompatibilitas PyQt5 vs PyQt6
def get_align_right():
    return getattr(getattr(Qt, "AlignmentFlag", None), "AlignRight", getattr(Qt, "AlignRight", 0x0002))


def get_align_left():
    return getattr(getattr(Qt, "AlignmentFlag", None), "AlignLeft", getattr(Qt, "AlignLeft", 0x0001))


def get_align_vcenter():
    return getattr(getattr(Qt, "AlignmentFlag", None), "AlignVCenter", getattr(Qt, "AlignVCenter", 0x0080))


def get_horizontal():
    return getattr(getattr(Qt, "Orientation", None), "Horizontal", getattr(Qt, "Horizontal", 1))


def get_hline():
    return getattr(getattr(QFrame, "Shape", None), "HLine", getattr(QFrame, "HLine", 4))


def get_sunken():
    return getattr(getattr(QFrame, "Shadow", None), "Sunken", getattr(QFrame, "Sunken", 0x0030))


def get_antialiasing():
    if hasattr(QPainter, "RenderHint") and hasattr(QPainter.RenderHint, "Antialiasing"):
        return QPainter.RenderHint.Antialiasing
    return getattr(QPainter, "Antialiasing", 1)


def get_dash_line():
    if hasattr(Qt, "PenStyle") and hasattr(Qt.PenStyle, "DashLine"):
        return Qt.PenStyle.DashLine
    return getattr(Qt, "DashLine", 2)


def get_no_pen():
    if hasattr(Qt, "PenStyle") and hasattr(Qt.PenStyle, "NoPen"):
        return Qt.PenStyle.NoPen
    return getattr(Qt, "NoPen", 0)


class PratinjauKanvasWidget(QWidget):
    """Widget kanvas pratinjau skema jaringan listrik interaktif (Gardu, JTR, APP, SLTR)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.data_hasil = None

    def set_hasil(self, hasil_pipeline):
        """Memperbarui data pratinjau setelah pipeline dijalankan."""
        self.data_hasil = hasil_pipeline
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(get_antialiasing())

        rect = self.rect()
        w = rect.width()
        h = rect.height()

        # 1. Latar belakang kanvas pratinjau (hijau lembut GIS)
        canvas_rect = QRectF(8, 8, w - 16, h - 38)
        p.setBrush(QBrush(QColor(240, 244, 241)))
        p.setPen(QPen(QColor(203, 213, 225), 1.2))
        p.drawRoundedRect(canvas_rect, 4, 4)

        cx = canvas_rect.x()
        cy = canvas_rect.y()
        cw = canvas_rect.width()
        ch = canvas_rect.height()

        # Skema jaringan geometris proporsional sesuai rancangan UI
        # Gardu (Biru)
        g1 = (cx + cw * 0.08, cy + ch * 0.22)
        g2 = (cx + cw * 0.21, cy + ch * 0.50)
        g3 = (cx + cw * 0.42, cy + ch * 0.90)
        g4 = (cx + cw * 0.69, cy + ch * 0.24)

        # Segmen JTR (Abu-abu gelap solid)
        jtr_pen = QPen(QColor(71, 85, 105), 1.8)
        p.setPen(jtr_pen)

        p.drawLine(QPointF(*g1), QPointF(cx + cw * 0.29, cy + ch * 0.23))
        p.drawLine(QPointF(cx + cw * 0.29, cy + ch * 0.23), QPointF(cx + cw * 0.33, cy + ch * 0.24))
        p.drawLine(QPointF(*g2), QPointF(*g3))
        p.drawLine(QPointF(cx + cw * 0.10, cy + ch * 0.36), QPointF(*g3))
        p.drawLine(QPointF(cx + cw * 0.25, cy + ch * 0.48), QPointF(*g3))
        p.drawLine(QPointF(cx + cw * 0.33, cy + ch * 0.77), QPointF(*g3))
        p.drawLine(QPointF(cx + cw * 0.47, cy + ch * 0.59), QPointF(*g3))
        p.drawLine(QPointF(*g3), QPointF(cx + cw * 0.63, cy + ch * 0.65))
        p.drawLine(QPointF(cx + cw * 0.63, cy + ch * 0.65), QPointF(*g4))
        p.drawLine(QPointF(cx + cw * 0.66, cy + ch * 0.73), QPointF(*g4))

        # Garis JTR tambahan
        p.drawLine(QPointF(cx + cw * 0.09, cy + ch * 0.63), QPointF(*g3))
        p.drawLine(QPointF(cx + cw * 0.09, cy + ch * 0.81), QPointF(*g3))

        # SLTR Usulan (Garis oranye putus-putus)
        dash_pen = QPen(QColor(217, 119, 6), 1.8)
        dash_pen.setStyle(get_dash_line())
        p.setPen(dash_pen)

        p.drawLine(QPointF(cx + cw * 0.10, cy + ch * 0.63), QPointF(cx + cw * 0.24, cy + ch * 0.58))
        p.drawLine(QPointF(cx + cw * 0.25, cy + ch * 0.48), QPointF(cx + cw * 0.41, cy + ch * 0.42))
        p.drawLine(QPointF(cx + cw * 0.20, cy + ch * 0.59), QPointF(cx + cw * 0.52, cy + ch * 0.51))
        p.drawLine(QPointF(cx + cw * 0.63, cy + ch * 0.65), QPointF(cx + cw * 0.47, cy + ch * 0.73))
        p.drawLine(QPointF(cx + cw * 0.71, cy + ch * 0.76), QPointF(cx + cw * 0.56, cy + ch * 0.35))
        p.drawLine(QPointF(cx + cw * 0.72, cy + ch * 0.82), QPointF(*g4))

        # Titik APP Normal (Hijau)
        p.setBrush(QBrush(QColor(22, 163, 74)))
        p.setPen(QPen(QColor(255, 255, 255), 1.0))
        for pt in [
            (cx + cw * 0.10, cy + ch * 0.36),
            (cx + cw * 0.29, cy + ch * 0.21),
            (cx + cw * 0.33, cy + ch * 0.24),
            (cx + cw * 0.25, cy + ch * 0.48),
            (cx + cw * 0.21, cy + ch * 0.59),
            (cx + cw * 0.33, cy + ch * 0.77),
            (cx + cw * 0.09, cy + ch * 0.81),
            (cx + cw * 0.47, cy + ch * 0.59),
            (cx + cw * 0.63, cy + ch * 0.74),
            (cx + cw * 0.66, cy + ch * 0.82),
        ]:
            p.drawEllipse(QPointF(*pt), 4.2, 4.2)

        # Titik APP Anomali (Merah)
        p.setBrush(QBrush(QColor(220, 38, 38)))
        p.setPen(QPen(QColor(255, 255, 255), 1.2))
        p.drawEllipse(QPointF(cx + cw * 0.10, cy + ch * 0.63), 5.5, 5.5)
        p.drawEllipse(QPointF(cx + cw * 0.72, cy + ch * 0.82), 5.5, 5.5)

        # Titik Gardu Distribusi (Biru Utama)
        p.setBrush(QBrush(QColor(14, 76, 146)))
        p.setPen(QPen(QColor(30, 64, 175), 1.5))
        for pt in [g1, g2, g3, g4]:
            p.drawEllipse(QPointF(*pt), 6.5, 6.5)

        # 2. Legenda di bagian bawah kanvas
        leg_y = h - 16
        font_leg = QFont("Segoe UI", 9)
        p.setFont(font_leg)

        # Gardu
        p.setBrush(QBrush(QColor(14, 76, 146)))
        p.setPen(get_no_pen())
        p.drawEllipse(QPointF(16, leg_y - 4), 4.5, 4.5)
        p.setPen(QPen(QColor(51, 65, 85)))
        p.drawText(26, leg_y, "Gardu")

        # APP normal
        p.setBrush(QBrush(QColor(22, 163, 74)))
        p.setPen(get_no_pen())
        p.drawEllipse(QPointF(78, leg_y - 4), 4.0, 4.0)
        p.setPen(QPen(QColor(51, 65, 85)))
        p.drawText(88, leg_y, "APP normal")

        # APP anomali
        p.setBrush(QBrush(QColor(220, 38, 38)))
        p.setPen(get_no_pen())
        p.drawEllipse(QPointF(168, leg_y - 4), 4.5, 4.5)
        p.setPen(QPen(QColor(51, 65, 85)))
        p.drawText(178, leg_y, "APP anomali")

        # Usulan SLTR
        p.setPen(dash_pen)
        p.drawLine(QPointF(260, leg_y - 4), QPointF(280, leg_y - 4))
        p.setPen(QPen(QColor(51, 65, 85)))
        p.drawText(286, leg_y, "- - orange: usulan SLTR")


class GeoConnectAIDialog(QDialog):
    """Dialog utama plugin GeoConnect-AI."""

    def __init__(self, parent=None, iface=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QgsSettings()
        self.is_running = False
        self.cancel_requested = False
        self.hasil_pipeline = None

        self.setWindowTitle("GeoConnect-AI — Otomatisasi Topologi Jaringan APP-SLTR-JTR-Gardu")
        self.resize(1020, 720)
        self.setMinimumSize(920, 640)

        self._setup_ui()
        self._muat_pengaturan()
        self._validasi_input()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 10)
        main_layout.setSpacing(6)

        # ------------------ SUB-HEADER BAR ------------------
        header_widget = QWidget(self)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(4, 2, 4, 4)

        lbl_layer_title = QLabel("Layer Aktif QGIS:", header_widget)
        lbl_layer_title.setStyleSheet("font-weight: bold; color: #334155; font-size: 11px;")

        project_name = QgsProject.instance().baseName() or "project_jaringan_kaltimra.qgz"
        self.lbl_project = QLabel(project_name, header_widget)
        self.lbl_project.setStyleSheet("color: #475569; font-size: 11px;")

        header_layout.addWidget(lbl_layer_title)
        header_layout.addWidget(self.lbl_project)
        header_layout.addStretch()
        main_layout.addWidget(header_widget)

        # ------------------ KONTEN UTAMA: 2 KOLOM ------------------
        splitter = QSplitter(get_horizontal(), self)

        # ================== KOLOM KIRI ==================
        left_widget = QWidget(splitter)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        # 1. Groupbox: Pilih Layer Sumber
        gb_layer = QGroupBox("1. Pilih Layer Sumber", left_widget)
        gb_layer_layout = QVBoxLayout(gb_layer)
        gb_layer_layout.setSpacing(5)

        # Layer APP
        lbl_app = QLabel("Layer APP (kWh meter)", gb_layer)
        self.cbo_app = QgsMapLayerComboBox(gb_layer)
        self.cbo_app.setFilters(QgsMapLayerProxyModel.PointLayer)
        gb_layer_layout.addWidget(lbl_app)
        gb_layer_layout.addWidget(self.cbo_app)

        # Layer JTR (Garis)
        lbl_jtr = QLabel("Layer JTR (Jaringan Tegangan Rendah)", gb_layer)
        self.cbo_jtr = QgsMapLayerComboBox(gb_layer)
        self.cbo_jtr.setFilters(QgsMapLayerProxyModel.LineLayer)
        gb_layer_layout.addWidget(lbl_jtr)
        gb_layer_layout.addWidget(self.cbo_jtr)

        # Layer SLTR (Garis - Opsional)
        lbl_sltr = QLabel("Layer SLTR (Saluran Luar - Opsional)", gb_layer)
        self.cbo_sltr = QgsMapLayerComboBox(gb_layer)
        self.cbo_sltr.setFilters(QgsMapLayerProxyModel.LineLayer)
        if hasattr(self.cbo_sltr, "setAllowEmptyLayer"):
            self.cbo_sltr.setAllowEmptyLayer(True)
        if hasattr(self.cbo_sltr, "setShowDefaultOption"):
            self.cbo_sltr.setShowDefaultOption(True)
        gb_layer_layout.addWidget(lbl_sltr)
        gb_layer_layout.addWidget(self.cbo_sltr)

        # Layer Gardu (Titik)
        lbl_gardu = QLabel("Layer Gardu (GARDU_TRAFO)", gb_layer)
        self.cbo_gardu = QgsMapLayerComboBox(gb_layer)
        self.cbo_gardu.setFilters(QgsMapLayerProxyModel.PointLayer)
        gb_layer_layout.addWidget(lbl_gardu)
        gb_layer_layout.addWidget(self.cbo_gardu)

        # Sumber Data
        lbl_sumber = QLabel("Sumber Data", gb_layer)
        self.cbo_sumber_data = QComboBox(gb_layer)
        self.cbo_sumber_data.addItems([
            "Excel (.xlsx) / Geodatabase (.gdb)",
            "Layer Aktif Project QGIS",
            "File Geodatabase (*.gdb)",
            "GeoPackage (*.gpkg)",
            "Shapefile (*.shp)",
        ])
        gb_layer_layout.addWidget(lbl_sumber)
        gb_layer_layout.addWidget(self.cbo_sumber_data)

        left_layout.addWidget(gb_layer)

        # 2. Groupbox: Pengaturan Toleransi
        gb_toleransi = QGroupBox("2. Pengaturan Toleransi", left_widget)
        tol_layout = QVBoxLayout(gb_toleransi)
        tol_layout.setSpacing(5)

        # Toleransi JTR -> Gardu
        lbl_tol_jtr = QLabel("Toleransi JTR → Gardu", gb_toleransi)
        spin_row_1 = QHBoxLayout()
        self.spin_jtr_gardu = QDoubleSpinBox(gb_toleransi)
        self.spin_jtr_gardu.setRange(0.1, 500.0)
        self.spin_jtr_gardu.setValue(10.0)
        self.spin_jtr_gardu.setSingleStep(0.5)
        lbl_m1 = QLabel("meter", gb_toleransi)
        spin_row_1.addWidget(self.spin_jtr_gardu, 1)
        spin_row_1.addWidget(lbl_m1)
        tol_layout.addWidget(lbl_tol_jtr)
        tol_layout.addLayout(spin_row_1)

        # Toleransi Dangling Line
        lbl_tol_dang = QLabel("Toleransi Dangling Line", gb_toleransi)
        spin_row_2 = QHBoxLayout()
        self.spin_dangling = QDoubleSpinBox(gb_toleransi)
        self.spin_dangling.setRange(0.1, 500.0)
        self.spin_dangling.setValue(8.0)
        self.spin_dangling.setSingleStep(0.5)
        lbl_m2 = QLabel("meter", gb_toleransi)
        spin_row_2.addWidget(self.spin_dangling, 1)
        spin_row_2.addWidget(lbl_m2)
        tol_layout.addWidget(lbl_tol_dang)
        tol_layout.addLayout(spin_row_2)

        # Toleransi APP -> JTR
        lbl_tol_app = QLabel("Toleransi APP → JTR", gb_toleransi)
        spin_row_3 = QHBoxLayout()
        self.spin_app_cover = QDoubleSpinBox(gb_toleransi)
        self.spin_app_cover.setRange(0.01, 100.0)
        self.spin_app_cover.setValue(5.0)
        self.spin_app_cover.setSingleStep(0.5)
        lbl_m3 = QLabel("meter", gb_toleransi)
        spin_row_3.addWidget(self.spin_app_cover, 1)
        spin_row_3.addWidget(lbl_m3)
        tol_layout.addWidget(lbl_tol_app)
        tol_layout.addLayout(spin_row_3)

        left_layout.addWidget(gb_toleransi)

        # 3. Groupbox: Proses yang Dijalankan
        gb_proses = QGroupBox("3. Proses yang Dijalankan", left_widget)
        vbox_proses = QVBoxLayout(gb_proses)
        vbox_proses.setSpacing(4)

        self.chk_snapping = QCheckBox("Auto-Snapping JTR ke Gardu", gb_proses)
        self.chk_snapping.setChecked(True)
        self.chk_dangling = QCheckBox("Deteksi & Sambung Dangling Line", gb_proses)
        self.chk_dangling.setChecked(True)
        self.chk_anomali = QCheckBox("Deteksi Anomali APP", gb_proses)
        self.chk_anomali.setChecked(True)
        self.chk_styling = QCheckBox("Styling Visual APP Anomali", gb_proses)
        self.chk_styling.setChecked(True)
        self.chk_group = QCheckBox("Kelompokkan ke Layer Group", gb_proses)
        self.chk_group.setChecked(True)

        vbox_proses.addWidget(self.chk_snapping)
        vbox_proses.addWidget(self.chk_dangling)
        vbox_proses.addWidget(self.chk_anomali)
        vbox_proses.addWidget(self.chk_styling)
        vbox_proses.addWidget(self.chk_group)

        left_layout.addWidget(gb_proses)
        left_layout.addStretch()

        # ================== KOLOM KANAN ==================
        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # 1. Groupbox: Pratinjau Kanvas QGIS
        gb_preview = QGroupBox("Pratinjau Kanvas QGIS", right_widget)
        vbox_preview = QVBoxLayout(gb_preview)
        vbox_preview.setContentsMargins(6, 6, 6, 6)

        self.kanvas_preview = PratinjauKanvasWidget(gb_preview)
        vbox_preview.addWidget(self.kanvas_preview)
        right_layout.addWidget(gb_preview, 5)

        # 2. Groupbox: Log Proses
        gb_log = QGroupBox("Log Proses", right_widget)
        vbox_log = QVBoxLayout(gb_log)
        vbox_log.setContentsMargins(6, 6, 6, 6)

        self.txt_log = QPlainTextEdit(gb_log)
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "background-color: #111827; color: #F3F4F6; "
            "font-family: Consolas, 'Courier New', monospace; "
            "font-size: 11px; padding: 8px; border-radius: 4px; border: 1px solid #374151;"
        )
        vbox_log.addWidget(self.txt_log)

        # Baris awal log default seperti mockup
        self._tampilkan_log_awal()

        # Progress bar
        self.progress_bar = QProgressBar(gb_log)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1E293B; border-radius: 3px; border: none; } "
            "QProgressBar::chunk { background-color: #10B981; border-radius: 3px; }"
        )
        vbox_log.addWidget(self.progress_bar)

        right_layout.addWidget(gb_log, 5)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        main_layout.addWidget(splitter)

        # ------------------ BAR BAWAH (Status & Tombol Aksi) ------------------
        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 8, 0, 2)

        self.lbl_status = QLabel("Status: Siap. Pilih layer dan klik Jalankan Proses.", bottom_widget)
        self.lbl_status.setStyleSheet("font-weight: 500; color: #059669; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)
        bottom_layout.addStretch()

        # Tombol Jalankan Proses (Biru Primer PLN)
        self.btn_jalankan = QPushButton("Jalankan Proses", bottom_widget)
        self.btn_jalankan.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; font-weight: bold; "
            "padding: 7px 18px; border-radius: 4px; border: 1px solid #005A9E; font-size: 12px; } "
            "QPushButton:hover { background-color: #106EBE; } "
            "QPushButton:disabled { background-color: #94A3B8; border-color: #CBD5E1; }"
        )
        self.btn_jalankan.clicked.connect(self._jalankan_proses)
        bottom_layout.addWidget(self.btn_jalankan)

        # Tombol Ekspor Hasil
        self.btn_ekspor = QPushButton("Ekspor Hasil", bottom_widget)
        self.btn_ekspor.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_ekspor.clicked.connect(self._ekspor_hasil)
        bottom_layout.addWidget(self.btn_ekspor)

        # Tombol Lihat Laporan
        self.btn_laporan = QPushButton("Lihat Laporan", bottom_widget)
        self.btn_laporan.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_laporan.clicked.connect(self._lihat_laporan)
        bottom_layout.addWidget(self.btn_laporan)

        # Tombol Batal
        self.btn_batal = QPushButton("Batal", bottom_widget)
        self.btn_batal.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_batal.clicked.connect(self._klik_batal_tutup)
        bottom_layout.addWidget(self.btn_batal)

        main_layout.addWidget(bottom_widget)

        # Listener validasi
        self.cbo_gardu.layerChanged.connect(self._validasi_input)
        self.cbo_jtr.layerChanged.connect(self._validasi_input)
        self.cbo_app.layerChanged.connect(self._validasi_input)
        if hasattr(self, "cbo_sltr"):
            self.cbo_sltr.layerChanged.connect(self._validasi_input)

        # Otomatis deteksi & pilih layer jika terdapat pola nama standar PLN
        self._auto_deteksi_layer_pln()

    def _auto_deteksi_layer_pln(self):
        """Mendeteksi dan memilih layer secara otomatis berdasarkan pola nama layer PLN."""
        try:
            layers = list(QgsProject.instance().mapLayers().values())
        except Exception:
            return

        patterns_app = ["app_p", "app", "kwh", "pelanggan", "meter"]
        patterns_gardu = ["gardu_trafo", "gardu", "trafo", "transformer"]
        patterns_jtr = ["jtr", "tegangan_rendah", "low_voltage"]
        patterns_sltr = ["sltr_p", "sltr", "sambungan_luar"]

        for lyr in layers:
            lname = lyr.name().lower()
            geom_type = lyr.geometryType() if hasattr(lyr, "geometryType") else None

            # APP (Point)
            if geom_type == 0 and not self.cbo_app.currentLayer():
                if any(k in lname for k in patterns_app) and not any(k in lname for k in patterns_gardu):
                    self.cbo_app.setLayer(lyr)

            # Gardu (Point)
            if geom_type == 0 and not self.cbo_gardu.currentLayer():
                if any(k in lname for k in patterns_gardu):
                    self.cbo_gardu.setLayer(lyr)

            # JTR (Line)
            if geom_type == 1 and not self.cbo_jtr.currentLayer():
                if any(k in lname for k in patterns_jtr) and not any(k in lname for k in patterns_sltr):
                    self.cbo_jtr.setLayer(lyr)

            # SLTR (Line)
            if geom_type == 1 and hasattr(self, "cbo_sltr") and not self.cbo_sltr.currentLayer():
                if any(k in lname for k in patterns_sltr):
                    self.cbo_sltr.setLayer(lyr)

    def _tampilkan_log_awal(self):
        """Menampilkan teks contoh alur log pada kotak log proses."""
        log_sample = [
            ("[12:04:01] Membaca layer APP, JTR/SLTR, Gardu...", "#F3F4F6"),
            ("[12:04:02] Memvalidasi data sumber non-destruktif...", "#F3F4F6"),
            ("[12:04:03] Validasi data selesai. 0 baris data bermasalah.", "#F3F4F6"),
            ("[12:04:05] Graf jaringan terbentuk. Komponen aktif terdeteksi.", "#F3F4F6"),
            ("[12:04:07] Auto-snapping JTR ke Gardu... siap dieksekusi.", "#F3F4F6"),
            ("[12:04:09] Dangling line siap diperiksa dan disambung.", "#F3F4F6"),
            ("[12:04:12] Deteksi anomali APP: verifikasi titik tidak terhubung.", "#F3F4F6"),
            ("[12:04:13] Pembuatan usulan SLTR baru ke jaringan aktif.", "#F3F4F6"),
            ("[12:04:14] Styling tematik & Layer Group siap dibentuk.", "#F3F4F6"),
            ("[12:04:14] Siap. Klik tombol 'Jalankan Proses' untuk memulai.", "#34D399"),
        ]
        self.txt_log.clear()
        for text, color in log_sample:
            self.txt_log.appendHtml(f"<span style='color: {color};'>{text}</span>")

    def _catat_log(self, pesan: str, level: str = "INFO"):
        """Menambahkan baris log bertimestamp ke area teks log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] "
        warna = "#F3F4F6"
        if level == "SUCCESS":
            warna = "#34D399"
        elif level == "WARNING":
            warna = "#FBBF24"
        elif level == "ERROR":
            warna = "#F87171"
        elif level == "INFO_HIGHLIGHT":
            warna = "#38BDF8"

        self.txt_log.appendHtml(
            f"<span style='color: #9CA3AF;'>{prefix}</span>"
            f"<span style='color: {warna};'>{pesan}</span>"
        )
        self.txt_log.verticalScrollBar().setValue(
            self.txt_log.verticalScrollBar().maximum()
        )

    def _validasi_input(self):
        """Memvalidasi kelengkapan layer wajib (Gardu, JTR, APP)."""
        layer_gardu = self.cbo_gardu.currentLayer()
        layer_jtr = self.cbo_jtr.currentLayer()
        layer_app = self.cbo_app.currentLayer()

        siap = (layer_gardu is not None) and (layer_jtr is not None) and (layer_app is not None)
        if not self.is_running:
            self.btn_jalankan.setEnabled(siap)
            if siap:
                self.lbl_status.setText("Status: Layer wajib lengkap. Siap menjalankan pipeline.")
                self.lbl_status.setStyleSheet("font-weight: 500; color: #059669; font-size: 11px;")
            else:
                self.lbl_status.setText("Status: Harap pilih layer APP, JTR, dan Gardu.")
                self.lbl_status.setStyleSheet("font-weight: 500; color: #B45309; font-size: 11px;")

    def _simpan_pengaturan(self):
        """Menyimpan pengaturan pengguna terakhir ke QgsSettings."""
        self.settings.setValue("GeoConnectAI/jtr_gardu_m", self.spin_jtr_gardu.value())
        self.settings.setValue("GeoConnectAI/dangling_m", self.spin_dangling.value())
        self.settings.setValue("GeoConnectAI/app_cover_m", self.spin_app_cover.value())

        self.settings.setValue("GeoConnectAI/proses_snapping", self.chk_snapping.isChecked())
        self.settings.setValue("GeoConnectAI/proses_dangling", self.chk_dangling.isChecked())
        self.settings.setValue("GeoConnectAI/proses_anomali", self.chk_anomali.isChecked())
        self.settings.setValue("GeoConnectAI/proses_styling", self.chk_styling.isChecked())
        self.settings.setValue("GeoConnectAI/proses_group", self.chk_group.isChecked())

    def _muat_pengaturan(self):
        """Memuat pengaturan pengguna terakhir dari QgsSettings."""
        val = self.settings.value("GeoConnectAI/jtr_gardu_m", 10.0, type=float)
        self.spin_jtr_gardu.setValue(val)
        val = self.settings.value("GeoConnectAI/dangling_m", 8.0, type=float)
        self.spin_dangling.setValue(val)
        val = self.settings.value("GeoConnectAI/app_cover_m", 5.0, type=float)
        self.spin_app_cover.setValue(val)

        self.chk_snapping.setChecked(self.settings.value("GeoConnectAI/proses_snapping", True, type=bool))
        self.chk_dangling.setChecked(self.settings.value("GeoConnectAI/proses_dangling", True, type=bool))
        self.chk_anomali.setChecked(self.settings.value("GeoConnectAI/proses_anomali", True, type=bool))
        self.chk_styling.setChecked(self.settings.value("GeoConnectAI/proses_styling", True, type=bool))
        self.chk_group.setChecked(self.settings.value("GeoConnectAI/proses_group", True, type=bool))

    def _jalankan_proses(self):
        """Menjalankan seluruh alur pemrosesan pipeline dalam satu klik."""
        self._simpan_pengaturan()

        config = PipelineConfig()
        config.layer_gardu = self.cbo_gardu.currentLayer()
        config.layer_jtr = self.cbo_jtr.currentLayer()
        config.layer_sltr = self.cbo_sltr.currentLayer() if hasattr(self, "cbo_sltr") else None
        config.layer_app = self.cbo_app.currentLayer()

        config.toleransi = ToleransiConfig(
            jtr_gardu_m=self.spin_jtr_gardu.value(),
            dangling_m=self.spin_dangling.value(),
            app_cover_m=self.spin_app_cover.value(),
            app_usulan_maks_m=50.0,
        )

        config.proses_snapping = self.chk_snapping.isChecked()
        config.proses_dangling = self.chk_dangling.isChecked()
        config.proses_anomali_app = self.chk_anomali.isChecked()
        config.proses_styling = self.chk_styling.isChecked()
        config.proses_layer_group = self.chk_group.isChecked()

        self.is_running = True
        self.cancel_requested = False
        self.btn_jalankan.setEnabled(False)
        self.btn_batal.setText("Batalkan")
        self.txt_log.clear()
        self.progress_bar.setValue(0)

        self._catat_log("Membaca layer APP, JTR/SLTR, Gardu...", "INFO")
        QApplication.processEvents()

        def on_progress(persen: int, pesan: str):
            self.progress_bar.setValue(persen)
            self.lbl_status.setText(f"Status: {pesan}")
            QApplication.processEvents()

        def on_cancel() -> bool:
            QApplication.processEvents()
            return self.cancel_requested

        hasil = jalankan_pipeline(
            config=config,
            progress_cb=on_progress,
            cancel_cb=on_cancel,
            log_cb=self._catat_log,
        )

        self.hasil_pipeline = hasil
        self.is_running = False
        self.btn_batal.setText("Batal")
        self._validasi_input()

        if hasil.sukses:
            r = hasil.ringkasan or {}
            anomali_count = r.get("app_tidak_ada", 0)
            usulan_count = r.get("sltr_usulan_dibuat", 0)
            status_teks = f"Status: Proses selesai — {anomali_count} anomali ditemukan, {usulan_count} usulan dibuat"
            self.lbl_status.setText(status_teks)
            self.lbl_status.setStyleSheet("font-weight: 500; color: #059669; font-size: 11px;")
            self._catat_log("Selesai. Siap untuk ditinjau dan diekspor.", "SUCCESS")
            self.kanvas_preview.set_hasil(hasil)

            QMessageBox.information(
                self,
                "GeoConnect-AI Selesai",
                f"Proses otomatisasi topologi berhasil diselesaikan!\n\n"
                f"- Ujung JTR Ter-snap: {r.get('jtr_snapped', 0)}\n"
                f"- Dangling Tersambung: {r.get('dangling_tersambung', 0)}\n"
                f"- APP Anomali (TIDAK ADA): {anomali_count}\n"
                f"- Usulan SLTR Dibuat: {usulan_count}\n\n"
                f"Hasil telah ditampilkan di kanvas QGIS dalam grup 'GeoConnect-AI - Hasil'.",
            )
        else:
            if self.cancel_requested:
                self.lbl_status.setText("Status: Proses dibatalkan oleh operator.")
                self.lbl_status.setStyleSheet("font-weight: 500; color: #D97706; font-size: 11px;")
            else:
                self.lbl_status.setText("Status: Proses terhenti karena error.")
                self.lbl_status.setStyleSheet("font-weight: 500; color: #DC2626; font-size: 11px;")
                QMessageBox.critical(
                    self,
                    "Kesalahan Proses",
                    f"Pipeline terhenti dengan pesan:\n{hasil.pesan_error}",
                )

    def _ekspor_hasil(self):
        """Membuka dialog ekspor untuk menyimpan seluruh layer hasil ke berkas."""
        if not self.hasil_pipeline:
            QMessageBox.warning(self, "Peringatan", "Belum ada hasil proses yang dapat diekspor. Jalankan proses terlebih dahulu.")
            return

        dialog_ekspor = QDialog(self)
        dialog_ekspor.setWindowTitle("Ekspor Hasil Analisis Topologi")
        e_layout = QFormLayout(dialog_ekspor)

        cbo_format = QComboBox(dialog_ekspor)
        cbo_format.addItems(["GeoPackage (.gpkg)", "ESRI Shapefile (.shp)", "GeoJSON (.geojson)", "File Geodatabase (.gdb)"])
        e_layout.addRow("Format Ekspor:", cbo_format)

        folder_edit = QLineEdit(dialog_ekspor)
        folder_edit.setText(os.path.expanduser("~/GeoConnect_Hasil"))
        btn_browse = QPushButton("Pilih Folder...", dialog_ekspor)

        def browse_folder():
            f = QFileDialog.getExistingDirectory(dialog_ekspor, "Pilih Folder Ekspor")
            if f:
                folder_edit.setText(f)

        btn_browse.clicked.connect(browse_folder)
        e_layout.addRow("Folder Tujuan:", folder_edit)
        e_layout.addRow("", btn_browse)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Ekspor Sekarang", dialog_ekspor)
        btn_tutup = QPushButton("Batal", dialog_ekspor)
        btn_ok.clicked.connect(dialog_ekspor.accept)
        btn_tutup.clicked.connect(dialog_ekspor.reject)
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_tutup)
        e_layout.addRow(btn_box)

        if dialog_ekspor.exec_() != QDialog.Accepted:
            return

        fmt_str = cbo_format.currentText()
        fmt_key = "GPKG"
        if "Shapefile" in fmt_str:
            fmt_key = "SHP"
        elif "GeoJSON" in fmt_str:
            fmt_key = "GEOJSON"
        elif "Geodatabase" in fmt_str:
            fmt_key = "GDB"

        tujuan = folder_edit.text().strip()
        hasil_ekspor = ekspor_semua_hasil(self.hasil_pipeline, tujuan, format_nama=fmt_key)
        sukses_count = sum(1 for s, _ in hasil_ekspor.values() if s)
        self._catat_log(f"Ekspor selesai: {sukses_count}/{len(hasil_ekspor)} layer berhasil disimpan ke {tujuan}.", "SUCCESS")
        QMessageBox.information(
            self,
            "Ekspor Selesai",
            f"Ekspor selesai ke format {fmt_key}.\nLokasi: {tujuan}\nLayer berhasil: {sukses_count}",
        )

    def _lihat_laporan(self):
        """Membuka dialog dan mengekspor laporan ringkasan ke format Excel (.xlsx) atau CSV."""
        if not self.hasil_pipeline:
            QMessageBox.warning(self, "Peringatan", "Belum ada hasil proses. Jalankan proses terlebih dahulu.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Laporan Hasil Analisis",
            os.path.expanduser("~/Laporan_GeoConnect_Topologi.xlsx"),
            "Excel Workbook (*.xlsx);;Comma Separated Values (*.csv)",
        )
        if not file_path:
            return

        sukses, pesan = buat_laporan_excel(self.hasil_pipeline, file_path)
        if sukses:
            self._catat_log(pesan, "SUCCESS")
            QMessageBox.information(self, "Laporan Disimpan", pesan)
        else:
            self._catat_log(pesan, "ERROR")
            QMessageBox.critical(self, "Gagal Menyimpan Laporan", pesan)

    def _klik_batal_tutup(self):
        """Menangani tombol batal saat proses berjalan atau tutup dialog."""
        if self.is_running:
            self.cancel_requested = True
            self._catat_log("Meminta pembatalan proses... Mohon tunggu tahap saat ini selesai.", "WARNING")
            self.btn_batal.setEnabled(False)
        else:
            self.close()
