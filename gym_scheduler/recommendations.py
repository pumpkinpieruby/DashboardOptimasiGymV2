"""
Rekomendasi penjadwalan & saran peningkatan utilisasi.

Modul TAMBAHAN -- tidak mengubah fuzzy_logic.py, pso.py, scheduler.py, atau
metrics.py yang sudah ada. Hanya membaca hasil (demand per slot) yang sudah
dihitung modul-modul tsb, lalu menerjemahkannya jadi teks rekomendasi yang
bisa dipakai langsung di Bab IV (Pembahasan) atau Bab V (Saran) skripsi.

Ada 2 jenis rekomendasi yang dihasilkan:
  1. status_per_slot   -> status & saran tindakan untuk tiap jam operasional,
                          dihitung dari kondisi SEBELUM optimasi (kondisi
                          nyata yang perlu ditindaklanjuti pengelola gym).
  2. redistribution    -> ringkasan jam mana yang disarankan DIKURANGI
                          bebannya dan jam mana yang disarankan MENERIMA
                          tambahan booking, didapat dari selisih demand
                          sebelum vs sesudah PSO.
"""

from typing import List

from . import config
from .fuzzy_logic import classify_slot


# Ambang batas rasio (demand / kapasitas) untuk menentukan status slot.
# Sengaja dipisah dari ambang fuzzy Rendah/Sedang/Tinggi di fuzzy_logic.py
# supaya rekomendasi bisa membedakan "Tinggi tapi belum konflik" dengan
# "sudah melebihi kapasitas" -- dua kondisi ini butuh saran berbeda.
CRITICAL_RATIO = 1.0     # demand > kapasitas -> konflik nyata
WATCH_RATIO = 0.7        # mendekati kapasitas -> perlu dipantau
LOW_RATIO = 0.3          # sama dengan ambang "rendah" di fuzzy_logic.py


def _slot_status(ratio: float) -> dict:
    """Menentukan kategori status & teks saran untuk satu slot, dari rasio
    okupansinya (demand / kapasitas) pada kondisi SEBELUM optimasi."""
    if ratio > CRITICAL_RATIO:
        return {
            "status": "Kritis",
            "severity": 3,
            "saran": (
                "Melebihi kapasitas -- pertimbangkan menambah kapasitas/alat pada jam ini, "
                "menambah staf, atau mengarahkan sebagian anggota ke jam alternatif yang lebih longgar."
            ),
        }
    if ratio > WATCH_RATIO:
        return {
            "status": "Perlu Perhatian",
            "severity": 2,
            "saran": (
                "Mendekati kapasitas -- pantau tren booking pada jam ini; berpotensi jadi "
                "konflik jika jumlah anggota terus bertambah."
            ),
        }
    if ratio < LOW_RATIO:
        return {
            "status": "Kurang Optimal",
            "severity": 1,
            "saran": (
                "Okupansi rendah -- berpotensi untuk promosi (diskon jam tertentu, kelas komunitas, "
                "sesi khusus) atau dijadwalkan untuk maintenance alat."
            ),
        }
    return {
        "status": "Ideal",
        "severity": 0,
        "saran": "Okupansi seimbang, tidak perlu tindakan khusus.",
    }


def status_per_slot(demand_before: List[int]) -> List[dict]:
    """Status & saran tindakan untuk tiap jam operasional (kondisi sebelum
    optimasi -- inilah kondisi nyata yang perlu direspons pengelola gym)."""
    result = []
    for hour, demand in zip(config.OPERATING_HOURS, demand_before):
        fuzzy = classify_slot(demand, config.CAPACITY_PER_SLOT)
        status = _slot_status(fuzzy["ratio"])
        result.append({
            "hour": hour,
            "demand": demand,
            "ratio": round(fuzzy["ratio"], 2),
            "fuzzy_label": fuzzy["label"],
            **status,
        })
    return result


def redistribution_summary(demand_before: List[int], demand_after: List[int]) -> dict:
    """Ringkasan jam yang disarankan dikurangi / ditambah bebannya, dari
    selisih demand sebelum vs sesudah PSO."""
    reduce_hours, add_hours = [], []
    for hour, before, after in zip(config.OPERATING_HOURS, demand_before, demand_after):
        delta = after - before
        if delta < 0:
            reduce_hours.append({"hour": hour, "delta": delta})
        elif delta > 0:
            add_hours.append({"hour": hour, "delta": delta})

    reduce_hours.sort(key=lambda x: x["delta"])       # paling banyak berkurang duluan
    add_hours.sort(key=lambda x: -x["delta"])         # paling banyak bertambah duluan

    total_moved = sum(-r["delta"] for r in reduce_hours)

    return {
        "total_booking_dipindah": total_moved,
        "jam_dikurangi": reduce_hours,
        "jam_ditambah": add_hours,
    }


def overall_recommendation(before_metrics: dict, after_metrics: dict, redistribution: dict) -> str:
    """Satu paragraf ringkasan rekomendasi (siap-pakai untuk Bab IV/V)."""
    moved = redistribution["total_booking_dipindah"]
    conflict_drop = round(before_metrics["conflicts"] - after_metrics["conflicts"], 2)
    util_gain = round(after_metrics["utilization_pct"] - before_metrics["utilization_pct"], 2)

    parts = []
    if moved > 0:
        jam_dikurangi = ", ".join(f"{h['hour']:02d}:00" for h in redistribution["jam_dikurangi"][:3])
        jam_ditambah = ", ".join(f"{h['hour']:02d}:00" for h in redistribution["jam_ditambah"][:3])
        parts.append(
            f"Sistem merekomendasikan pemindahan {moved} booking dari jam padat "
            f"({jam_dikurangi}) ke jam yang lebih longgar ({jam_ditambah})."
        )
    if conflict_drop > 0:
        parts.append(f"Langkah ini mengeliminasi {conflict_drop} konflik penjadwalan.")
    elif conflict_drop == 0 and before_metrics["conflicts"] > 0:
        parts.append(
            f"Namun {after_metrics['conflicts']} konflik masih tersisa karena permintaan "
            f"melebihi total kapasitas fasilitas sepanjang hari -- solusi jangka panjang perlu "
            f"menambah kapasitas atau jam operasional, bukan hanya redistribusi jadwal."
        )
    if util_gain > 0:
        parts.append(f"Utilisasi fasilitas meningkat {util_gain:.1f} poin persentase.")

    return " ".join(parts) if parts else "Distribusi booking sudah cukup merata, tidak ada pemindahan yang disarankan."
