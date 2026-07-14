"""
Konfigurasi & parameter model.

Nilai-nilai di sini SAMA PERSIS dengan yang dipakai pada dashboard
(dashboard_optimasi_gym.html) supaya hasil keduanya konsisten satu sama lain.
Semua yang berlabel "ASUMSI" bisa diganti kalau sudah ada data kapasitas
alat yang sebenarnya (mis. dari wawancara pengelola gym).
"""

# --- Jam operasional gym -------------------------------------------------
OPERATING_HOURS = list(range(5, 23))   # 05:00 s.d. 22:00 -> 18 slot per hari
N_SLOTS = len(OPERATING_HOURS)

# --- ASUMSI kapasitas & pola kunjungan -----------------------------------
CAPACITY_PER_SLOT = 5          # kapasitas gym (orang) per slot 1 jam
TURNOVER_MINUTES = 20          # rata-rata waktu sampai 1 slot alat kosong kembali
EMPTY_THRESHOLD_RATIO = 0.4    # slot dianggap "kosong" jika terisi < 40% kapasitas
BUSY_DAY_BOOKINGS = 80         # jumlah booking pada skenario "hari sibuk"
PEAK_SKEW = 1.8                # memperbesar kontras jam ramai vs sepi

# --- Parameter PSO -------------------------------
SWARM_SIZE = 25
ITERATIONS = 60
W = 0.7     # inertia weight
C1 = 2.0    # koefisien kognitif (menuju pbest)
C2 = 2.0    # koefisien sosial (menuju gbest)

# --- Bobot fungsi fitness (semakin besar, semakin "mahal" pelanggarannya) --
WEIGHT_CONFLICT = 100   # pelanggaran mutual exclusion (hard constraint)
WEIGHT_VARIANCE = 5     # pemerataan beban antar slot
WEIGHT_FUZZY = 3        # penalti fuzzy: hindari memindah ke slot yang sudah "Tinggi"
