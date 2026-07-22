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
    # Simulasikan: KALAU tebakan solusi (slot_indices) ini diterapkan,
    # jadi seperti apa demand akhirnya? base_demand di-copy dulu supaya
    # data asli tidak ikut berubah (base_demand dipakai ulang untuk
    # menguji BANYAK tebakan solusi lain, jadi harus tetap utuh).
    demand = base_demand.copy()
    for s in slot_indices:
        # s = index slot tujuan 1 booking yang dipindah -> tambah 1 ke
        # slot itu (mensimulasikan "booking ini jadi terisi di sini").
        demand[s] += 1

    # Komponen 1: Total kelebihan kapasitas di seluruh slot.
    # Untuk tiap slot, hitung selisih (demand - kapasitas); kalau demand
    # tidak melebihi kapasitas, selisihnya dianggap 0 (bukan minus) lewat
    # max(..., 0). Semua selisih dijumlahkan.
    over_capacity = sum(max(d - config.CAPACITY_PER_SLOT, 0) for d in demand)

    # Komponen 2: Variansi -- ukuran statistik seberapa "timpang" sebaran
    # demand antar slot. Rumus baku: rata-rata dari kuadrat selisih tiap
    # nilai terhadap rata-rata keseluruhan. Semakin merata sebarannya,
    # semakin kecil variansinya (semakin bagus).
    mean = sum(demand) / len(demand)
    variance = sum((d - mean) ** 2 for d in demand) / len(demand)

    # Komponen 3: Penalti fuzzy -- dari fuzzy_logic.py, menjumlahkan
    # derajat "Tinggi" semua slot. Supaya PSO menghindari slot yang sudah
    # mulai padat, bukan cuma yang benar-benar melebihi kapasitas.
    fuzzy_penalty = fuzzy_high_penalty(demand, config.CAPACITY_PER_SLOT)

    # Gabungkan ketiga komponen jadi 1 angka, masing-masing dikali bobot
    # dari config.py. WEIGHT_CONFLICT (100) jauh lebih besar dari yang
    # lain supaya PSO memprioritaskan menghindari pelanggaran kapasitas
    # di atas segalanya. Semakin KECIL hasil fitness ini, semakin BAIK
    # solusinya (PSO tugasnya MEMINIMALKAN angka ini).
    return (
        over_capacity * config.WEIGHT_CONFLICT
        + variance * config.WEIGHT_VARIANCE
        + fuzzy_penalty * config.WEIGHT_FUZZY
    )


class Particle:
    """Representasi 1 'tebakan solusi' yang bergerak mencari solusi terbaik,
    meniru cara segerombolan burung mencari makanan bersama."""

    def __init__(self, n_vars: int, n_slots: int, rng: random.Random):
        # Posisi AWAL: tebakan acak slot tujuan untuk tiap booking yang
        # perlu dipindah (n_vars = jumlah booking itu). Angkanya desimal
        # (bukan integer langsung) supaya partikel bisa "bergerak halus"
        # sedikit demi sedikit -- nanti dibulatkan pakai _rounded_slots().
        self.position = [rng.uniform(0, n_slots - 1) for _ in range(n_vars)]

        # Kecepatan AWAL: juga acak, menentukan seberapa jauh & ke arah
        # mana partikel ini akan "melangkah" di iterasi pertama.
        self.velocity = [rng.uniform(-n_slots / 2, n_slots / 2) for _ in range(n_vars)]

        # pbest ("personal best") = posisi TERBAIK yang PERNAH ditemukan
        # partikel ini sendiri sepanjang proses. Di awal, disamakan dulu
        # dengan posisi saat ini (belum ada rekor lain untuk dibandingkan).
        self.pbest = list(self.position)

        # Nilai fitness dari pbest, dimulai dari infinity ("tak terhingga")
        # supaya perbandingan PERTAMA pasti kalah dan pbest_fitness auto
        # terisi dengan nilai fitness sungguhan begitu partikel pertama
        # kali dievaluasi.
        self.pbest_fitness = float("inf")


def _rounded_slots(position: List[float], n_slots: int) -> List[int]:
    """Ubah posisi partikel (angka desimal) jadi index slot yang valid
    (bilangan bulat, 0 s.d. n_slots-1)."""
    return [min(n_slots - 1, max(0, round(x))) for x in position]
    # Baca dari dalam ke luar untuk tiap elemen x:
    #   round(x)              -> bulatkan ke bilangan bulat terdekat
    #   max(0, ...)           -> kalau hasilnya negatif, paksa jadi 0
    #   min(n_slots - 1, ...) -> kalau hasilnya kelebihan, paksa jadi n_slots-1
    # Ini "menjepit" (clamp) nilai supaya selalu jadi index slot yang sah.


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

    # Kalau tidak ada booking yang perlu dipindah (hari sepi, semua slot
    # sudah cukup), tidak perlu jalankan PSO sama sekali -- langsung selesai.
    if movable_count == 0:
        return [], [0.0]

    # Bikin sekawanan partikel sekaligus (SWARM_SIZE=25 dari config.py),
    # tiap partikel mulai dari posisi acak yang BERBEDA-beda.
    particles = [Particle(movable_count, n_slots, rng) for _ in range(config.SWARM_SIZE)]

    # gbest ("global best") = posisi TERBAIK yang ditemukan SELURUH
    # kawanan (bukan cuma 1 partikel). Ini "pengetahuan bersama" yang
    # dipakai semua partikel untuk saling menarik satu sama lain.
    gbest, gbest_fitness = None, float("inf")
    history = []

    # Loop utama: ulangi proses "evaluasi -> bergerak" sebanyak ITERATIONS
    # kali (60x dari config.py). Semakin banyak iterasi, semakin besar
    # peluang kawanan menemukan solusi mendekati optimal.
    for _ in range(config.ITERATIONS):

        # --- TAHAP 1: EVALUASI ---
        # Untuk tiap partikel, nilai seberapa bagus posisinya SAAT INI,
        # lalu update rekor pribadi (pbest) dan rekor kawanan (gbest)
        # kalau ketemu yang lebih baik dari sebelumnya.
        for p in particles:
            slots = _rounded_slots(p.position, n_slots)
            f = fitness(slots, base_demand)

            if f < p.pbest_fitness:      # rekor pribadi baru?
                p.pbest_fitness = f
                p.pbest = list(p.position)

            if f < gbest_fitness:        # rekor SELURUH kawanan baru?
                gbest_fitness = f
                gbest = list(p.position)

        # Kalau diminta (track_history=True), catat gbest_fitness di
        # iterasi ini -- dipakai untuk menggambar grafik konvergensi
        # (menunjukkan solusi makin membaik seiring iterasi).
        if track_history:
            history.append(gbest_fitness)

        # --- TAHAP 2: PERGERAKAN ---
        # Update kecepatan & posisi tiap partikel berdasarkan rumus PSO
        # klasik (rumus 2.4 & 2.5 di docstring atas).
        for p in particles:
            for i in range(movable_count):
                # r1, r2 = bilangan acak 0-1, bikin gerakan tidak kaku/
                # deterministik -- ada unsur eksplorasi di tiap langkah.
                r1, r2 = rng.random(), rng.random()

                p.velocity[i] = (
                    config.W * p.velocity[i]
                    # ^ inersia: kecenderungan melanjutkan arah gerak sebelumnya

                    + config.C1 * r1 * (p.pbest[i] - p.position[i])
                    # ^ tarikan menuju rekor terbaik PRIBADI partikel ini

                    + config.C2 * r2 * (gbest[i] - p.position[i])
                    # ^ tarikan menuju rekor terbaik SELURUH kawanan
                )

                # Batasi kecepatan (velocity clamping) supaya partikel
                # tidak "meloncat" terlalu jauh dan melewatkan solusi bagus.
                p.velocity[i] = max(-n_slots / 2, min(n_slots / 2, p.velocity[i]))

                # Posisi baru = posisi lama + kecepatan yang baru dihitung.
                p.position[i] += p.velocity[i]

                # Jaga posisi tetap dalam rentang valid (0 s.d. n_slots-1).
                p.position[i] = max(0, min(n_slots - 1, p.position[i]))

    # Setelah semua iterasi selesai, gbest adalah solusi TERBAIK yang
    # pernah ditemukan sepanjang proses -- dibulatkan jadi index slot
    # integer, dikembalikan sebagai jawaban akhir.
    return _rounded_slots(gbest, n_slots), history