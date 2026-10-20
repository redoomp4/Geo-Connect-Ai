# Asumsi & Keputusan Desain GeoConnect-AI

Dokumen ini mencatat asumsi dan keputusan teknis yang diambil selama pengembangan plugin QGIS **GeoConnect-AI** untuk menjaga konsistensi, keandalan, dan kepatuhan terhadap batasan sistem.

---

## 1. Lingkungan & Kompatibilitas
- **Versi QGIS:** Target kompatibilitas QGIS 3.28 LTR, QGIS 3.34 LTR, dan QGIS 4.x (termasuk QGIS 4.2.1 yang terdeteksi di lingkungan lokal).
- **Import Qt:** Menggunakan `from qgis.PyQt...` (seperti `from qgis.PyQt.QtCore import ...`, `from qgis.PyQt.QtWidgets import ...`, `from qgis.PyQt.QtGui import ...`) untuk kompatibilitas lintas PyQt5 dan PyQt6.
- **Python Runtime:** Python 3.9+ murni, hanya modul bawaan Python standard library (`math`, `re`, `typing`, `dataclasses`, `os`, `sys`, `time`, `datetime`, `collections`, `csv`, dll) serta API resmi QGIS (`qgis.core`, `qgis.gui`, `qgis.PyQt`). Tanpa dependensi pihak ketiga eksternal seperti `networkx`, `shapely`, `geopandas`, `openpyxl`, atau `scipy`.

---

## 2. Struktur Data & Topologi
- **Kunci Node Graf (`epsilon_node_m`):** Titik ujung segmen JTR dan titik Gardu dibulatkan ke grid kelipatan `epsilon_node_m` (default 0.05 meter) untuk kunci node graf: `(round(x / eps) * eps, round(y / eps) * eps)`. Hal ini menjamin ujung yang praktis berimpit (< 5 cm) terhubung ke simpul yang sama.
- **Penentuan Komponen Aktif:**
  - Komponen terhubung pada graf JTR dianggap **aktif** jika mengandung/menyentuh minimal satu titik Gardu (setelah snapping).
  - Jika tidak ada komponen yang menyentuh Gardu sama sekali, fallback ke komponen dengan total panjang/jumlah segmen terbesar, dan catat peringatan (WARNING) di log proses.
  - Usulan sambungan APP baru (SLTR usulan) **hanya diarahkan ke segmen pada jaringan aktif**.
- **Koneksi Dangling:**
  - Ujung segmen JTR dianggap dangling jika derajat simpulnya = 1, tidak berada di Gardu, dan tidak menyentuh segmen JTR lain.
  - Sambungan dangling dibuat sebagai garis penghubung baru (`STATUS="TERSAMBUNG"`) dari ujung dangling ke titik terdekat pada segmen JTR lain yang jaraknya `<= dangling_m`.
- **Anomali APP:**
  - Jarak APP ke garis terdekat (gabungan JTR + SLTR) dihitung dengan `QgsGeometry.distance()`.
  - Jika `jarak <= app_cover_m` (default 0.5 m), maka `STATUS = "ADA"`.
  - Jika `jarak > app_cover_m`, maka `STATUS = "TIDAK ADA"`.
  - Untuk APP `TIDAK ADA`, jika jaraknya ke jaringan aktif `<= app_usulan_maks_m` (default 50.0 m), maka dibuat fitur baru di layer SLTR Usulan (`STATUS = "USULAN"`). Jika `> app_usulan_maks_m`, APP tetap `TIDAK ADA`, dicatat sebagai tanpa usulan, dan tidak dibuatkan SLTR usulan.

---

## 3. Penanganan Geometri & Multi-Part
- Semua input layer disalin ke memori dan dipecah jika multi-part (`multipartToSingleParts` atau iterasi sub-geometri). Fitur dengan geometri `NULL`, panjang nol, atau tidak valid disaring di tahap validasi data dan dicatat di tabel data bermasalah tanpa menyentuh layer asli.
- Nilai field atribut nama dibatasi maksimal 10 karakter agar kompatibel penuh dengan ESRI Shapefile (DBF limit).

---

## 4. Sistem Proyeksi Koordinat (CRS)
- Jika CRS input berupa koordinat geografis (derajat, e.g. WGS 84 EPSG:4326), plugin secara otomatis menghitung zona UTM berdasarkan bujur titik tengah extent:
  - $\text{zona} = \lfloor(\text{lon} + 180) / 6\rfloor + 1$
  - EPSG: $32600 + \text{zona}$ (lintang utara) atau $32700 + \text{zona}$ (lintang selatan). Contoh: Balikpapan $\approx$ EPSG:32750 (UTM Zone 50S).
- Jika layer JTR sudah terproyeksi (satuan meter), CRS JTR digunakan sebagai CRS kerja default. Pengguna juga dapat memilih CRS override manual pada UI.
- Semua kalkulasi jarak dan spasial dilakukan pada CRS kerja (satuan meter).

---

## 5. Non-Destruktif & Layer Hasil
- Layer sumber (Gardu, JTR, SLTR, APP) tidak pernah diedit, dimodifikasi, atau dihapus.
- Hasil seluruh analisis ditulis ke 4 layer memory (`QgsVectorLayer` dengan skema `memory:`):
  1. `JTR Snapping`
  2. `Penyambungan Dangling`
  3. `APP Anomali`
  4. `SLTR Usulan`
- Keempat layer ini dikelompokkan ke dalam `QgsLayerTreeGroup` bernama `GeoConnect-AI - Hasil (HH:MM:SS)` pada bagian paling atas layer tree.

---

## 6. Ekspor & Format Laporan
- Ekspor layer spasial mendukung GeoJSON, ESRI Shapefile, GeoPackage (.gpkg), dan File Geodatabase (.gdb jika GDAL OpenFileGDB write didukung, dengan pesan fallback ke GeoPackage jika tidak didukung).
- Laporan ringkasan dan detail diekspor ke format Excel (.xlsx) melalui driver OGR QGIS, dengan fallback otomatis ke .csv jika driver XLSX tidak tersedia di instalasi GDAL.
