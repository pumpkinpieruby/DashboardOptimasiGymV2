"""
Metrik evaluasi hasil penjadwalan: konflik booking, utilisasi slot,
slot kosong, dan rata-rata waktu tunggu.
"""

import math
from typing import List

from . import config


def evaluate(demand: List[int]) -> dict:
    total_capacity = config.CAPACITY_PER_SLOT * len(demand)
    used = sum(min(d, config.CAPACITY_PER_SLOT) for d in demand)
    utilization_pct = used / total_capacity * 100

    empty_threshold = config.EMPTY_THRESHOLD_RATIO * config.CAPACITY_PER_SLOT
    empty_slot_pct = sum(1 for d in demand if d < empty_threshold) / len(demand) * 100

    conflicts = sum(max(d - config.CAPACITY_PER_SLOT, 0) for d in demand)

    waits = []
    for d in demand:
        if d > config.CAPACITY_PER_SLOT:
            excess = d - config.CAPACITY_PER_SLOT
            for k in range(1, excess + 1):
                waits.append(math.ceil(k / config.CAPACITY_PER_SLOT) * config.TURNOVER_MINUTES)
    avg_wait_minutes = sum(waits) / len(waits) if waits else 0.0

    return {
        "utilization_pct": round(utilization_pct, 1),
        "empty_slot_pct": round(empty_slot_pct, 1),
        "conflicts": int(conflicts),
        "avg_wait_minutes": round(avg_wait_minutes, 1),
    }
