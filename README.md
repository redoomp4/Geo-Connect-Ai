# GeoConnect-AI: Otomatisasi Topologi Jaringan APP-SLTR-JTR-Gardu (PyQGIS)

[![QGIS Compatibility](https://img.shields.io/badge/QGIS-3.28%20LTR%20--%203.99%20%7C%204.x-brightgreen.svg)](https://qgis.org/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20PLN-orange.svg)]()
[![Repository](https://img.shields.io/badge/GitHub-redoomp4%2FGeo--Connect--Ai-lightgrey.svg)](https://github.com/redoomp4/Geo-Connect-Ai)

Plugin resmi QGIS untuk **PT PLN (Persero) UID Kalimantan Timur dan Utara** yang mengotomatisasi pembersihan, *snapping*, penyambungan *dangling line*, dan deteksi anomali titik sambung APP (kWh meter) dalam **satu klik (*one-click action*)** untuk persiapan simulasi aliran daya **PSS SINCAL**.

---

## Daftar Isi
1. [Prasyarat Sistem (Apa Saja yang Harus Diinstal)](#1-prasyarat-sistem-apa-saja-yang-harus-diinstal)
2. [Langkah-Langkah Instalasi Lengkap (Step-by-Step)](#2-langkah-langkah-instalasi-lengkap-step-by-step)
   - [Langkah 1: Siapkan QGIS Desktop](#langkah-1-siapkan-qgis-desktop)
   - [Langkah 2: Dapatkan Berkas Plugin](#langkah-2-dapatkan-berkas-plugin)
   - [Langkah 3: Pasang Plugin ke QGIS](#langkah-3-pasang-plugin-ke-qgis)
   - [Langkah 4: Verifikasi & Aktifkan Plugin](#langkah-4-verifikasi--aktifkan-plugin)
3. [Panduan Penggunaan Cepat (Quick Start Tutorial)](#3-panduan-penggunaan-cepat-quick-start-tutorial)
4. [Penjelasan Fitur Lengkap](#4-penjelasan-fitur-lengkap)
5. [Arti Layer Hasil & Simbologi Warna](#5-arti-layer-hasil--simbologi-warna)
6. [Struktur Direktori Repositori](#6-struktur-direktori-repositori)
7. [Pengujian Otomatis & Benchmark Performa](#7-pengujian-otomatis--benchmark-performa)
8. [Troubleshooting & Solusi Kendala](#8-troubleshooting--solusi-kendala)

---

## 1. Prasyarat Sistem (Apa Saja yang Harus Diinstal)

Sebelum memasang plugin ini, pastikan komputer Anda memenuhi prasyarat berikut:

### A. Perangkat Lunak Utama: QGIS Desktop
* **Versi yang Didukung:** **QGIS 3.28 LTR**, **QGIS 3.34 LTR**, atau versi yang lebih baru (hingga QGIS 3.99 / 4.x).
* **Sistem Operasi:** Windows 10/11 (64-bit), macOS, atau Linux.
* **Tautan Unduhan Resmi:**
  👉 [Unduh QGIS Desktop dari Situs Resmi (qgis.org)](https://qgis.org/en/site/forusers/download.html)
  *(Disarankan memilih versi **Long Term Release (LTR)** untuk stabilitas maksimal).*

### B. Lingkungan Python
* **TIDAK PERLU menginstal Python secara terpisah!**
  QGIS sudah dilengkapi dengan lingkungan Python bawaan (Python 3.9+).
* **TIDAK MEMERLUKAN library tambahan (*No External Dependencies*)!**
  Plugin ini dirancang murni menggunakan API bawaan PyQGIS dan Standard Library Python. Anda **tidak perlu** menjalankan perintah `pip install` (seperti `networkx`, `shapely`, `geopandas`, atau `scipy`). Semuanya langsung siap pakai begitu QGIS terpasang.

---

## 2. Langkah-Langkah Instalasi Lengkap (Step-by-Step)

Ikuti tahapan berikut secara berurutan:

### Langkah 1: Siapkan QGIS Desktop
1. Unduh installer QGIS dari [qgis.org](https://qgis.org/en/site/forusers/download.html).
2. Jalankan berkas installer (misal `QGIS-OSGeo4W-3.34.x-Setup-x86_64.exe`) dan ikuti instruksi di layar hingga selesai.
3. Buka aplikasi **QGIS Desktop** dari Start Menu / Application Launcher.

### Langkah 2: Dapatkan Berkas Plugin
Anda memiliki 2 pilihan untuk mengunduh plugin:

* **Opsi A (Paling Praktis): Unduh Berkas ZIP Langsung**
  Unduh berkas `geoconnect_ai.zip` dari repositori ini:
  👉 [geoconnect_ai.zip](https://github.com/redoomp4/Geo-Connect-Ai/raw/main/geoconnect_ai.zip)
* **Opsi B: Meng-clone Repositori (Bagi Pengembang / Mahasiswa)**
  ```bash
  git clone https://github.com/redoomp4/Geo-Connect-Ai.git
  ```
  *(Jika Anda meng-clone repo dan ingin membuat berkas ZIP sendiri, jalankan `python tools/buat_zip.py`).*

---

### Langkah 3: Pasang Plugin ke QGIS

Pilih salah satu metode berikut:

#### Metode A: Instalasi dari Menu QGIS (Direkomendasikan)
1. Buka aplikasi **QGIS**.
2. Pada bilah menu atas, klik **Plugins** (atau **Plugin**) ➔ **Manage and Install Plugins...** (Kelola dan Pasang Plugin).
   
   ![Menu Plugin QGIS](https://raw.githubusercontent.com/redoomp4/Geo-Connect-Ai/main/geoconnect_ai/icon.png)

3. Di jendela dialog yang muncul, pilih tab **Install from ZIP** di sisi panel kiri.
4. Klik tombol titik tiga (**...**) pada bagian *ZIP file*, lalu arahkan dan pilih berkas **`geoconnect_ai.zip`** yang sudah diunduh.
5. Klik tombol **Install Plugin** (Pasang Plugin).
6. Tunggu beberapa detik hingga muncul notifikasi hijau di bagian atas:
   > *"Plugin installed successfully"*.

---

#### Metode B: Salin Folder Manual (Alternatif Jika Menu ZIP Dibatasi)
Jika instalasi via ZIP mengalami kendala izin akses (*permission*), Anda dapat menyalin folder plugin secara manual:
1. Ekstrak berkas `geoconnect_ai.zip` (atau ambil folder `geoconnect_ai` dari repositori).
2. Salin folder bernama **`geoconnect_ai`** ke lokasi profil pengguna QGIS sesuai sistem operasi Anda:

   * **Windows:**
     Tekan tombol `Windows + R`, ketik atau salin path berikut lalu tekan Enter:
     ```plaintext
     %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins
     ```
     *(Salin folder `geoconnect_ai` ke dalam folder `plugins` di atas).*
   * **Linux:**
     ```bash
     ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
     ```
   * **macOS:**
     ```bash
     ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/
     ```
3. Tutup dan buka kembali (restart) aplikasi QGIS Anda.

---

### Langkah 4: Verifikasi & Aktifkan Plugin
1. Buka menu **Plugins** ➔ **Manage and Install Plugins...**.
2. Klik tab **Installed** di sisi kiri.
3. Cari nama **GeoConnect-AI**.
4. Pastikan kotak di samping namanya telah **dicentang** (`[✓]`).
5. Klik **Close**.
6. Anda sekarang akan melihat:
   * Ikon **GeoConnect-AI** pada toolbar QGIS.
   * Menu baru di bilah menu: **Plugins ➔ GeoConnect-AI ➔ Buka GeoConnect-AI**.

Plugin telah siap 100% untuk digunakan! 🎉

---

## 3. Panduan Penggunaan Cepat (Quick Start Tutorial)

Untuk menguji apakah plugin berfungsi dengan baik, gunakan data uji bawaan yang disertakan:

1. **Buka Project Baru di QGIS**:
   Buka QGIS dengan project kosong.
2. **Muat Data Uji Jaringan**:
   * Ambil berkas **`data_uji_balikpapan.gpkg`** dari repositori.
   * *Drag and drop* (seret) file tersebut ke dalam Map Canvas QGIS.
   * Centang dan masukkan semua layer: `gardu`, `jtr`, `sltr`, dan `app`.
3. **Buka Dialog GeoConnect-AI**:
   * Klik ikon **GeoConnect-AI** di toolbar atau via menu **Plugins ➔ GeoConnect-AI**.
4. **Pilih Layer & Kolom Acuan**:
   * **Gardu (Titik):** Pilih layer `gardu`.
   * **JTR (Garis):** Pilih layer `jtr`.
   * **SLTR (Garis, Opsional):** Pilih layer `sltr` (boleh dikosongkan jika belum ada kabel sambungan luar).
   * **APP (Titik):** Pilih layer `app`.
   *(Plugin secara otomatis mengenali nama layer & nama kolom ID standar).*
5. **Konfigurasi Parameter Toleransi**:
   Gunakan nilai rekomendasi default PLN:
   * **Snapping JTR ➔ Gardu:** `10.0` meter.
   * **Sambungan Dangling:** `8.0` meter.
   * **Batas APP Tersambung:** `0.5` meter.
   * **Jarak Maksimal Usulan SLTR:** `50.0` meter.
6. **Eksekusi Sekali Klik**:
   * Klik tombol **Jalankan Proses (One-Click)**.
   * Perhatikan progress bar dan log realtime di panel kanan.
7. **Lihat Hasil Analisis**:
   * QGIS otomatis membuat grup layer baru: `GeoConnect-AI - Hasil (HH:MM:SS)`.
   * Di peta akan langsung terlihat titik hijau (APP normal), titik merah (APP anomali), garis oranye putus-putus (usulan SLTR), dan garis biru putus-putus (kabel dangling yang disambung).
8. **Ekspor Hasil (Opsional)**:
   * Pada tab **Ekspor**, Anda dapat mengekspor seluruh layer usulan ke format `.gpkg`, `.shp`, atau `.geojson`, serta mengunduh ringkasan metriks ke berkas Excel (`.xlsx`) / CSV.

---

## 4. Penjelasan Fitur Lengkap

| Fitur | Keterangan & Logika Algoritma |
|---|---|
| **100% Non-Destruktif** | Data GIS asli PLN tidak dimodifikasi, digeser, atau dihapus. Hasil disajikan sebagai *memory layer* atau file baru sehingga aman terhadap data induk. |
| **Auto-Snapping JTR** | Menggeser vertex ujung JTR terdekat secara presisi ke posisi Gardu menggunakan indeks spasial R-Tree $O(N \log N)$ untuk menjamin kontinuitas aliran daya hulu. |
| **Dangling Resolver** | Menemukan segmen JTR yang terputus di tengah jaringan (ujung menggantung berderajat 1) dan mengusulkan garis penyambung (*connector line*) otomatis. |
| **Deteksi Anomali APP** | Menerapkan aturan standar *Topology Checker* QGIS (*point not covered by segment*). APP berjarak $\le$ 0.5 m dari jaringan ditandai normal (`ADA`), sedangkan selebihnya ditandai anomali (`TIDAK ADA`). |
| **Smart SLTR Usulan** | Membentuk rute kabel usulan baru bagi APP anomali **hanya ke segmen jaringan aktif** (komponen yang tersambung ke Gardu melalui graf *Union-Find*). APP tidak akan disambungkan ke jaringan mati. |
| **Simbologi Visual Otomatis** | Menerapkan pewarnaan tematik standar operasional lapangan PLN secara otomatis tanpa perlu pengaturan manual oleh operator GIS. |
| **Auto Layer Grouping** | Mengorganisir layer hasil ke dalam grup terstruktur rapi pada panel Layer QGIS dengan penanda waktu (*timestamp*). |
| **Ekspor Multi-Format & Laporan** | Mendukung ekspor ke format spasial standar industri (GPKG, SHP, GeoJSON, GDB) dan rekapitulasi eksekutif berupa tabel Excel (.xlsx) / CSV. |

---

## 5. Arti Layer Hasil & Simbologi Warna

| Nama Layer | Tipe Geometri | Simbologi & Warna | Keterangan |
|---|---|---|---|
| **APP Anomali** | Titik (*Point*) | 🟢 Titik Hijau Kecil (`ADA`)<br>🔴 **Titik Merah Mencolok** (`TIDAK ADA`) | Menampilkan seluruh pelanggan PLN. Warna merah menandakan titik kWh meter yang belum tersambung ke jaringan kabel (anomali topologi). |
| **SLTR Usulan** | Garis (*LineString*) | 🟠 **Garis Oranye Putus-Putus** | Usulan tarikan kabel Saluran Luar Tegangan Rendah baru dari APP anomali ke tiang/kabel JTR aktif terdekat. |
| **Penyambungan Dangling** | Garis (*LineString*) | 🔵 **Garis Biru Muda Putus-Putus** | Usulan sambungan untuk menghubungkan kabel JTR yang terputus/menggantung di lapangan. |
| **JTR Snapping** | Garis (*LineString*) | 🟢 Garis Hijau Toska (`SNAPPED`)<br>⚪ Garis Abu-abu (`UTUH`) | Layer JTR hasil perbaikan. Ujung yang dekat dengan Gardu sudah menempel sempurna (*snapped*). |

---

## 6. Struktur Direktori Repositori

```plaintext
Geo-Connect AI/
├── geoconnect_ai/                 # Folder inti plugin QGIS
│   ├── __init__.py                # Entry point modul plugin
│   ├── geoconnect_ai.py           # Kelas utama lifecycle plugin QGIS
│   ├── metadata.txt               # Metadata spesifikasi plugin QGIS
│   ├── icon.png                   # Ikon toolbar plugin
│   ├── core/                      # Modul algoritma & pemrosesan topologi
│   │   ├── config.py              # Konfigurasi parameter & toleransi default
│   │   ├── crs_utils.py           # Transformasi koordinat & kalkulasi metrik
│   │   ├── nearest.py             # Algoritma pencarian tetangga terdekat (R-Tree)
│   │   ├── snapping.py            # Engine auto-snapping JTR ke Gardu
│   │   ├── dangling.py            # Detektor & penyambung dangling line
│   │   ├── graph_builder.py       # Engine graf topologi (Union-Find)
│   │   ├── anomali_app.py         # Deteksi keterhubungan APP
│   │   ├── usulan.py              # Generator rute kabel SLTR usulan
│   │   ├── styler.py              # Engine visualisasi simbologi tematik
│   │   ├── layer_group.py         # Manajemen pengelompokan layer QGIS
│   │   ├── exporter.py            # Engine ekspor data spasial (GPKG/SHP/GeoJSON/GDB)
│   │   ├── reporter.py            # Pembuat laporan rekapitulasi Excel / CSV
│   │   ├── validator.py           # Validasi layer input pengguna
│   │   └── pipeline.py            # Orkestrator alur kerja menyeluruh
│   └── ui/                        # Antarmuka Pengguna (GUI)
│       └── dialog.py              # Dialog PyQt5/PyQt6 2-kolom responsif
├── tests/                         # Suite pengujian otomatis
│   ├── test_unit_murni.py         # Unit test mandiri (tanpa butuh QGIS)
│   ├── test_integrasi_qgis.py     # Integrasi test di dalam QGIS
│   └── data_sintetis.py           # Generator data jaringan sintetis
├── tools/                         # Utilitas pengembang
│   ├── buat_zip.py                # Skrip otomatisasi build paket ZIP plugin
│   ├── buat_data_uji.py           # Generator dataset uji data_uji_balikpapan.gpkg
│   ├── benchmark.py               # Pengujian performa skala 1K s.d. 10K objek
│   └── run_qgis.bat               # Runner skrip berbasis lingkungan QGIS Windows
├── data_uji_balikpapan.gpkg       # Dataset uji coba simulasi Balikpapan
├── geoconnect_ai.zip              # Paket instalasi siap pasang
├── ASSUMPTIONS.md                 # Dokumentasi keputusan teknis & asumsi
└── README.md                      # Dokumentasi lengkap panduan pengguna
```

---

## 7. Pengujian Otomatis & Benchmark Performa

### A. Menjalankan Unit Test (Bisa Dijalankan di Python Standar)
```powershell
python -m unittest tests/test_unit_murni.py -v
```

### B. Menjalankan Integrasi Test (Di Lingkungan QGIS)
```powershell
cmd /c tools\run_qgis.bat -m unittest tests/test_integrasi_qgis.py -v
```

### C. Hasil Pengujian Benchmark Aktual
Diuji menggunakan skenario jaringan bertingkat (`tools/benchmark.py`):

| Skenario Pengujian | Jumlah Objek APP | Jumlah Segmen JTR | Gardu | Waktu Eksekusi Aktual | Status Batas Standar (< 60s) |
|---|---|---|---|---|---|
| **Skenario 1K** | 1.000 APP | 500 segmen | 5 Gardu | **0.12 detik** | MEMENUHI (500x lebih cepat) |
| **Skenario 5K** | 5.000 APP | 2.500 segmen | 20 Gardu | **0.68 detik** | MEMENUHI (88x lebih cepat) |
| **Skenario 10K** | 10.000 APP | 5.000 segmen | 40 Gardu | **1.43 detik** | MEMENUHI (41x lebih cepat) |

---

## 8. Troubleshooting & Solusi Kendala

| Kendala | Penyebab Umum | Solusi Praktis |
|---|---|---|
| **Pesan: *"Plugin is incompatible with this version of QGIS"*** | Metadata versi minimum atau maksimum tidak sesuai dengan QGIS Anda. | Versi pada `metadata.txt` sudah disesuaikan untuk QGIS 3.28 s.d. 3.99/4.x. Pastikan Anda menggunakan berkas `geoconnect_ai.zip` terbaru dari repositori ini. |
| **Ikon Plugin Tidak Muncul di Toolbar** | Plugin belum dicentang setelah instalasi. | Buka menu **Plugins ➔ Manage and Install Plugins... ➔ Installed**, lalu pastikan tanda centang pada **GeoConnect-AI** aktif. |
| **Layer Asli Sedang Dalam Mode Edit (*Editing Session*)** | Fitur pada layer sumber sedang diedit (*unsaved edits*). | Simpan atau batalkan sesi edit layer sumber (*Save Layer Edits* / *Toggle Editing*) sebelum menekan tombol Jalankan. |
| **Peringatan Driver Ekspor GDB** | Driver GDAL OpenFileGDB pada instalasi QGIS tertentu berstatus *read-only*. | Pilih format ekspor standar **GeoPackage (.gpkg)** yang didukung secara penuh dan optimal di semua versi QGIS. |
| **Ekspor Excel Mengarah ke CSV** | Driver OGR XLSX tidak tersedia pada build GDAL tertentu. | Plugin secara otomatis mengalihkan penyimpanan ke file `.csv` dengan integritas data dan kolom yang sama lengkapnya. |

---

## Kontributor & Lisensi
Dikembangkan untuk kebutuhan automasi jaringan distribusi listrik **PT PLN (Persero) UID Kalimantan Timur dan Utara**.
Repositori: [https://github.com/redoomp4/Geo-Connect-Ai](https://github.com/redoomp4/Geo-Connect-Ai)
