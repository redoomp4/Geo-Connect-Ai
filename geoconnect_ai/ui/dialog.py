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
        QScrollArea,
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
        self.layer_gardu = None

    def set_hasil(self, hasil_pipeline, layer_gardu=None):
        """Memperbarui data pratinjau setelah pipeline dijalankan."""
        self.data_hasil = hasil_pipeline
        self.layer_gardu = layer_gardu
        self.update()

    def _gambar_data_nyata(self, p: QPainter, canvas_rect: QRectF, dash_pen: QPen) -> bool:
        """Menggambar geometri nyata dari hasil pipeline jika tersedia."""
        hp = self.data_hasil
        if hp is None or not getattr(hp, "sukses", False):
            return False

        layers_to_check = [
            hp.layer_jtr_snapped,
            hp.layer_dangling,
            hp.layer_sltr_usulan,
            hp.layer_app_anomali,
            getattr(hp, "layer_tiang_hasil", None),
            getattr(hp, "layer_gardu_hasil", None) or self.layer_gardu,
        ]
        valid_layers = [l for l in layers_to_check if l is not None and hasattr(l, "extent") and l.featureCount() > 0]
        if not valid_layers:
            return False

        min_x = min(l.extent().xMinimum() for l in valid_layers)
        max_x = max(l.extent().xMaximum() for l in valid_layers)
        min_y = min(l.extent().yMinimum() for l in valid_layers)
        max_y = max(l.extent().yMaximum() for l in valid_layers)

        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)

        pad = 22.0
        avail_w = max(canvas_rect.width() - 2 * pad, 10.0)
        avail_h = max(canvas_rect.height() - 2 * pad, 10.0)
        scale = min(avail_w / span_x, avail_h / span_y)

        offset_x = canvas_rect.x() + pad + (avail_w - span_x * scale) / 2.0
        offset_y = canvas_rect.y() + pad + (avail_h - span_y * scale) / 2.0

        def to_screen(x: float, y: float) -> QPointF:
            sx = offset_x + (x - min_x) * scale
            sy = offset_y + (max_y - y) * scale
            return QPointF(sx, sy)

        # 1. Gambar JTR Snapping
        if hp.layer_jtr_snapped and hp.layer_jtr_snapped.featureCount() > 0:
            jtr_pen = QPen(QColor(71, 85, 105), 1.8)
            snap_pen = QPen(QColor(6, 214, 160), 2.2)
            for f in hp.layer_jtr_snapped.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                status = f["STATUS"] if f.fields().indexOf("STATUS") != -1 else "UTUH"
                p.setPen(snap_pen if status == "SNAPPED" else jtr_pen)
                pts = geom.asPolyline() if not geom.isMultipart() else (geom.asMultiPolyline()[0] if geom.asMultiPolyline() else [])
                for i in range(len(pts) - 1):
                    p.drawLine(to_screen(pts[i].x(), pts[i].y()), to_screen(pts[i + 1].x(), pts[i + 1].y()))

        # 2. Gambar Penyambungan Dangling
        if hp.layer_dangling and hp.layer_dangling.featureCount() > 0:
            dang_pen = QPen(QColor(0, 180, 216), 1.8)
            dang_pen.setStyle(get_dash_line())
            p.setPen(dang_pen)
            for f in hp.layer_dangling.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                pts = geom.asPolyline()
                for i in range(len(pts) - 1):
                    p.drawLine(to_screen(pts[i].x(), pts[i].y()), to_screen(pts[i + 1].x(), pts[i + 1].y()))

        # 3. Gambar SLTR (ASLI = Hijau limau solid, USULAN = Oranye putus-putus)
        if hp.layer_sltr_usulan and hp.layer_sltr_usulan.featureCount() > 0:
            sltr_asli_pen = QPen(QColor(101, 163, 13), 1.4)
            for f in hp.layer_sltr_usulan.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                status_sltr = f["STATUS"] if f.fields().indexOf("STATUS") != -1 else "USULAN"
                p.setPen(sltr_asli_pen if status_sltr == "ASLI" else dash_pen)
                pts = geom.asPolyline() if not geom.isMultipart() else (geom.asMultiPolyline()[0] if geom.asMultiPolyline() else [])
                for i in range(len(pts) - 1):
                    p.drawLine(to_screen(pts[i].x(), pts[i].y()), to_screen(pts[i + 1].x(), pts[i + 1].y()))

        # 3b. Gambar Titik Tiang TR (Ungu)
        lyr_tiang_p = getattr(hp, "layer_tiang_hasil", None)
        if lyr_tiang_p and lyr_tiang_p.featureCount() > 0:
            p.setBrush(QBrush(QColor(147, 51, 234)))
            p.setPen(QPen(QColor(255, 255, 255), 1.0))
            for f in lyr_tiang_p.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                pt = geom.asPoint()
                p.drawEllipse(to_screen(pt.x(), pt.y()), 4.0, 4.0)

        # 4. Gambar Titik APP (ADA = Hijau, TIDAK ADA = Merah)
        if hp.layer_app_anomali and hp.layer_app_anomali.featureCount() > 0:
            for f in hp.layer_app_anomali.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                pt = geom.asPoint()
                status = f["STATUS"] if f.fields().indexOf("STATUS") != -1 else "ADA"
                if status == "TIDAK ADA":
                    p.setBrush(QBrush(QColor(220, 38, 38)))
                    p.setPen(QPen(QColor(255, 255, 255), 1.0))
                    p.drawEllipse(to_screen(pt.x(), pt.y()), 4.5, 4.5)
                else:
                    p.setBrush(QBrush(QColor(22, 163, 74)))
                    p.setPen(QPen(QColor(255, 255, 255), 0.8))
                    p.drawEllipse(to_screen(pt.x(), pt.y()), 3.2, 3.2)

        # 5. Gambar Titik Gardu
        lyr_gardu_p = getattr(hp, "layer_gardu_hasil", None) or self.layer_gardu
        if lyr_gardu_p and lyr_gardu_p.featureCount() > 0:
            p.setBrush(QBrush(QColor(14, 76, 146)))
            p.setPen(QPen(QColor(255, 255, 255), 1.5))
            for f in lyr_gardu_p.getFeatures():
                geom = f.geometry()
                if not geom or geom.isEmpty():
                    continue
                pt = geom.asPoint()
                p.drawEllipse(to_screen(pt.x(), pt.y()), 6.5, 6.5)

        return True

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

        dash_pen = QPen(QColor(217, 119, 6), 1.8)
        dash_pen.setStyle(get_dash_line())

        if not self._gambar_data_nyata(p, canvas_rect, dash_pen):
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
        self.resize(1060, 760)
        self.setMinimumSize(940, 660)
        self.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 11px; margin-top: 6px; padding-top: 8px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; } "
            "QLabel { font-size: 11px; } "
            "QComboBox, QDoubleSpinBox { min-height: 26px; padding: 2px 6px; font-size: 11px; } "
            "QPushButton { min-height: 26px; padding: 4px 10px; font-size: 11px; } "
            "QCheckBox { font-size: 11px; spacing: 6px; min-height: 20px; }"
        )

        self._setup_ui()
        self._muat_pengaturan()
        self._validasi_input()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 10)
        main_layout.setSpacing(6)

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

        splitter = QSplitter(get_horizontal(), self)

        scroll_left = QScrollArea(splitter)
        scroll_left.setWidgetResizable(True)
        no_frame = getattr(getattr(QFrame, "Shape", None), "NoFrame", getattr(QFrame, "NoFrame", 0))
        scroll_left.setFrameShape(no_frame)
        scroll_left.setMinimumWidth(350)

        left_widget = QWidget(scroll_left)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        gb_layer = QGroupBox("1. Pilih Layer Sumber", left_widget)
        gb_layer_layout = QVBoxLayout(gb_layer)
        gb_layer_layout.setContentsMargins(10, 12, 10, 10)
        gb_layer_layout.setSpacing(5)

        lbl_app = QLabel("Layer APP (kWh meter)", gb_layer)
        self.cbo_app = QgsMapLayerComboBox(gb_layer)
        self.cbo_app.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cbo_app.setMinimumHeight(28)
        gb_layer_layout.addWidget(lbl_app)
        gb_layer_layout.addWidget(self.cbo_app)

        lbl_jtr = QLabel("Layer JTR (Jaringan Tegangan Rendah)", gb_layer)
        self.cbo_jtr = QgsMapLayerComboBox(gb_layer)
        self.cbo_jtr.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.cbo_jtr.setMinimumHeight(28)
        gb_layer_layout.addWidget(lbl_jtr)
        gb_layer_layout.addWidget(self.cbo_jtr)

        lbl_sltr = QLabel("Layer SLTR (Saluran Luar - Opsional)", gb_layer)
        self.cbo_sltr = QgsMapLayerComboBox(gb_layer)
        self.cbo_sltr.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.cbo_sltr.setMinimumHeight(28)
        if hasattr(self.cbo_sltr, "setAllowEmptyLayer"):
            self.cbo_sltr.setAllowEmptyLayer(True)
        if hasattr(self.cbo_sltr, "setShowDefaultOption"):
            self.cbo_sltr.setShowDefaultOption(True)
        gb_layer_layout.addWidget(lbl_sltr)
        gb_layer_layout.addWidget(self.cbo_sltr)

        lbl_gardu = QLabel("Layer Gardu (GARDU_TRAFO)", gb_layer)
        self.cbo_gardu = QgsMapLayerComboBox(gb_layer)
        self.cbo_gardu.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cbo_gardu.setMinimumHeight(28)
        gb_layer_layout.addWidget(lbl_gardu)
        gb_layer_layout.addWidget(self.cbo_gardu)

        lbl_tiang = QLabel("Layer Tiang TR (Opsional)", gb_layer)
        self.cbo_tiang = QgsMapLayerComboBox(gb_layer)
        self.cbo_tiang.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cbo_tiang.setMinimumHeight(28)
        if hasattr(self.cbo_tiang, "setAllowEmptyLayer"):
            self.cbo_tiang.setAllowEmptyLayer(True)
        if hasattr(self.cbo_tiang, "setShowDefaultOption"):
            self.cbo_tiang.setShowDefaultOption(True)
        gb_layer_layout.addWidget(lbl_tiang)
        gb_layer_layout.addWidget(self.cbo_tiang)

        lbl_sumber = QLabel("Sumber Data", gb_layer)
        self.cbo_sumber_data = QComboBox(gb_layer)
        self.cbo_sumber_data.setMinimumHeight(28)
        self.cbo_sumber_data.addItems([
            "Layer Aktif Project QGIS",
            "GeoPackage (*.gpkg)",
            "File Geodatabase (*.gdb)",
            "Shapefile (*.shp)",
            "Excel (.xlsx) / CSV (.csv)",
        ])
        sumber_btn_row = QHBoxLayout()
        self.btn_muat_folder = QPushButton("Muat Folder (.gpkg/.shp)...", gb_layer)
        self.btn_muat_folder.setMinimumHeight(28)
        self.btn_muat_folder.setToolTip("Pilih folder dataset (mis. SBJ0045) untuk memuat otomatis layer APP, JTR, SLTR, Gardu, dan Tiang")
        self.btn_muat_folder.clicked.connect(self._muat_dataset_folder)

        self.btn_muat_tabel = QPushButton("Muat dari Excel/CSV...", gb_layer)
        self.btn_muat_tabel.setMinimumHeight(28)
        self.btn_muat_tabel.setToolTip("Impor tabel koordinat Excel/CSV menjadi layer titik di QGIS")
        self.btn_muat_tabel.clicked.connect(self._muat_dari_excel_csv)

        sumber_btn_row.addWidget(self.btn_muat_folder)
        sumber_btn_row.addWidget(self.btn_muat_tabel)
        gb_layer_layout.addWidget(lbl_sumber)
        gb_layer_layout.addWidget(self.cbo_sumber_data)
        gb_layer_layout.addLayout(sumber_btn_row)

        left_layout.addWidget(gb_layer)

        gb_toleransi = QGroupBox("2. Pengaturan Toleransi", left_widget)
        tol_layout = QVBoxLayout(gb_toleransi)
        tol_layout.setContentsMargins(10, 12, 10, 10)
        tol_layout.setSpacing(5)

        lbl_tol_jtr = QLabel("Toleransi JTR → Gardu", gb_toleransi)
        spin_row_1 = QHBoxLayout()
        self.spin_jtr_gardu = QDoubleSpinBox(gb_toleransi)
        self.spin_jtr_gardu.setMinimumHeight(28)
        self.spin_jtr_gardu.setRange(0.0, 500.0)
        self.spin_jtr_gardu.setValue(10.0)
        self.spin_jtr_gardu.setSingleStep(0.5)
        lbl_m1 = QLabel("meter", gb_toleransi)
        spin_row_1.addWidget(self.spin_jtr_gardu, 1)
        spin_row_1.addWidget(lbl_m1)
        tol_layout.addWidget(lbl_tol_jtr)
        tol_layout.addLayout(spin_row_1)

        lbl_tol_dang = QLabel("Toleransi Dangling Line", gb_toleransi)
        spin_row_2 = QHBoxLayout()
        self.spin_dangling = QDoubleSpinBox(gb_toleransi)
        self.spin_dangling.setMinimumHeight(28)
        self.spin_dangling.setRange(0.0, 500.0)
        self.spin_dangling.setValue(8.0)
        self.spin_dangling.setSingleStep(0.5)
        lbl_m2 = QLabel("meter", gb_toleransi)
        spin_row_2.addWidget(self.spin_dangling, 1)
        spin_row_2.addWidget(lbl_m2)
        tol_layout.addWidget(lbl_tol_dang)
        tol_layout.addLayout(spin_row_2)

        lbl_tol_app = QLabel("Toleransi APP → Jaringan (Cover)", gb_toleransi)
        spin_row_3 = QHBoxLayout()
        self.spin_app_cover = QDoubleSpinBox(gb_toleransi)
        self.spin_app_cover.setMinimumHeight(28)
        self.spin_app_cover.setRange(0.0, 100.0)
        self.spin_app_cover.setValue(0.5)
        self.spin_app_cover.setSingleStep(0.1)
        lbl_m3 = QLabel("meter", gb_toleransi)
        spin_row_3.addWidget(self.spin_app_cover, 1)
        spin_row_3.addWidget(lbl_m3)
        tol_layout.addWidget(lbl_tol_app)
        tol_layout.addLayout(spin_row_3)

        lbl_tol_usul = QLabel("Jarak Maksimal Usulan SLTR", gb_toleransi)
        spin_row_4 = QHBoxLayout()
        self.spin_usulan_maks = QDoubleSpinBox(gb_toleransi)
        self.spin_usulan_maks.setMinimumHeight(28)
        self.spin_usulan_maks.setRange(0.0, 1000.0)
        self.spin_usulan_maks.setValue(50.0)
        self.spin_usulan_maks.setSingleStep(5.0)
        lbl_m4 = QLabel("meter", gb_toleransi)
        spin_row_4.addWidget(self.spin_usulan_maks, 1)
        spin_row_4.addWidget(lbl_m4)
        tol_layout.addWidget(lbl_tol_usul)
        tol_layout.addLayout(spin_row_4)

        lbl_crs_kerja = QLabel("CRS Kerja (Meter)", gb_toleransi)
        self.cbo_crs_kerja = QComboBox(gb_toleransi)
        self.cbo_crs_kerja.setMinimumHeight(28)
        self.cbo_crs_kerja.addItems([
            "Otomatis (UTM / CRS Proyeksi Layer)",
            "EPSG:32750 — WGS 84 / UTM zone 50S (Kaltim)",
            "EPSG:32650 — WGS 84 / UTM zone 50N (Kaltara)",
            "EPSG:3857 — WGS 84 / Pseudo-Mercator",
        ])
        tol_layout.addWidget(lbl_crs_kerja)
        tol_layout.addWidget(self.cbo_crs_kerja)

        left_layout.addWidget(gb_toleransi)

        gb_proses = QGroupBox("3. Proses yang Dijalankan", left_widget)
        vbox_proses = QVBoxLayout(gb_proses)
        vbox_proses.setContentsMargins(10, 12, 10, 10)
        vbox_proses.setSpacing(5)

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
        scroll_left.setWidget(left_widget)

        right_widget = QWidget(splitter)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        gb_preview = QGroupBox("Pratinjau Kanvas QGIS", right_widget)
        vbox_preview = QVBoxLayout(gb_preview)
        vbox_preview.setContentsMargins(6, 6, 6, 6)

        self.kanvas_preview = PratinjauKanvasWidget(gb_preview)
        vbox_preview.addWidget(self.kanvas_preview)
        right_layout.addWidget(gb_preview, 5)

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

        self._tampilkan_log_awal()

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

        splitter.addWidget(scroll_left)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter, 1)

        bottom_widget = QWidget(self)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 8, 0, 2)

        self.lbl_status = QLabel("Status: Siap. Pilih layer dan klik Jalankan Proses.", bottom_widget)
        self.lbl_status.setStyleSheet("font-weight: 500; color: #059669; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)
        bottom_layout.addStretch()

        self.btn_jalankan = QPushButton("Jalankan Proses", bottom_widget)
        self.btn_jalankan.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; font-weight: bold; "
            "padding: 7px 18px; border-radius: 4px; border: 1px solid #005A9E; font-size: 12px; } "
            "QPushButton:hover { background-color: #106EBE; } "
            "QPushButton:disabled { background-color: #94A3B8; border-color: #CBD5E1; }"
        )
        self.btn_jalankan.clicked.connect(self._jalankan_proses)
        bottom_layout.addWidget(self.btn_jalankan)

        self.btn_ekspor = QPushButton("Ekspor Hasil", bottom_widget)
        self.btn_ekspor.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_ekspor.clicked.connect(self._ekspor_hasil)
        bottom_layout.addWidget(self.btn_ekspor)

        self.btn_laporan = QPushButton("Lihat Laporan", bottom_widget)
        self.btn_laporan.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_laporan.clicked.connect(self._lihat_laporan)
        bottom_layout.addWidget(self.btn_laporan)

        self.btn_batal = QPushButton("Batal", bottom_widget)
        self.btn_batal.setStyleSheet("padding: 7px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_batal.clicked.connect(self._klik_batal_tutup)
        bottom_layout.addWidget(self.btn_batal)

        main_layout.addWidget(bottom_widget)

        self.cbo_gardu.layerChanged.connect(self._validasi_input)
        self.cbo_jtr.layerChanged.connect(self._validasi_input)
        self.cbo_app.layerChanged.connect(self._validasi_input)
        if hasattr(self, "cbo_sltr"):
            self.cbo_sltr.layerChanged.connect(self._validasi_input)

        self._auto_deteksi_layer_pln()

        try:
            QgsProject.instance().layersAdded.connect(self._saat_layer_ditambahkan)
        except Exception:
            pass

    def _saat_layer_ditambahkan(self, *args):
        """Callback saat layer baru masuk ke project: perbarui pilihan dropdown otomatis."""
        if self.is_running:
            return
        try:
            self._auto_deteksi_layer_pln()
            self._validasi_input()
        except RuntimeError:
            # Dialog sudah dihapus oleh Qt
            pass

    # Nama layer keluaran plugin sendiri — tidak boleh dipilih sebagai layer sumber
    NAMA_LAYER_HASIL = {
        "app anomali", "sltr usulan", "penyambungan dangling",
        "jtr snapping", "gardu distribusi", "tiang tr",
    }

    @staticmethod
    def _tipe_geom(lyr) -> int:
        """Mengembalikan tipe geometri layer sebagai int (0=titik, 1=garis, 2=poligon, -1=lainnya)."""
        if not hasattr(lyr, "geometryType"):
            return -1
        gt = lyr.geometryType()
        val = getattr(gt, "value", gt)
        try:
            return int(val)
        except (TypeError, ValueError):
            return -1

    def _auto_deteksi_layer_pln(self, paksa: bool = False):
        """Mendeteksi dan memilih layer secara otomatis berdasarkan pola nama layer PLN.

        QgsMapLayerComboBox selalu memilih layer pertama secara default (mis. APP1 ikut
        terpilih di dropdown Gardu/Tiang). Karena itu setiap dropdown dicek: jika layer
        yang sedang terpilih tidak cocok dengan perannya, diganti dengan layer yang cocok.
        Dropdown opsional (SLTR, Tiang) dikosongkan bila tidak ada layer yang cocok.
        """
        try:
            layers = [
                l for l in QgsProject.instance().mapLayers().values()
                if self._tipe_geom(l) in (0, 1)
                and l.name().strip().lower() not in self.NAMA_LAYER_HASIL
            ]
        except Exception:
            return

        p_app = ["app", "kwh", "pelanggan", "meter"]
        p_gardu = ["gardu", "trafo", "transformer"]
        p_jtr = ["jtr", "tegangan_rendah", "low_voltage"]
        p_sltr = ["sltr", "sambungan_luar", "sambungan_rumah"]
        p_tiang = ["tiang", "pole", "tumpu"]

        def ada(nama, pola):
            return any(k in nama for k in pola)

        def cek_app(n):
            return ada(n, p_app) and not ada(n, p_gardu) and not ada(n, p_tiang)

        def cek_gardu(n):
            return ada(n, p_gardu) and not ada(n, p_tiang)

        def cek_tiang(n):
            return ada(n, p_tiang)

        def cek_jtr(n):
            return ada(n, p_jtr) and not ada(n, p_sltr)

        def cek_sltr(n):
            return ada(n, p_sltr)

        peran = [
            (self.cbo_app, 0, cek_app, False),
            (self.cbo_gardu, 0, cek_gardu, False),
            (self.cbo_jtr, 1, cek_jtr, False),
            (getattr(self, "cbo_sltr", None), 1, cek_sltr, True),
            (getattr(self, "cbo_tiang", None), 0, cek_tiang, True),
        ]

        for cbo, tipe, cek, opsional in peran:
            if cbo is None:
                continue
            sekarang = cbo.currentLayer()
            if (
                not paksa
                and sekarang is not None
                and sekarang.name().strip().lower() not in self.NAMA_LAYER_HASIL
                and cek(sekarang.name().lower())
            ):
                continue  # Pilihan saat ini sudah sesuai peran

            kandidat = sorted(
                [l for l in layers if self._tipe_geom(l) == tipe and cek(l.name().lower())],
                key=lambda l: l.name().lower(),
            )
            if kandidat:
                cbo.setLayer(kandidat[0])
            elif opsional:
                cbo.setLayer(None)

    def _muat_dataset_folder(self):
        """Memuat berkas spasial (.gpkg / .shp) dari sebuah folder dataset (seperti SBJ0045) ke dalam QGIS."""
        default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "SBJ0045"))
        if not os.path.exists(default_dir):
            default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Pilih Folder Dataset Jaringan PLN (misal: SBJ0045)",
            default_dir,
        )
        if not folder_path:
            return

        dimuat = 0
        for fname in sorted(os.listdir(folder_path)):
            if not fname.lower().endswith((".gpkg", ".shp", ".geojson")):
                continue
            fpath = os.path.join(folder_path, fname)
            layer_name = os.path.splitext(fname)[0]
            lyr = QgsVectorLayer(fpath, layer_name, "ogr")
            if lyr.isValid():
                QgsProject.instance().addMapLayer(lyr)
                dimuat += 1

        if dimuat > 0:
            self._catat_log(f"Berhasil memuat {dimuat} layer dari folder: {os.path.basename(folder_path)}", "SUCCESS")
            self.lbl_project.setText(os.path.basename(folder_path))
            # Paksa auto-deteksi ulang untuk seluruh dropdown sesuai dataset yang baru dimuat
            self._auto_deteksi_layer_pln(paksa=True)
            self._validasi_input()
        else:
            QMessageBox.warning(
                self,
                "Tidak Ada Layer",
                f"Tidak ditemukan berkas layer valid (.gpkg/.shp/.geojson) di dalam folder:\n{folder_path}",
            )

    def _muat_dari_excel_csv(self):
        """Membuka dialog impor file Excel (.xlsx) atau CSV (.csv) menjadi layer titik di QGIS."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih Berkas Tabel Koordinat (Excel / CSV)",
            os.path.expanduser("~"),
            "Tabel Koordinat (*.xlsx *.csv *.xls);;Semua Berkas (*.*)",
        )
        if not file_path:
            return

        tbl_layer = QgsVectorLayer(file_path, os.path.splitext(os.path.basename(file_path))[0], "ogr")
        if not tbl_layer.isValid():
            QMessageBox.critical(self, "Gagal Membuka Berkas", f"Berkas tidak dapat dibuka oleh OGR:\n{file_path}")
            return

        field_names = [f.name() for f in tbl_layer.fields()]
        if not field_names:
            QMessageBox.warning(self, "Tabel Kosong", "Tidak ditemukan kolom atribut pada berkas tersebut.")
            return

        dlg_imp = QDialog(self)
        dlg_imp.setWindowTitle("Impor Titik dari Excel / CSV")
        form = QFormLayout(dlg_imp)

        cbo_x = QComboBox(dlg_imp)
        cbo_x.addItems(field_names)
        cbo_y = QComboBox(dlg_imp)
        cbo_y.addItems(field_names)
        cbo_crs = QComboBox(dlg_imp)
        cbo_crs.addItems(["EPSG:4326 (WGS 84 Derajat)", "EPSG:32750 (UTM 50S Meter)", "EPSG:3857 (Pseudo-Mercator)"])

        # Auto-select kolom X/LONG dan Y/LAT jika ada
        for idx, fn in enumerate(field_names):
            fl = fn.lower()
            if fl in ("long", "lon", "longitude", "longitudex", "x", "koordinat_x"):
                cbo_x.setCurrentIndex(idx)
            if fl in ("lat", "latitude", "latitudey", "y", "koordinat_y"):
                cbo_y.setCurrentIndex(idx)

        form.addRow("Kolom Bujur / X:", cbo_x)
        form.addRow("Kolom Lintang / Y:", cbo_y)
        form.addRow("CRS Koordinat:", cbo_crs)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Buat Layer Titik", dlg_imp)
        btn_cancel = QPushButton("Batal", dlg_imp)
        btn_ok.clicked.connect(dlg_imp.accept)
        btn_cancel.clicked.connect(dlg_imp.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        form.addRow(btn_row)

        eq_fn = getattr(dlg_imp, "exec", getattr(dlg_imp, "exec_", None))
        if not eq_fn or eq_fn() != getattr(QDialog, "Accepted", 1):
            return

        col_x = cbo_x.currentText()
        col_y = cbo_y.currentText()
        crs_auth = cbo_crs.currentText().split(" ")[0]

        try:
            from qgis import processing
            res = processing.run(
                "native:createpointslayerfromtable",
                {
                    "INPUT": tbl_layer,
                    "XFIELD": col_x,
                    "YFIELD": col_y,
                    "TARGET_CRS": QgsCoordinateReferenceSystem(crs_auth),
                    "OUTPUT": "memory:",
                },
            )
            out_lyr = res.get("OUTPUT")
            if out_lyr and out_lyr.isValid():
                out_lyr.setName(os.path.splitext(os.path.basename(file_path))[0])
                QgsProject.instance().addMapLayer(out_lyr)
                self._catat_log(f"Layer titik '{out_lyr.name()}' berhasil dibuat dari Excel/CSV.", "SUCCESS")
                self._auto_deteksi_layer_pln()
                self._validasi_input()
                return
        except Exception:
            pass

        # Fallback manual jika modul processing tidak aktif
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
        pt_lyr = QgsVectorLayer(f"Point?crs={crs_auth}", os.path.splitext(os.path.basename(file_path))[0], "memory")
        pr = pt_lyr.dataProvider()
        pr.addAttributes(tbl_layer.fields().toList())
        pt_lyr.updateFields()
        feats = []
        for f in tbl_layer.getFeatures():
            try:
                xv = float(f[col_x])
                yv = float(f[col_y])
                nf = QgsFeature(pt_lyr.fields())
                nf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(xv, yv)))
                nf.setAttributes(f.attributes())
                feats.append(nf)
            except (ValueError, TypeError):
                continue
        pr.addFeatures(feats)
        pt_lyr.updateExtents()
        QgsProject.instance().addMapLayer(pt_lyr)
        self._catat_log(f"Layer titik '{pt_lyr.name()}' ({len(feats)} fitur) berhasil dimuat dari Excel/CSV.", "SUCCESS")
        self._auto_deteksi_layer_pln()
        self._validasi_input()

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
        self.settings.setValue("GeoConnectAI/app_usulan_maks_m", self.spin_usulan_maks.value())

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
        val = self.settings.value("GeoConnectAI/app_cover_m", 0.5, type=float)
        self.spin_app_cover.setValue(val)
        val = self.settings.value("GeoConnectAI/app_usulan_maks_m", 50.0, type=float)
        self.spin_usulan_maks.setValue(val)

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
        config.layer_tiang = self.cbo_tiang.currentLayer() if hasattr(self, "cbo_tiang") else None

        config.toleransi = ToleransiConfig(
            jtr_gardu_m=self.spin_jtr_gardu.value(),
            dangling_m=self.spin_dangling.value(),
            app_cover_m=self.spin_app_cover.value(),
            app_usulan_maks_m=self.spin_usulan_maks.value(),
        )

        crs_pilihan = self.cbo_crs_kerja.currentText() if hasattr(self, "cbo_crs_kerja") else ""
        if crs_pilihan.startswith("EPSG:"):
            config.crs_kerja_auth_id = crs_pilihan.split(" ")[0]
        else:
            config.crs_kerja_auth_id = None

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
            self.kanvas_preview.set_hasil(hasil, layer_gardu=config.layer_gardu)

            QMessageBox.information(
                self,
                "GeoConnect-AI Selesai",
                f"Proses otomatisasi topologi berhasil diselesaikan!\n\n"
                f"- Ujung JTR Ter-snap: {r.get('jtr_snapped', 0)}\n"
                f"- Dangling Tersambung: {r.get('dangling_tersambung', 0)}\n"
                f"- APP Anomali (TIDAK ADA): {anomali_count}\n"
                f"- Usulan SLTR Dibuat: {usulan_count}\n\n"
                f"Hasil telah ditampilkan di kanvas QGIS dalam grup '{hasil.nama_grup_hasil or 'master_done'}'.",
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

        eq_fn = getattr(dialog_ekspor, "exec", getattr(dialog_ekspor, "exec_", None))
        if not eq_fn or eq_fn() != getattr(QDialog, "Accepted", 1):
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
        """Membuka jendela pratinjau laporan ringkasan dan opsi ekspor ke Excel (.xlsx) atau CSV."""
        if not self.hasil_pipeline:
            QMessageBox.warning(self, "Peringatan", "Belum ada hasil proses. Jalankan proses terlebih dahulu.")
            return

        dlg_lap = QDialog(self)
        dlg_lap.setWindowTitle("Laporan Ringkasan Analisis Topologi GeoConnect-AI")
        dlg_lap.resize(620, 480)
        v_layout = QVBoxLayout(dlg_lap)

        txt_ringkasan = QPlainTextEdit(dlg_lap)
        txt_ringkasan.setReadOnly(True)
        txt_ringkasan.setStyleSheet(
            "background-color: #0F172A; color: #F8FAFC; "
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; padding: 10px;"
        )
        txt_ringkasan.setPlainText(buat_ringkasan_teks(self.hasil_pipeline))
        v_layout.addWidget(txt_ringkasan)

        btn_row = QHBoxLayout()
        btn_simpan = QPushButton("Simpan ke Excel (.xlsx) / CSV...", dlg_lap)
        btn_simpan.setStyleSheet(
            "background-color: #0078D7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        btn_tutup = QPushButton("Tutup", dlg_lap)
        btn_tutup.setStyleSheet("padding: 6px 14px; border-radius: 4px;")

        def simpan_file():
            file_path, _ = QFileDialog.getSaveFileName(
                dlg_lap,
                "Simpan Laporan Hasil Analisis",
                os.path.expanduser("~/Laporan_GeoConnect_Topologi.xlsx"),
                "Excel Workbook (*.xlsx);;Comma Separated Values (*.csv)",
            )
            if not file_path:
                return
            sukses, pesan = buat_laporan_excel(self.hasil_pipeline, file_path)
            if sukses:
                self._catat_log(pesan, "SUCCESS")
                QMessageBox.information(dlg_lap, "Laporan Disimpan", pesan)
            else:
                self._catat_log(pesan, "ERROR")
                QMessageBox.critical(dlg_lap, "Gagal Menyimpan Laporan", pesan)

        btn_simpan.clicked.connect(simpan_file)
        btn_tutup.clicked.connect(dlg_lap.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_simpan)
        btn_row.addWidget(btn_tutup)
        v_layout.addLayout(btn_row)

        eq_fn = getattr(dlg_lap, "exec", getattr(dlg_lap, "exec_", None))
        if eq_fn:
            eq_fn()

    def _klik_batal_tutup(self):
        """Menangani tombol batal saat proses berjalan atau tutup dialog."""
        if self.is_running:
            self.cancel_requested = True
            self._catat_log("Meminta pembatalan proses... Mohon tunggu tahap saat ini selesai.", "WARNING")
            self.btn_batal.setEnabled(False)
        else:
            self.close()
