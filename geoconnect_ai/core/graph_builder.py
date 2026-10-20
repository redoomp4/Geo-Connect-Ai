"""Modul pembentukan graf topologi dan analisis komponen terhubung (Union-Find).

Menggunakan struktur data Disjoint-Set murni Python tanpa dependensi networkx/scipy.
Mengidentifikasi komponen aktif berdasarkan keterhubungan dengan Gardu distribusi.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


def kunci_node(x: float, y: float, epsilon: float = 0.05) -> Tuple[float, float]:
    """Membulatkan koordinat (x, y) dalam meter ke grid epsilon.

    Args:
        x (float): Koordinat X.
        y (float): Koordinat Y.
        epsilon (float): Toleransi grid node (default 0.05 meter).

    Returns:
        Tuple[float, float]: Koordinat grid terbulatkan.
    """
    if epsilon <= 0:
        return (round(x, 6), round(y, 6))
    kx = round(x / epsilon) * epsilon
    ky = round(y / epsilon) * epsilon
    rx = 0.0 if abs(kx) < 1e-12 else round(kx, 6)
    ry = 0.0 if abs(ky) < 1e-12 else round(ky, 6)
    return (rx, ry)


class DisjointSet:
    """Implementasi struktur data Union-Find dengan path compression dan union by size."""

    def __init__(self):
        self.parent: Dict[Any, Any] = {}
        self.size: Dict[Any, int] = {}

    def make_set(self, item: Any):
        """Mendaftarkan item baru ke dalam himpunan jika belum ada."""
        if item not in self.parent:
            self.parent[item] = item
            self.size[item] = 1

    def find(self, item: Any) -> Any:
        """Mencari representasi akar (root) dari himpunan dengan path compression."""
        if item not in self.parent:
            self.parent[item] = item
            self.size[item] = 1
            return item

        path = []
        curr = item
        while self.parent[curr] != curr:
            path.append(curr)
            curr = self.parent[curr]

        # Path compression
        for node in path:
            self.parent[node] = curr

        return curr

    def union(self, item1: Any, item2: Any) -> Any:
        """Menggabungkan dua himpunan berdasarkan ukuran (union by size)."""
        root1 = self.find(item1)
        root2 = self.find(item2)

        if root1 == root2:
            return root1

        # Gabungkan himpunan yang lebih kecil ke yang lebih besar
        if self.size[root1] < self.size[root2]:
            root1, root2 = root2, root1

        self.parent[root2] = root1
        self.size[root1] += self.size[root2]
        return root1

    def connected(self, item1: Any, item2: Any) -> bool:
        """Memeriksa apakah dua item berada dalam komponen yang sama."""
        return self.find(item1) == self.find(item2)

    def get_components(self) -> Dict[Any, Set[Any]]:
        """Mengembalikan mapping akar -> himpunan semua anggota dalam komponen."""
        comps = defaultdict(set)
        for item in list(self.parent.keys()):
            root = self.find(item)
            comps[root].add(item)
        return dict(comps)


def ekstrak_ujung_segmen(segmen: Any) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], float, Any]]:
    """Mengekstrak koordinat titik awal, titik akhir, panjang, dan id dari segmen.

    Mendukung dict murni Python maupun objek QgsFeature garis.
    """
    if isinstance(segmen, dict):
        p1 = segmen["start"]
        p2 = segmen["end"]
        panjang = segmen.get("length", 0.0)
        sid = segmen.get("id", id(segmen))
        return (p1, p2, panjang, sid)

    # Objek QgsFeature
    if hasattr(segmen, "geometry"):
        geom = segmen.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            return None
        panjang = geom.length() if hasattr(geom, "length") else 0.0
        sid = segmen.id() if hasattr(segmen, "id") else id(segmen)

        # Ambil titik pertama dan terakhir
        if hasattr(geom, "asPolyline"):
            pts = geom.asPolyline()
            if pts and len(pts) >= 2:
                return ((pts[0].x(), pts[0].y()), (pts[-1].x(), pts[-1].y()), panjang, sid)

        # Fallback ke multipart jika ada
        if hasattr(geom, "asMultiPolyline"):
            multi = geom.asMultiPolyline()
            if multi and len(multi) > 0 and len(multi[0]) >= 2:
                first_line = multi[0]
                last_line = multi[-1]
                return (
                    (first_line[0].x(), first_line[0].y()),
                    (last_line[-1].x(), last_line[-1].y()),
                    panjang,
                    sid,
                )

        # Fallback melalui vertex(0) dan vertex(n-1)
        if hasattr(geom, "vertexAtOffset"):
            try:
                v_start = geom.vertexAtOffset(0)
                v_end = geom.vertexAtOffset(panjang)
                return ((v_start.x(), v_start.y()), (v_end.x(), v_end.y()), panjang, sid)
            except Exception:
                pass

    return None


def ekstrak_titik_gardu(gardu: Any) -> Optional[Tuple[Tuple[float, float], Any]]:
    """Mengekstrak koordinat (x, y) dan id dari objek Gardu."""
    if isinstance(gardu, dict):
        pos = gardu.get("pos") or gardu.get("coord")
        gid = gardu.get("id", id(gardu))
        return (pos, gid)

    if hasattr(gardu, "geometry"):
        geom = gardu.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            return None
        gid = gardu.id() if hasattr(gardu, "id") else id(gardu)
        if hasattr(geom, "asPoint"):
            pt = geom.asPoint()
            return ((pt.x(), pt.y()), gid)

    return None


def bangun_graf(
    daftar_segmen: List[Any],
    daftar_gardu: Optional[List[Any]] = None,
    epsilon: float = 0.05,
) -> Dict[str, Any]:
    """Membangun representasi graf jaringan dan DisjointSet keterhubungan.

    Args:
        daftar_segmen: Kumpulan segmen JTR.
        daftar_gardu: Kumpulan titik Gardu distribusi.
        epsilon: Toleransi grid node (default 0.05 meter).

    Returns:
        Dict[str, Any]: Graf berisi disjoint_set, adj, node_gardu, node_segmen, dll.
    """
    uf = DisjointSet()
    adj = defaultdict(list)
    node_to_segmen = defaultdict(set)
    segmen_info = {}
    node_gardu = defaultdict(set)

    # 1. Daftarkan Gardu ke grid node
    if daftar_gardu:
        for g in daftar_gardu:
            res_g = ekstrak_titik_gardu(g)
            if res_g is not None:
                (gx, gy), gid = res_g
                k_g = kunci_node(gx, gy, epsilon)
                uf.make_set(k_g)
                node_gardu[k_g].add(gid)

    # 2. Proses segmen JTR
    for s in daftar_segmen:
        res_s = ekstrak_ujung_segmen(s)
        if res_s is None:
            continue
        (x1, y1), (x2, y2), panjang, sid = res_s
        k1 = kunci_node(x1, y1, epsilon)
        k2 = kunci_node(x2, y2, epsilon)

        uf.make_set(k1)
        uf.make_set(k2)
        uf.union(k1, k2)

        adj[k1].append((k2, sid, panjang))
        adj[k2].append((k1, sid, panjang))

        node_to_segmen[k1].add(sid)
        node_to_segmen[k2].add(sid)

        segmen_info[sid] = {
            "segmen_obj": s,
            "node1": k1,
            "node2": k2,
            "panjang": panjang,
        }

    return {
        "disjoint_set": uf,
        "adj": dict(adj),
        "node_to_segmen": dict(node_to_segmen),
        "segmen_info": segmen_info,
        "node_gardu": dict(node_gardu),
        "epsilon": epsilon,
    }


def cari_connected_components(graf: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Mencari semua komponen terhubung (connected components) dalam graf.

    Returns:
        List[Dict[str, Any]]: Daftar komponen terhubung dengan atribut lengkap.
    """
    uf: DisjointSet = graf["disjoint_set"]
    node_gardu = graf["node_gardu"]
    segmen_info = graf["segmen_info"]
    node_to_segmen = graf["node_to_segmen"]

    raw_comps = uf.get_components()
    daftar_komponen = []
    comp_idx = 1

    for root, nodes in raw_comps.items():
        comp_segmen_ids = set()
        comp_gardu_ids = set()

        for n in nodes:
            if n in node_to_segmen:
                comp_segmen_ids.update(node_to_segmen[n])
            if n in node_gardu:
                comp_gardu_ids.update(node_gardu[n])

        total_panjang = sum(
            segmen_info[sid]["panjang"] for sid in comp_segmen_ids if sid in segmen_info
        )

        daftar_komponen.append({
            "id_komponen": comp_idx,
            "root": root,
            "nodes": nodes,
            "segmen_ids": comp_segmen_ids,
            "jumlah_segmen": len(comp_segmen_ids),
            "panjang_total": total_panjang,
            "ada_gardu": len(comp_gardu_ids) > 0,
            "gardu_ids": comp_gardu_ids,
        })
        comp_idx += 1

    return daftar_komponen


def tandai_komponen_aktif(
    graf: Dict[str, Any],
    daftar_komponen: Optional[List[Dict[str, Any]]] = None,
    log_cb=None,
) -> Tuple[Set[int], Set[Any]]:
    """Menandai komponen terhubung yang aktif (menyentuh Gardu).

    Jika tidak ada komponen yang menyentuh Gardu sama sekali, fallback
    ke komponen terbesar dan catat peringatan log.

    Args:
        graf: Objek graf hasil `bangun_graf`.
        daftar_komponen: Hasil `cari_connected_components` (opsional dihitung otomatis).
        log_cb: Callback opsional untuk mencatat log peringatan.

    Returns:
        Tuple[Set[int], Set[Any]]: (Set ID komponen aktif, Set ID segmen aktif).
    """
    if daftar_komponen is None:
        daftar_komponen = cari_connected_components(graf)

    aktif_comp_ids = set()
    aktif_segmen_ids = set()

    for comp in daftar_komponen:
        if comp["ada_gardu"]:
            aktif_comp_ids.add(comp["id_komponen"])
            aktif_segmen_ids.update(comp["segmen_ids"])

    # Fallback ke komponen terbesar jika tidak ada yang menyentuh Gardu
    if not aktif_comp_ids and daftar_komponen:
        pesan = (
            "PERINGATAN: Tidak ada komponen jaringan yang terhubung ke Gardu! "
            "Menggunakan fallback komponen terbesar sebagai jaringan aktif."
        )
        if log_cb:
            log_cb(pesan)

        # Cari komponen terbesar berdasarkan panjang total atau jumlah segmen
        komp_terbesar = max(
            daftar_komponen,
            key=lambda c: (c["panjang_total"], c["jumlah_segmen"]),
        )
        aktif_comp_ids.add(komp_terbesar["id_komponen"])
        aktif_segmen_ids.update(komp_terbesar["segmen_ids"])

    return aktif_comp_ids, aktif_segmen_ids
