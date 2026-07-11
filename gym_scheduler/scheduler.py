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
    demand = [0] * config.N_SLOTS
    for h in booking_hours:
        demand[config.OPERATING_HOURS.index(h)] += 1
    return demand


def split_movable(booking_hours: List[int]):
    """Booking yang MELEBIHI kapasitas slotnya ditandai untuk dipindah;
    sisanya tetap ('fixed') di slot pilihan awal."""
    by_slot = {}
    for h in booking_hours:
        by_slot.setdefault(h, []).append(h)

    fixed, movable_count = [], 0
    for group in by_slot.values():
        fixed.extend(group[: config.CAPACITY_PER_SLOT])
        movable_count += max(0, len(group) - config.CAPACITY_PER_SLOT)
    return fixed, movable_count


def repair_hard_constraint(demand: List[int]) -> List[int]:
    """Perbaikan akhir: pastikan mutual exclusion benar-benar terpenuhi
    (kapasitas tidak pernah dilampaui), walau PSO belum menemukan solusi
    yang sempurna sekalipun."""
    d = demand.copy()
    for _ in range(2000):
        over_idx = next((i for i, v in enumerate(d) if v > config.CAPACITY_PER_SLOT), None)
        if over_idx is None:
            break
        under_idx = d.index(min(d))
        if d[under_idx] >= config.CAPACITY_PER_SLOT:
            break  # sudah tidak ada slot yang longgar
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
    rng = rng or random.Random()

    before_demand = demand_by_slot(booking_hours)
    before_metrics = evaluate(before_demand)

    fixed, movable_count = split_movable(booking_hours)
    base_demand = demand_by_slot(fixed)

    target_slots, history = run_pso(movable_count, base_demand, rng=rng,
                                     track_history=track_history)

    after_demand = base_demand.copy()
    for s in target_slots:
        after_demand[s] += 1
    after_demand = repair_hard_constraint(after_demand)
    after_metrics = evaluate(after_demand)

    fuzzy_before = [classify_slot(d, config.CAPACITY_PER_SLOT) for d in before_demand]
    fuzzy_after = [classify_slot(d, config.CAPACITY_PER_SLOT) for d in after_demand]

    return {
        "operating_hours": config.OPERATING_HOURS,
        "before": {"demand": before_demand, "metrics": before_metrics, "fuzzy": fuzzy_before},
        "after": {"demand": after_demand, "metrics": after_metrics, "fuzzy": fuzzy_after},
        "pso_history": history,
    }
