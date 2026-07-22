"""
Konfigurasi & parameter model.

Nilai-nilai di sini SAMA PERSIS dengan yang dipakai pada dashboard
(dashboard_optimasi_gym.html) supaya hasil keduanya konsisten satu sama lain.
Semua yang berlabel "ASUMSI" bisa diganti kalau sudah ada data kapasitas
alat yang sebenarnya (mis. dari wawancara pengelola gym).

Nilai ASUMSI di bawah juga bisa di-override TANPA mengedit file ini --
taruh file "gym_capacity_config.json" di folder root project (sejajar
dengan gym_scheduler/), isinya cukup key yang mau diganti, misal:

    {
      "CAPACITY_PER_SLOT": 8,
      "TURNOVER_MINUTES": 15
    }

Berguna kalau yang mengisi angka aslinya bukan kamu sendiri (mis. pengelola
gym kasih data kapasitas alat) -- mereka cukup edit JSON, tidak perlu
paham/sentuh kode Python. Lihat _apply_overrides() di bagian bawah file ini.
"""

import json
from pathlib import Path

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

WEIGHT_CONFLICT = 100   # pelanggaran mutual exclusion (hard constraint)
WEIGHT_VARIANCE = 5     # pemerataan beban antar slot
WEIGHT_FUZZY = 3        # penalti fuzzy: hindari memindah ke slot yang sudah "Tinggi"


_OVERRIDE_FILE = Path(__file__).resolve().parent.parent / "gym_capacity_config.json"


def _apply_overrides():
    if not _OVERRIDE_FILE.exists():
        return
    try:
        with open(_OVERRIDE_FILE) as f:
            overrides = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[config] Gagal membaca {_OVERRIDE_FILE.name}, override diabaikan ({e}).")
        return

    for key, value in overrides.items():
        if key in globals():
            globals()[key] = value
        else:
            print(f"[config] Peringatan: '{key}' di {_OVERRIDE_FILE.name} "
                  "bukan nama parameter yang dikenal -- diabaikan.")

    global N_SLOTS
    N_SLOTS = len(OPERATING_HOURS)


_apply_overrides()
