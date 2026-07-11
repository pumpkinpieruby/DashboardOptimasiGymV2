"""
Particle Swarm Optimization (PSO) untuk redistribusi booking.

Variabel keputusan
------------------
Hanya booking pada slot yang MELEBIHI kapasitas yang perlu dicarikan slot
baru ("booking dipindah"). Booking lain dibiarkan di slot pilihan awal
(soft constraint: meminimalkan gangguan terhadap preferensi pengguna).

Posisi partikel = daftar slot tujuan (indeks 0..N_SLOTS-1), satu nilai
per booking yang dipindah.

Update kecepatan & posisi memakai rumus (2.4) & (2.5) pada Bab II:
    v_i(t+1) = w*v_i(t) + c1*r1*(pbest_i - x_i(t)) + c2*r2*(gbest - x_i(t))
    x_i(t+1) = x_i(t) + v_i(t+1)
"""

import random
from typing import List

from . import config
from .fuzzy_logic import fuzzy_high_penalty


def fitness(slot_indices: List[int], base_demand: List[int]) -> float:
    """Fungsi objektif yang diminimalkan PSO.

    Terdiri dari 3 komponen:
      1. Pelanggaran mutual exclusion (kapasitas terlampaui) -- bobot terbesar
      2. Variansi beban antar slot (semakin merata semakin baik)
      3. Penalti fuzzy: menghindari slot yang berstatus 'Tinggi'
    """
    demand = base_demand.copy()
    for s in slot_indices:
        demand[s] += 1

    over_capacity = sum(max(d - config.CAPACITY_PER_SLOT, 0) for d in demand)
    mean = sum(demand) / len(demand)
    variance = sum((d - mean) ** 2 for d in demand) / len(demand)
    fuzzy_penalty = fuzzy_high_penalty(demand, config.CAPACITY_PER_SLOT)

    return (
        over_capacity * config.WEIGHT_CONFLICT
        + variance * config.WEIGHT_VARIANCE
        + fuzzy_penalty * config.WEIGHT_FUZZY
    )


class Particle:
    def __init__(self, n_vars: int, n_slots: int, rng: random.Random):
        self.position = [rng.uniform(0, n_slots - 1) for _ in range(n_vars)]
        self.velocity = [rng.uniform(-n_slots / 2, n_slots / 2) for _ in range(n_vars)]
        self.pbest = list(self.position)
        self.pbest_fitness = float("inf")


def _rounded_slots(position: List[float], n_slots: int) -> List[int]:
    return [min(n_slots - 1, max(0, round(x))) for x in position]


def run_pso(movable_count: int, base_demand: List[int], rng: random.Random = None,
            track_history: bool = False):
    """Menjalankan PSO untuk menentukan slot tujuan tiap booking yang dipindah.

    Parameters
    ----------
    movable_count : jumlah booking yang perlu dicarikan slot baru
    base_demand   : demand awal per slot HANYA dari booking yang tidak dipindah
    rng           : random.Random, supaya hasil bisa direproduksi (opsional)
    track_history : jika True, ikut mengembalikan riwayat fitness terbaik
                    tiap iterasi (dipakai untuk kurva konvergensi di Bab IV)

    Returns
    -------
    (target_slots, history) : list slot tujuan (index) & riwayat fitness gbest
    """
    rng = rng or random.Random()
    n_slots = config.N_SLOTS

    if movable_count == 0:
        return [], [0.0]

    particles = [Particle(movable_count, n_slots, rng) for _ in range(config.SWARM_SIZE)]
    gbest, gbest_fitness = None, float("inf")
    history = []

    for _ in range(config.ITERATIONS):
        for p in particles:
            slots = _rounded_slots(p.position, n_slots)
            f = fitness(slots, base_demand)
            if f < p.pbest_fitness:
                p.pbest_fitness = f
                p.pbest = list(p.position)
            if f < gbest_fitness:
                gbest_fitness = f
                gbest = list(p.position)

        if track_history:
            history.append(gbest_fitness)

        for p in particles:
            for i in range(movable_count):
                r1, r2 = rng.random(), rng.random()
                p.velocity[i] = (
                    config.W * p.velocity[i]
                    + config.C1 * r1 * (p.pbest[i] - p.position[i])
                    + config.C2 * r2 * (gbest[i] - p.position[i])
                )
                p.velocity[i] = max(-n_slots / 2, min(n_slots / 2, p.velocity[i]))
                p.position[i] += p.velocity[i]
                p.position[i] = max(0, min(n_slots - 1, p.position[i]))

    return _rounded_slots(gbest, n_slots), history
