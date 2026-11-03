"""Modul pengelompokan layer hasil ke dalam QgsLayerTreeGroup.

Menyusun layer hasil ke dalam grup bernama sesuai data master + akhiran '_done'
(contoh: layer master 'SBJ0045_APP1', 'SBJ0045_JTR', ... -> grup 'SBJ0045_done')
di posisi teratas layer tree tanpa mengganggu layer atau grup lain milik pengguna.
"""

import os
from typing import Any, List, Optional

try:
    from qgis.core import (
        QgsLayerTreeGroup,
        QgsProject,
        QgsVectorLayer,
    )
except ImportError:
    QgsLayerTreeGroup = None
    QgsProject = None
    QgsVectorLayer = None


AKHIRAN_GRUP = "_done"
NAMA_MASTER_DEFAULT = "GeoConnect-AI"


def tentukan_nama_master(layer_sumber: List[Any]) -> str:
    """Menentukan nama data master dari nama layer-layer sumber.

    Mengambil awalan (prefix) bersama dari nama layer sumber, misalnya
    'SBJ0045_APP1', 'SBJ0045_JTR', 'SBJ0045_GARDU' -> 'SBJ0045'.
    Jika tidak ada awalan bersama yang berarti, gunakan nama layer pertama.

    Args:
        layer_sumber: Daftar layer sumber (boleh berisi None).

    Returns:
        str: Nama data master (tanpa akhiran '_done').
    """
    nama_list = []
    for lyr in layer_sumber:
        if lyr is None or not hasattr(lyr, "name"):
            continue
        nama = (lyr.name() or "").strip()
        if nama and nama not in nama_list:
            nama_list.append(nama)

    if not nama_list:
        return NAMA_MASTER_DEFAULT

    if len(nama_list) == 1:
        return nama_list[0].strip(" _-.") or NAMA_MASTER_DEFAULT

    prefix = os.path.commonprefix(nama_list)
    # Potong di pemisah terakhir agar tidak berhenti di tengah kata (mis. 'SBJ0045_A')
    if not all(n == prefix or n[len(prefix):len(prefix) + 1] in "_- ." for n in nama_list):
        posisi = max(prefix.rfind(c) for c in "_- .")
        prefix = prefix[:posisi] if posisi > 0 else ""
    prefix = prefix.strip(" _-.")

    if len(prefix) >= 2:
        return prefix
    return nama_list[0].strip(" _-.") or NAMA_MASTER_DEFAULT


def _hapus_grup_lama(root: Any, prj: Any, nama_group: str) -> None:
    """Menghapus grup hasil sebelumnya dengan nama sama (hanya layer memory hasil plugin)."""
    lama = root.findGroup(nama_group) if hasattr(root, "findGroup") else None
    while lama is not None:
        for node in lama.findLayers():
            lyr = node.layer()
            if lyr is not None and lyr.providerType() == "memory":
                prj.removeMapLayer(lyr.id())
        parent = lama.parent() or root
        parent.removeChildNode(lama)
        lama = root.findGroup(nama_group)


def kelompokkan_layer(
    layer_jtr_snapped: Optional[Any],
    layer_dangling: Optional[Any],
    layer_app_anomali: Optional[Any],
    layer_sltr_usulan: Optional[Any],
    project: Optional[Any] = None,
    layer_gardu_hasil: Optional[Any] = None,
    layer_tiang_hasil: Optional[Any] = None,
    nama_master: Optional[str] = None,
) -> Optional[Any]:
    """Mengelompokkan layer hasil analisis ke grup teratas pada QGIS Layer Tree.

    Nama grup = '<nama_master>_done'. Jika grup dengan nama yang sama sudah ada
    (hasil proses sebelumnya), grup lama diganti dengan hasil terbaru.

    Urutan layer di dalam grup (dari atas ke bawah):
    1. APP Anomali (Titik)
    2. Tiang TR (Titik, opsional)
    3. Gardu Distribusi (Titik, opsional)
    4. SLTR Usulan (Garis SLTR asli + usulan)
    5. Penyambungan Dangling (Garis putus-putus)
    6. JTR Snapping (Garis)
    """
    prj = project or (QgsProject.instance() if QgsProject else None)
    if prj is None:
        return None

    root = prj.layerTreeRoot()
    if root is None:
        return None

    master = (nama_master or "").strip() or NAMA_MASTER_DEFAULT
    nama_group = f"{master}{AKHIRAN_GRUP}"

    # Ganti hasil proses sebelumnya untuk master yang sama
    _hapus_grup_lama(root, prj, nama_group)

    # Sisipkan grup baru di urutan teratas (index 0)
    group = root.insertGroup(0, nama_group)

    # Urutan: titik di atas garis agar Tiang & Gardu tidak tertutup garis JTR/SLTR.
    # Tiang di atas Gardu agar tiang yang berimpit dengan gardu tetap terlihat.
    urutan_layer = [
        layer_app_anomali,
        layer_tiang_hasil,
        layer_gardu_hasil,
        layer_sltr_usulan,
        layer_dangling,
        layer_jtr_snapped,
    ]

    for lyr in urutan_layer:
        if lyr is not None and hasattr(lyr, "isValid") and lyr.isValid():
            # Daftarkan layer ke project (False = jangan auto-add ke root tree)
            prj.addMapLayer(lyr, False)
            # Tambahkan ke dalam grup hasil
            group.addLayer(lyr)

    return group
