"""
Orkestrasi model: menggabungkan data, Fuzzy Logic, PSO, dan metrik
menjadi satu alur "optimize_schedule()" -- ini fungsi utama yang dipanggil
baik oleh CLI demo maupun endpoint FastAPI.
"""

import random
from typing import List

from . import config
from .fuzzy_logic import classify_slot
from .pso import run_pso
from .metrics import evaluate


def demand_by_slot(booking_hours: List[int]) -> List[int]:
    """Hitung berapa banyak booking jatuh di tiap slot jam operasional."""
    # Siapkan list demand kosong (semua 0), panjangnya = jumlah slot.
    demand = [0] * config.N_SLOTS

    for h in booking_hours:
        # config.OPERATING_HOURS.index(h) -- cari h (misal jam 8) ada di
        # posisi ke berapa di daftar OPERATING_HOURS ([5,6,7,8,...,22]).
        # Karena OPERATING_HOURS mulai dari 5, jam 8 ada di index ke-3.
        # Index inilah yang dipakai untuk menambah hitungan di list demand.
        demand[config.OPERATING_HOURS.index(h)] += 1
    return demand


def split_movable(booking_hours: List[int]):
    """Booking yang MELEBIHI kapasitas slotnya ditandai untuk dipindah;
    sisanya tetap ('fixed') di slot pilihan awal."""

    # Kelompokkan semua booking berdasarkan jam pilihannya.
    # Contoh hasil by_slot: {8: [8,8,8,8,8,8,8], 17: [17,17], ...}
    # -- key = jam, value = list berisi jam itu berulang sebanyak booking-nya.
    by_slot = {}
    for h in booking_hours:
        if h not in by_slot:
            by_slot[h] = []
        by_slot[h].append(h)

    fixed, movable_count = [], 0
    for group in by_slot.values():
        # Untuk tiap kelompok jam, N booking PERTAMA (sebanyak kapasitas)
        # dibiarkan tetap ("fixed") -- tidak perlu dicarikan slot baru.
        # group[:CAPACITY_PER_SLOT] mengambil maksimal CAPACITY_PER_SLOT
        # elemen pertama dari list (kalau groupnya lebih pendek dari itu,
        # ambil semuanya saja, tidak error).
        fixed.extend(group[: config.CAPACITY_PER_SLOT])

        # Sisanya (kalau ada kelebihan) dihitung sebagai booking yang perlu
        # dipindah. max(0, ...) memastikan tidak jadi minus kalau group-nya
        # ternyata lebih sedikit dari kapasitas (tidak ada kelebihan).
        movable_count += max(0, len(group) - config.CAPACITY_PER_SLOT)

    return fixed, movable_count


def repair_hard_constraint(demand: List[int]) -> List[int]:
    """Perbaikan akhir: pastikan mutual exclusion benar-benar terpenuhi
    (kapasitas tidak pernah dilampaui), walau PSO belum menemukan solusi
    yang sempurna sekalipun."""
    d = demand.copy()

    # Ulangi maksimal 2000 kali (angka aman supaya tidak infinite loop
    # kalau ada kondisi aneh yang tidak terduga).
    for _ in range(2000):
        # Cari slot PERTAMA yang masih melebihi kapasitas.
        over_idx = None
        for i in range(len(d)):
            if d[i] > config.CAPACITY_PER_SLOT:
                over_idx = i
                break

        # Kalau tidak ada lagi slot yang melebihi kapasitas, tugas selesai
        # -- hentikan loop lebih awal (tidak perlu tunggu sampai 2000x).
        if over_idx is None:
            break

        # Cari slot yang PALING KOSONG (demand paling kecil) sebagai tujuan
        # pemindahan. d.index(min(d)) -- cari posisi dari nilai terkecil
        # di list d.
        under_idx = d.index(min(d))

        # Kalau slot paling kosong SEKALIPUN sudah mencapai kapasitas,
        # artinya sudah tidak ada tempat aman untuk dipindah kemanapun --
        # hentikan (ini terjadi di skenario overload, seperti yang kita
        # bahas sebelumnya, total permintaan > total kapasitas).
        if d[under_idx] >= config.CAPACITY_PER_SLOT:
            break

        # Geser 1 booking: kurangi dari slot yang kelebihan, tambahkan ke
        # slot yang paling kosong.
        d[over_idx] -= 1
        d[under_idx] += 1

    return d


def optimize_schedule(booking_hours: List[int], rng: random.Random = None,
                       track_history: bool = False) -> dict:
    """Menjalankan satu siklus penuh: evaluasi kondisi awal (sebelum),
    Fuzzy Logic + PSO, perbaikan hard constraint, lalu evaluasi hasil akhir
    (sesudah).

    Returns dict berisi demand & metrik sebelum/sesudah, klasifikasi fuzzy
    per slot, dan (opsional) riwayat konvergensi PSO.
    """
    if rng is None:
        rng = random.Random()

    # --- Langkah 1: Hitung kondisi SEBELUM optimasi ---
    before_demand = demand_by_slot(booking_hours)
    before_metrics = evaluate(before_demand)   # dari metrics.py

    # --- Langkah 2: Pisahkan booking yang perlu dipindah ---
    fixed, movable_count = split_movable(booking_hours)
    # base_demand = demand HANYA dari booking yang "fixed" (tidak dipindah)
    # -- ini titik awal yang dipakai PSO untuk mencari slot tujuan terbaik.
    base_demand = demand_by_slot(fixed)

    # --- Langkah 3: Jalankan Fuzzy Logic + PSO ---
    # run_pso() (dari pso.py) mencari kombinasi slot tujuan terbaik untuk
    # booking yang movable, sambil menghindari slot yang fuzzy-nya "Tinggi"
    # (fuzzy_high_penalty ada di dalam fungsi fitness-nya PSO).
    target_slots, history = run_pso(movable_count, base_demand, rng=rng,
                                     track_history=track_history)

    # --- Langkah 4: Terapkan hasil PSO, lalu perbaiki kalau masih ada
    #     pelanggaran kapasitas ---
    after_demand = base_demand.copy()
    for s in target_slots:
        after_demand[s] += 1
    after_demand = repair_hard_constraint(after_demand)   # safety net terakhir

    # --- Langkah 5: Hitung kondisi SESUDAH optimasi ---
    after_metrics = evaluate(after_demand)

    # --- Langkah 6: Klasifikasi fuzzy per slot, untuk sebelum & sesudah
    #     (dipakai tabel "Tingkat Kepadatan per Slot" di dashboard) ---
    fuzzy_before = [classify_slot(d, config.CAPACITY_PER_SLOT) for d in before_demand]
    fuzzy_after = [classify_slot(d, config.CAPACITY_PER_SLOT) for d in after_demand]

    # Kumpulkan semua hasil jadi 1 dictionary besar, siap dipakai pemanggil
    # fungsi ini (cli_demo.py, api.py, export_dashboard_data.py, dll).
    return {
        "operating_hours": config.OPERATING_HOURS,
        "before": {"demand": before_demand, "metrics": before_metrics, "fuzzy": fuzzy_before},
        "after": {"demand": after_demand, "metrics": after_metrics, "fuzzy": fuzzy_after},
        "pso_history": history,
    }