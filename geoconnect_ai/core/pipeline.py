"""Modul orkestrasi pipeline eksekusi topologi GeoConnect-AI.

Menjalankan seluruh tahapan topologi dalam satu klik (one-click action):
Validasi -> Proyeksi CRS Kerja -> Snapping JTR -> Dangling Line ->
Komponen Aktif -> Deteksi Anomali APP -> SLTR Usulan -> Styling -> Layer Group.
Mendukung callback progres, pembatalan (cancellation), dan logging aman.
"""

import time
from typing import Any, Callable, Dict, List, Optional

try:
    from qgis.core import (
        QgsCoordinateTransform,
        QgsFeature,
        QgsGeometry,
        QgsMessageLog,
        QgsProject,
        QgsVectorLayer,
        Qgis,
    )
except ImportError:
    QgsCoordinateTransform = None
    QgsFeature = None
    QgsGeometry = None
    QgsMessageLog = None
    QgsProject = None
    QgsVectorLayer = None
    Qgis = None

from .anomali_app import deteksi_anomali_app
from .config import HasilPipeline, PipelineConfig
from .crs_utils import buat_transformasi, tentukan_crs_kerja
from .dangling import deteksi_dangling, sambung_dangling
from .graph_builder import (
    bangun_graf,
    cari_connected_components,
    tandai_komponen_aktif,
)
from .layer_group import kelompokkan_layer
from .snapping import auto_snap_jtr_ke_gardu
from .styler import (
    terapkan_style_app_anomali,
    terapkan_style_dangling,
    terapkan_style_jtr_snapping,
    terapkan_style_sltr_usulan,
)
from .usulan import buat_sltr_usulan
from .validator import validasi_data


def log_pesan(pesan: str, level: str = "INFO", log_cb: Optional[Callable[[str, str], None]] = None):
    """Mencatat pesan ke log callback UI dan QgsMessageLog."""
    if log_cb:
        log_cb(pesan, level)

    if QgsMessageLog and Qgis:
        lvl_qgis = Qgis.MessageLevel.Info
        if level == "WARNING":
            lvl_qgis = Qgis.MessageLevel.Warning
        elif level == "ERROR":
            lvl_qgis = Qgis.MessageLevel.Critical
        elif level == "SUCCESS":
            lvl_qgis = Qgis.MessageLevel.Success
        QgsMessageLog.logMessage(pesan, "GeoConnect-AI", lvl_qgis)


def salin_dan_transformasi_fitur(daftar_fitur, transform):
    """Menyalin fitur dan mentransformasikan geometrinya ke CRS kerja jika transform aktif."""
    if not transform:
        return list(daftar_fitur)

    hasil_fitur = []
    for f in daftar_fitur:
        geom = f.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        geom_salinan = QgsGeometry(geom)
        geom_salinan.transform(transform)

        f_baru = QgsFeature(f)
        f_baru.setGeometry(geom_salinan)
        hasil_fitur.append(f_baru)

    return hasil_fitur


def jalankan_pipeline(
    config: PipelineConfig,
    progress_cb: Optional[Callable[[int, str], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
    log_cb: Optional[Callable[[str, str], None]] = None,
) -> HasilPipeline:
    """Menjalankan seluruh alur kerja perbaikan topologi GeoConnect-AI.

    Args:
        config: Konfigurasi pipeline lengkap.
        progress_cb: Callback (persen: int, pesan: str).
        cancel_cb: Callback () -> bool untuk mendeteksi pembatalan pengguna.
        log_cb: Callback (pesan: str, level: str) untuk pencatatan log UI.

    Returns:
        HasilPipeline: Hasil eksekusi pipeline lengkap.
    """
    waktu_mulai = time.time()
    hasil = HasilPipeline()

    def cek_batal() -> bool:
        if cancel_cb and cancel_cb():
            log_pesan("Proses dibatalkan oleh pengguna.", "WARNING", log_cb)
            hasil.sukses = False
            hasil.pesan_error = "Dibatalkan oleh pengguna."
            return True
        return False

    def update_progress(persen: int, teks: str):
        if progress_cb:
            progress_cb(persen, teks)
        log_pesan(teks, "INFO", log_cb)

    try:
        log_pesan("Memulai pipeline topologi GeoConnect-AI...", "INFO", log_cb)
        update_progress(5, "Tahap 1/8: Memvalidasi data masukan...")

        # 1. Validasi data sumber secara non-destruktif
        val_gardu = validasi_data(config.layer_gardu, "GARDU", config.field_id_gardu)
        val_jtr = validasi_data(config.layer_jtr, "JTR", config.field_id_jtr)
        val_sltr = (
            validasi_data(config.layer_sltr, "SLTR", config.field_id_sltr)
            if config.layer_sltr
            else None
        )
        val_app = validasi_data(config.layer_app, "APP", config.field_id_app)

        data_bermasalah = []
        data_bermasalah.extend(val_gardu.bermasalah)
        data_bermasalah.extend(val_jtr.bermasalah)
        if val_sltr:
            data_bermasalah.extend(val_sltr.bermasalah)
        data_bermasalah.extend(val_app.bermasalah)
        hasil.data_bermasalah = data_bermasalah

        total_diproses = (
            len(val_gardu.valid)
            + len(val_jtr.valid)
            + (len(val_sltr.valid) if val_sltr else 0)
            + len(val_app.valid)
            + len(data_bermasalah)
        )
        total_valid = total_diproses - len(data_bermasalah)

        log_pesan(
            f"Validasi selesai: {total_valid} fitur valid, {len(data_bermasalah)} bermasalah disaring.",
            "SUCCESS" if len(data_bermasalah) == 0 else "WARNING",
            log_cb,
        )

        if cek_batal():
            return hasil

        # 2. Penentuan dan transformasi CRS kerja (meter)
        update_progress(15, "Tahap 2/8: Menentukan CRS kerja terproyeksi (meter)...")
        crs_kerja = tentukan_crs_kerja(
            layer_jtr=config.layer_jtr,
            layer_gardu=config.layer_gardu,
            layer_app=config.layer_app,
            override_crs_auth_id=config.crs_kerja_auth_id,
        )
        log_pesan(f"CRS kerja yang digunakan: {crs_kerja.authid()} ({crs_kerja.description()})", "INFO", log_cb)

        # Siapkan transform ke CRS kerja untuk tiap layer
        t_gardu = buat_transformasi(config.layer_gardu.crs(), crs_kerja) if config.layer_gardu else None
        t_jtr = buat_transformasi(config.layer_jtr.crs(), crs_kerja) if config.layer_jtr else None
        t_sltr = buat_transformasi(config.layer_sltr.crs(), crs_kerja) if config.layer_sltr else None
        t_app = buat_transformasi(config.layer_app.crs(), crs_kerja) if config.layer_app else None

        # Salin fitur ke CRS kerja (layer sumber asli tidak disentuh)
        fitur_gardu = salin_dan_transformasi_fitur(val_gardu.valid, t_gardu)
        fitur_jtr = salin_dan_transformasi_fitur(val_jtr.valid, t_jtr)
        fitur_sltr = salin_dan_transformasi_fitur(val_sltr.valid, t_sltr) if val_sltr else []
        fitur_app = salin_dan_transformasi_fitur(val_app.valid, t_app)

        if cek_batal():
            return hasil

        # 3. Auto-snapping JTR ke Gardu
        fitur_jtr_aktif = fitur_jtr
        jtr_snapped_count = 0
        jtr_utuh_count = len(fitur_jtr)

        if config.proses_snapping:
            update_progress(25, "Tahap 3/8: Menjalankan auto-snapping JTR ke Gardu...")
            hasil_snap = auto_snap_jtr_ke_gardu(
                daftar_jtr=fitur_jtr,
                daftar_gardu=fitur_gardu,
                toleransi_m=config.toleransi.jtr_gardu_m,
                field_id_jtr=config.field_id_jtr,
                field_id_gardu=config.field_id_gardu,
                crs=crs_kerja,
            )
            hasil.layer_jtr_snapped = hasil_snap.layer_hasil
            fitur_jtr_aktif = hasil_snap.fitur_hasil
            jtr_snapped_count = hasil_snap.jumlah_snapped
            jtr_utuh_count = hasil_snap.jumlah_utuh
            log_pesan(
                f"Snapping JTR selesai: {jtr_snapped_count} ujung di-snap ke Gardu, {jtr_utuh_count} segmen utuh.",
                "SUCCESS",
                log_cb,
            )

        if cek_batal():
            return hasil

        # 4. Bangun graf dan Deteksi + Penyambungan Dangling
        dangling_terdeteksi = 0
        dangling_tersambung = 0
        dangling_tak_tersambung = 0
        fitur_garis_penghubung = []

        if config.proses_dangling:
            update_progress(40, "Tahap 4/8: Memeriksa dan menyambungkan garis dangling...")
            dangling_list = deteksi_dangling(
                daftar_jtr=fitur_jtr_aktif,
                daftar_gardu=fitur_gardu,
                epsilon_m=config.toleransi.epsilon_node_m,
                field_id_jtr=config.field_id_jtr,
                field_id_gardu=config.field_id_gardu,
            )
            dangling_terdeteksi = len(dangling_list)

            hasil_dangling = sambung_dangling(
                daftar_dangling=dangling_list,
                daftar_jtr=fitur_jtr_aktif,
                toleransi_m=config.toleransi.dangling_m,
                field_id_jtr=config.field_id_jtr,
                crs=crs_kerja,
            )
            hasil.layer_dangling = hasil_dangling.layer_hasil
            dangling_tersambung = hasil_dangling.jumlah_tersambung
            dangling_tak_tersambung = hasil_dangling.jumlah_tidak_tersambung
            fitur_garis_penghubung = hasil_dangling.fitur_penghubung
            log_pesan(
                f"Analisis Dangling selesai: {dangling_terdeteksi} terdeteksi, {dangling_tersambung} tersambung.",
                "SUCCESS",
                log_cb,
            )

        if cek_batal():
            return hasil

        # 5. Bangun ulang graf keterhubungan dan tandai jaringan aktif
        update_progress(55, "Tahap 5/8: Menganalisis jaringan aktif yang terhubung ke Gardu...")
        gabungan_segmen_jtr = list(fitur_jtr_aktif) + list(fitur_garis_penghubung)

        graf = bangun_graf(
            daftar_segmen=gabungan_segmen_jtr,
            daftar_gardu=fitur_gardu,
            epsilon=config.toleransi.epsilon_node_m,
        )
        daftar_komponen = cari_connected_components(graf)

        aktif_comp_ids, aktif_segmen_ids = tandai_komponen_aktif(
            graf=graf,
            daftar_komponen=daftar_komponen,
            log_cb=lambda msg: log_pesan(msg, "WARNING", log_cb),
        )

        # Filter kumpulan segmen yang berada pada jaringan aktif saja
        segmen_jaringan_aktif = [
            s for s in gabungan_segmen_jtr if s.id() in aktif_segmen_ids
        ]
        # Jika fallback tidak menemukan segmen aktif, gunakan semua segmen JTR
        if not segmen_jaringan_aktif:
            segmen_jaringan_aktif = gabungan_segmen_jtr

        log_pesan(
            f"Analisis topologi graf: {len(daftar_komponen)} komponen terdeteksi, {len(segmen_jaringan_aktif)} segmen pada jaringan aktif.",
            "INFO",
            log_cb,
        )

        if cek_batal():
            return hasil

        # 6. Deteksi anomali keterhubungan APP
        app_total = len(fitur_app)
        app_ada = 0
        app_tidak_ada = 0
        sltr_usulan_dibuat = 0
        app_tanpa_usulan = 0

        if config.proses_anomali_app:
            update_progress(70, "Tahap 6/8: Menganalisis anomali keterhubungan APP (kWh meter)...")
            # Gabungan garis jaringan untuk deteksi cover: JTR aktif + SLTR asli
            gabungan_garis_cover = list(gabungan_segmen_jtr) + list(fitur_sltr)

            hasil_anomali = deteksi_anomali_app(
                daftar_app=fitur_app,
                daftar_jaringan=gabungan_garis_cover,
                app_cover_m=config.toleransi.app_cover_m,
                field_id_app=config.field_id_app,
                field_id_jaringan=config.field_id_jtr,
                crs=crs_kerja,
            )
            hasil.layer_app_anomali = hasil_anomali.layer_hasil
            app_ada = hasil_anomali.jumlah_ada
            app_tidak_ada = hasil_anomali.jumlah_tidak_ada

            log_pesan(
                f"Keterhubungan APP: {app_ada} ADA (tersambung), {app_tidak_ada} TIDAK ADA (anomali).",
                "SUCCESS" if app_tidak_ada == 0 else "WARNING",
                log_cb,
            )

            # 7. Pembuatan SLTR Usulan HANYA ke jaringan aktif
            update_progress(80, "Tahap 7/8: Membuat usulan sambungan SLTR untuk APP anomali...")
            hasil_usulan = buat_sltr_usulan(
                daftar_app_anomali=hasil_anomali.detail_app,
                daftar_jaringan_aktif=segmen_jaringan_aktif,
                app_usulan_maks_m=config.toleransi.app_usulan_maks_m,
                field_id_jaringan=config.field_id_jtr,
                crs=crs_kerja,
            )
            hasil.layer_sltr_usulan = hasil_usulan.layer_hasil
            sltr_usulan_dibuat = hasil_usulan.jumlah_usulan
            app_tanpa_usulan = hasil_usulan.jumlah_tanpa_usulan

            log_pesan(
                f"Usulan SLTR: {sltr_usulan_dibuat} usulan dibuat ke jaringan aktif, {app_tanpa_usulan} tanpa usulan (jarak > {config.toleransi.app_usulan_maks_m}m).",
                "SUCCESS",
                log_cb,
            )

        if cek_batal():
            return hasil

        # 8. Styling visual tematik
        if config.proses_styling:
            update_progress(90, "Tahap 8/8: Menerapkan styling visual tematik...")
            if hasil.layer_app_anomali:
                terapkan_style_app_anomali(hasil.layer_app_anomali)
            if hasil.layer_sltr_usulan:
                terapkan_style_sltr_usulan(hasil.layer_sltr_usulan)
            if hasil.layer_dangling:
                terapkan_style_dangling(hasil.layer_dangling)
            if hasil.layer_jtr_snapped:
                terapkan_style_jtr_snapping(hasil.layer_jtr_snapped)

        # 9. Kelompokkan ke Layer Tree Group
        if config.proses_layer_group:
            kelompokkan_layer(
                layer_jtr_snapped=hasil.layer_jtr_snapped,
                layer_dangling=hasil.layer_dangling,
                layer_app_anomali=hasil.layer_app_anomali,
                layer_sltr_usulan=hasil.layer_sltr_usulan,
            )
            log_pesan("Layer hasil dikelompokkan ke dalam Layer Group teratas.", "INFO", log_cb)

        # Susun ringkasan akhir
        hasil.waktu_eksekusi_detik = time.time() - waktu_mulai
        hasil.ringkasan = {
            "total_data_diproses": total_diproses,
            "total_data_valid": total_valid,
            "total_data_bermasalah": len(data_bermasalah),
            "jtr_snapped": jtr_snapped_count,
            "jtr_utuh": jtr_utuh_count,
            "dangling_terdeteksi": dangling_terdeteksi,
            "dangling_tersambung": dangling_tersambung,
            "dangling_tak_tersambung": dangling_tak_tersambung,
            "app_total": app_total,
            "app_ada": app_ada,
            "app_tidak_ada": app_tidak_ada,
            "sltr_usulan_dibuat": sltr_usulan_dibuat,
            "app_tanpa_usulan": app_tanpa_usulan,
        }
        hasil.sukses = True

        update_progress(100, "Seluruh proses topologi GeoConnect-AI berhasil diselesaikan!")
        log_pesan("Pipeline topologi selesai dengan sukses.", "SUCCESS", log_cb)

    except Exception as e:
        import traceback
        hasil.sukses = False
        hasil.pesan_error = f"Terjadi kesalahan saat menjalankan pipeline: {str(e)}"
        hasil.waktu_eksekusi_detik = time.time() - waktu_mulai
        log_pesan(f"ERROR FATAL: {str(e)}", "ERROR", log_cb)
        log_pesan(traceback.format_exc(), "ERROR", log_cb)

    return hasil
