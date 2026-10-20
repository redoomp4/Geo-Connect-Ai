"""Modul konfigurasi dan struktur data untuk GeoConnect-AI.

Menyediakan dataclass untuk toleransi analisis, konfigurasi pipeline,
hasil validasi, dan ringkasan eksekusi.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToleransiConfig:
    """Pengaturan toleransi jarak (dalam satuan meter) untuk analisis topologi."""

    jtr_gardu_m: float = 10.0
    dangling_m: float = 8.0
    app_cover_m: float = 0.5
    app_usulan_maks_m: float = 50.0
    epsilon_node_m: float = 0.05


@dataclass
class HasilValidasi:
    """Hasil pemeriksaan validasi layer input."""

    valid: List[Any] = field(default_factory=list)
    bermasalah: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PipelineConfig:
    """Konfigurasi lengkap eksekusi pipeline GeoConnect-AI."""

    layer_gardu: Any = None
    layer_jtr: Any = None
    layer_sltr: Optional[Any] = None
    layer_app: Any = None

    field_id_gardu: Optional[str] = None
    field_id_jtr: Optional[str] = None
    field_id_sltr: Optional[str] = None
    field_id_app: Optional[str] = None

    toleransi: ToleransiConfig = field(default_factory=ToleransiConfig)
    crs_kerja_auth_id: Optional[str] = None

    proses_snapping: bool = True
    proses_dangling: bool = True
    proses_anomali_app: bool = True
    proses_styling: bool = True
    proses_layer_group: bool = True


@dataclass
class HasilPipeline:
    """Hasil akhir pemrosesan pipeline topologi."""

    sukses: bool = False
    pesan_error: Optional[str] = None
    waktu_eksekusi_detik: float = 0.0

    layer_jtr_snapped: Optional[Any] = None
    layer_dangling: Optional[Any] = None
    layer_app_anomali: Optional[Any] = None
    layer_sltr_usulan: Optional[Any] = None

    ringkasan: Dict[str, Any] = field(default_factory=dict)
    data_bermasalah: List[Dict[str, Any]] = field(default_factory=list)
