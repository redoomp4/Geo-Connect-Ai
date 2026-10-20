"""Skrip pembungkus paket plugin GeoConnect-AI ke format berkas ZIP instalasi.

Menghasilkan `geoconnect_ai.zip` dengan struktur direktori internal `geoconnect_ai/`
yang bersih dari berkas cache (`__pycache__`, `.pyc`, `.pytest_cache`), direktori tes,
dan file sementara, siap untuk 'Plugins > Manage and Install Plugins > Install from ZIP'.
"""

import os
import zipfile


def buat_paket_zip():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    plugin_dir = os.path.join(repo_root, "geoconnect_ai")
    output_zip = os.path.join(repo_root, "geoconnect_ai.zip")

    if not os.path.exists(plugin_dir):
        raise FileNotFoundError(f"Direktori plugin tidak ditemukan: {plugin_dir}")

    if os.path.exists(output_zip):
        os.remove(output_zip)

    print(f"Membangun arsip plugin QGIS: {output_zip}...")
    file_count = 0

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(plugin_dir):
            # Abaikan __pycache__ dan direktori cache lainnya
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]

            for file in files:
                if file.endswith((".pyc", ".pyo", ".pyd")):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_root)

                # Pastikan path di dalam ZIP menggunakan pemisah forward slash
                zip_path = rel_path.replace("\\", "/")
                zipf.write(full_path, zip_path)
                file_count += 1
                print(f"  + {zip_path}")

    print(f"\nSelesai! {file_count} berkas dikemas ke dalam '{output_zip}'.")
    print("Petunjuk Instalasi di QGIS:")
    print("  1. Buka menu 'Plugins' > 'Manage and Install Plugins...'")
    print("  2. Pilih tab 'Install from ZIP'")
    print(f"  3. Pilih berkas: {output_zip}")
    print("  4. Klik 'Install Plugin'")


if __name__ == "__main__":
    buat_paket_zip()
