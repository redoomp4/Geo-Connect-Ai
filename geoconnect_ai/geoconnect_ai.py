"""Modul utama integrasi QGIS untuk GeoConnect-AI.

Mengelola siklus hidup plugin (initGui, unload, run), registrasi menu,
serta pembukaan dialog antarmuka utama.
"""

import os
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .ui.dialog import GeoConnectAIDialog


class GeoConnectAI:
    """Kelas utama plugin GeoConnect-AI untuk QGIS."""

    def __init__(self, iface):
        """Konstruktor plugin GeoConnect-AI.

        Args:
            iface (QgisInterface): Antarmuka QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.menu_name = "&GeoConnect-AI"
        self.dialog = None

    def tr(self, message):
        """Fungsi helper terjemahan i18n."""
        return QCoreApplication.translate("GeoConnectAI", message)

    def initGui(self):
        """Membuat action, ikon toolbar, dan entri menu pada QGIS."""
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, self.tr("GeoConnect-AI"), self.iface.mainWindow())
        self.action.setStatusTip(
            self.tr("Otomatisasi Topologi Jaringan APP-SLTR-JTR-Gardu (PLN UID Kaltimtara)")
        )
        self.action.triggered.connect(self.run)

        # Tambahkan ke toolbar dan menu Plugins
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(self.menu_name, self.action)

    def unload(self):
        """Membersihkan action, toolbar, dan menu saat plugin dinonaktifkan."""
        if self.action:
            self.iface.removePluginMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            del self.action
            self.action = None

        if self.dialog:
            self.dialog.close()
            self.dialog = None

    def run(self):
        """Membuka atau mengaktifkan dialog utama GeoConnect-AI."""
        if self.dialog is None:
            self.dialog = GeoConnectAIDialog(parent=self.iface.mainWindow(), iface=self.iface)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
