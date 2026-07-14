"""
Metrik evaluasi hasil penjadwalan: konflik booking, utilisasi slot,
slot kosong, dan rata-rata waktu tunggu.
"""

import math
from typing import List

from . import config


def evaluate(demand: List[int]) -> dict:
    # Kapasitas total sepanjang hari = kapasitas per slot × jumlah slot.
    # Contoh: kapasitas 5/slot × 18 slot = 90 total.
    total_capacity = config.CAPACITY_PER_SLOT * len(demand)

    # "Terpakai" itu maksimal sebesar kapasitas per slot -- kalau demand
    # melebihi kapasitas (misal demand=8, kapasitas=5), kelebihannya (3)
    # tidak dihitung sebagai "terpakai" karena secara fisik tidak mungkin
    # tertampung. min(d, CAPACITY_PER_SLOT) memotong nilai d supaya tidak
    # lebih dari kapasitas.
    used = sum(min(d, config.CAPACITY_PER_SLOT) for d in demand)

    # Persentase pemakaian dari total kapasitas yang tersedia.
    utilization_pct = used / total_capacity * 100

    # Batas demand di bawahnya sebuah slot dianggap "kosong" / kurang
    # dimanfaatkan. EMPTY_THRESHOLD_RATIO=0.4 dan kapasitas=5 -> batasnya 2
    # (demand di bawah 2 dianggap slot kosong).
    empty_threshold = config.EMPTY_THRESHOLD_RATIO * config.CAPACITY_PER_SLOT

    # Hitung berapa banyak slot yang demand-nya di bawah batas itu.
    jumlah_slot_kosong = 0
    for d in demand:
        if d < empty_threshold:
            jumlah_slot_kosong += 1
    empty_slot_pct = jumlah_slot_kosong / len(demand) * 100

    # Total "kelebihan" booking dari seluruh slot -- untuk tiap slot,
    # hitung selisih (demand - kapasitas); kalau tidak lebih, dianggap 0
    # lewat max(..., 0). Ini angka yang sama dipakai sebagai komponen
    # over_capacity di fungsi fitness() PSO.
    conflicts = sum(max(d - config.CAPACITY_PER_SLOT, 0) for d in demand)

    # --- Simulasi waktu tunggu ---
    # Ide dasarnya: kalau 1 slot kelebihan booking, orang yang kebagian
    # "sisa" harus menunggu giliran alat kosong (turnover). Karena alat
    # cuma bisa dipakai CAPACITY_PER_SLOT orang sekaligus, orang-orang
    # kelebihan ini mengantre dalam "gelombang" -- gelombang pertama
    # (sebanyak kapasitas) nunggu 1x waktu turnover, gelombang kedua
    # nunggu 2x, dst.
    waits = []
    for d in demand:
        if d > config.CAPACITY_PER_SLOT:
            # excess = jumlah orang yang tidak kebagian slot langsung.
            # Contoh: demand=8, kapasitas=5 -> excess=3 (3 orang mengantre).
            excess = d - config.CAPACITY_PER_SLOT

            # Untuk tiap orang yang mengantre (k = orang ke-1, ke-2, ...):
            for k in range(1, excess + 1):
                # k dibagi kapasitas, dibulatkan KE ATAS (math.ceil), untuk
                # tahu orang ke-k ini ada di "gelombang" antrean ke berapa.
                # Contoh (kapasitas=5): k=1..5 -> gelombang 1 (nunggu 1x
                # turnover); k=6..10 -> gelombang 2 (nunggu 2x turnover).
                gelombang_ke = math.ceil(k / config.CAPACITY_PER_SLOT)

                # Waktu tunggu orang ini = gelombang_ke × waktu 1x turnover
                # (TURNOVER_MINUTES = 20 menit, dari config.py).
                waktu_tunggu = gelombang_ke * config.TURNOVER_MINUTES
                waits.append(waktu_tunggu)

    # Rata-rata waktu tunggu dari SEMUA orang yang sempat mengantre
    # (across seluruh slot). Kalau tidak ada yang mengantre sama sekali
    # (waits kosong), rata-ratanya 0 -- supaya tidak error dibagi 0.
    if waits:
        avg_wait_minutes = sum(waits) / len(waits)
    else:
        avg_wait_minutes = 0.0

    return {
        "utilization_pct": round(utilization_pct, 1),
        "empty_slot_pct": round(empty_slot_pct, 1),
        "conflicts": int(conflicts),
        "avg_wait_minutes": round(avg_wait_minutes, 1),
    }