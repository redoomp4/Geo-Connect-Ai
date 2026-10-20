# GeoConnect-AI: Otomatisasi Topologi Jaringan APP-SLTR-JTR-Gardu (PyQGIS)

Plugin resmi QGIS untuk **PT PLN (Persero) UID Kalimantan Timur dan Utara** yang mengotomatisasi pembersihan, snapping, penyambungan dangling line, dan deteksi anomali titik sambung APP (kWh meter) dalam **satu klik (one-click action)** untuk persiapan simulasi aliran daya **PSS SINCAL**.

---

## 1. Fitur Utama

- **100% Non-Destruktif:** Layer sumber asli (Gardu, JTR, SLTR, APP) tidak pernah diubah, digeser, maupun dihapus. Seluruh hasil analisis disajikan sebagai usulan pada *memory layer* terpisah.
- **Auto-Snapping JTR ke Gardu:** Menggeser vertex ujung JTR ke koordinat Gardu distribusi terdekat secara presisi jika memenuhi batas toleransi metrik.
- **Deteksi & Penyambungan Dangling Line:** Menemukan ujung jaringan yang menggantung tanpa koneksi dan mengusulkan garis penghubung baru ke segmen tetangga.
- **Analisis Keterhubungan APP (kWh Meter):** Mereplikasi aturan QGIS Topology Checker (*point not covered by segment*) untuk memisahkan APP normal (`ADA`) dan anomali (`TIDAK ADA`).
- **SLTR Usulan ke Jaringan Aktif:** Membentuk garis usulan sambungan baru untuk APP anomali **hanya ke segmen jaringan aktif** (komponen yang menyentuh Gardu). APP yang dekat dengan komponen terisolasi tidak akan disambungkan ke segmen mati tersebut.
- **Simbologi Visual Tematik:** Mewarnai APP normal dengan hijau kecil, APP anomali dengan titik merah mencolok, SLTR usulan dengan garis oranye putus-putus, dan sambungan dangling dengan garis biru muda putus-putus.
- **Manajemen Layer Group Rapi:** Mengelompokkan seluruh layer hasil ke dalam satu grup `GeoConnect-AI - Hasil (HH:MM:SS)` di bagian teratas panel layer QGIS.
- **Ekspor Fleksibel & Laporan:** Mendukung ekspor ke GeoPackage (.gpkg), ESRI Shapefile (.shp), GeoJSON (.geojson), File Geodatabase (.gdb), serta ekspor ringkasan eksekutif ke tabel Excel (.xlsx) atau CSV.
- **Performa Tinggi Tanpa Dependensi Tambahan:** Algoritma berbasis $O(N \log N)$ dengan `QgsSpatialIndex` dan Union-Find murni Python. Tidak membutuhkan `pip install` library tambahan (`networkx`, `shapely`, `geopandas`, `scipy` dsb).

---

## 2. Cara Instalasi di QGIS

Target kompatibilitas: **QGIS 3.28 LTR, QGIS 3.34 LTR, dan QGIS 4.x** (Python 3.9+).

### Metode A: Instalasi dari ZIP (Direkomendasikan)
1. Buka aplikasi **QGIS**.
2. Masuk ke menu **Plugins** > **Manage and Install Plugins...**
3. Klik tab **Install from ZIP** di sisi kiri.
4. Klik tombol **Browse (...)** dan pilih berkas `geoconnect_ai.zip`.
5. Klik **Install Plugin**.
6. Ikon **GeoConnect-AI** akan otomatis muncul di toolbar dan menu **Plugins > GeoConnect-AI**.

### Metode B: Salin Manual ke Direktori Profil QGIS
Salin folder `geoconnect_ai` ke lokasi direktori plugin QGIS pengguna:
- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\geoconnect_ai`
- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geoconnect_ai`
- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/geoconnect_ai`
Setelah disalin, restart QGIS atau aktifkan plugin melalui menu **Plugins > Manage and Install Plugins > Installed > GeoConnect-AI**.

---

## 3. Langkah Penggunaan & Rekomendasi Toleransi

1. Muat layer data jaringan Anda ke QGIS (atau gunakan data uji `data_uji_balikpapan.gpkg`).
2. Klik ikon **GeoConnect-AI** pada toolbar.
3. Pada dialog, pilih layer:
   - **Gardu (Titik):** Layer gardu distribusi acuan.
   - **JTR (Garis):** Layer garis Jaringan Tegangan Rendah.
   - **SLTR (Garis, Opsional):** Saluran Luar Tegangan Rendah (bisa dikosongkan jika belum ada).
   - **APP (Titik):** Layer titik kWh meter pelanggan PLN.
   - *(Opsional)* Pilih kolom ID spesifik jika tersedia, atau biarkan default (menggunakan `fid`).
4. Atur toleransi spasial (satuan meter):
   - **Snapping JTR → Gardu (Default: 10.0 m):** Jarak maksimal ujung JTR ditarik menempel ke Gardu.
   - **Sambungan Dangling (Default: 8.0 m):** Jarak maksimal ujung gantung dihubungkan ke segmen JTR lain.
   - **Batas APP Tersambung (Default: 0.5 m):** Toleransi jarak APP menempel ke garis JTR/SLTR untuk dianggap `ADA`.
   - **Jarak Maksimal Usulan SLTR (Default: 50.0 m):** Jarak terjauh APP anomali yang masih dibuatkan garis usulan SLTR baru.
5. Klik tombol **Jalankan Proses (One-Click)**.
6. Pantau proses melalui panel log realtime dan bilah progres.

---

## 4. Arti Layer Hasil & Simbologi Warna

| Nama Layer | Geometri | Simbol & Warna | Deskripsi |
|---|---|---|---|
| **APP Anomali** | Titik | Titik Hijau Kecil (`ADA`)<br>Titik **Merah Mencolok** (`TIDAK ADA`) | Memuat **semua** pelanggan. Hijau menandakan kWh meter normal yang sudah menempel jaringan; Merah menandakan anomali topologi yang belum terhubung. |
| **SLTR Usulan** | Garis | Garis **Oranye Putus-Putus** | Usulan sambungan Saluran Luar Tegangan Rendah baru dari APP anomali ke jaringan aktif. |
| **Penyambungan Dangling** | Garis | Garis **Biru Muda Putus-Putus** | Garis penghubung usulan untuk menyambung segmen JTR yang terputus di lapangan. |
| **JTR Snapping** | Garis | Garis **Cyan / Hijau** (`SNAPPED`)<br>Garis **Abu-abu Slate** (`UTUH`) | Seluruh segmen JTR hasil snapping. Ujung yang menempel ke gardu diperbarui geometrinya. |

---

## 5. Hasil Pengujian Benchmark Performa Aktual

Pengujian diukur secara aktual menggunakan CPU lokal pada skenario jaringan sintetis bertingkat (`tools/benchmark.py`):

| Skenario Pengujian | Jumlah Titik APP | Jumlah Segmen JTR | Jumlah Gardu | Waktu Eksekusi Aktual | Target Batas (< 60s) |
|---|---|---|---|---|---|
| **Skenario 1K** | 1.000 APP | 500 segmen | 5 Gardu | **0.12 detik** | MEMENUHI (500x lebih cepat) |
| **Skenario 5K** | 5.000 APP | 2.500 segmen | 20 Gardu | **0.68 detik** | MEMENUHI (88x lebih cepat) |
| **Skenario 10K** | 10.000 APP | 5.000 segmen | 40 Gardu | **1.43 detik** | MEMENUHI (41x lebih cepat) |

---

## 6. Cara Menjalankan Pengujian Otomatis

### A. Unit Test Murni (Tanpa Perlu QGIS)
Dapat dijalankan di lingkungan Python standar manapun:
```powershell
python -m unittest tests/test_unit_murni.py -v
```

### B. Integrasi Test PyQGIS (Membutuhkan QGIS)
Dijalankan menggunakan skrip pembantu `tools/run_qgis.bat`:
```powershell
cmd /c tools\run_qgis.bat -m unittest tests/test_integrasi_qgis.py -v
```

### C. Menghasilkan Data Uji Sintetis (.gpkg)
```powershell
cmd /c tools\run_qgis.bat tools/buat_data_uji.py
```

### D. Mengemas Ulang ZIP Plugin
```powershell
python tools/buat_zip.py
```

---

## 7. Troubleshooting & Keterbatasan

1. **Penulisan File Geodatabase (.gdb):**
   Driver GDAL `OpenFileGDB` memerlukan versi GDAL $\ge 3.6$ dengan dukungan tulis (*write support*). Jika instalasi QGIS Anda menggunakan versi lama yang hanya mendukung *read-only*, plugin akan menampilkan peringatan informatif dan menyarankan format standar **GeoPackage (.gpkg)**.
2. **Keterbatasan Layer Asli Sedang Dalam Mode Edit:**
   Pastikan layer sumber tidak dalam kondisi sesi edit (*toggle editing*) yang belum tersimpan (*unsaved buffer*). Simpan perubahan terlebih dahulu sebelum menjalankan pipeline.
3. **Ekspor Laporan Excel (.xlsx):**
   Plugin menggunakan driver OGR bawaan QGIS untuk menulis file `.xlsx`. Jika instalasi GDAL tidak memuat driver XLSX, plugin secara otomatis mengalihkan penyimpanan ke format `.csv` dengan integritas data tabel yang sama lengkapnya.
