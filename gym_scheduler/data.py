"""
Memuat dataset CSV & membangun skenario "hari sibuk" untuk simulasi.

Dataset asli (daily_gym_attendance_workout_data.csv) berisi data kehadiran
& latihan individual -- bukan data booking dengan kapasitas alat. Karena
itu, pola jam check-in ASLI pada dataset dipakai sebagai bobot untuk
membangkitkan skenario booking pada satu hari sibuk (lihat Bab III,
bagian skenario pengujian "jam sibuk / kepadatan tinggi").
"""

import random
from typing import List

import pandas as pd

from . import config


def load_dataset(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["hour"] = df["check_in_time"].str.split(":").str[0].astype(int)
    return df


def dataset_summary(df: pd.DataFrame) -> dict:
    """Statistik deskriptif dasar (dipakai kartu KPI pada dashboard)."""
    present = df[df["attendance_status"] == "Present"]
    membership_counts = df["membership_type"].value_counts().to_dict()
    top_membership = max(membership_counts, key=membership_counts.get)

    return {
        "total_records": int(len(df)),
        "attendance_rate_pct": round(len(present) / len(df) * 100, 1),
        "avg_duration_minutes": round(present["workout_duration_minutes"].mean(), 1),
        "top_membership_type": top_membership,
        "top_membership_count": int(membership_counts[top_membership]),
        "monthly_present_counts": (
            present.assign(month=present["visit_date"].str.slice(0, 7))
            .groupby("month").size().to_dict()
        ),
        "hourly_present_counts": present.groupby("hour").size().to_dict(),
        "membership_counts": membership_counts,
        "workout_type_counts": df["workout_type"].value_counts().to_dict(),
    }


def hourly_weights(df: pd.DataFrame) -> List[float]:
    """Bobot per jam operasional, diambil dari jumlah kunjungan Present asli
    pada tiap jam (jam yang tidak muncul di data diberi bobot minimal 1)."""
    present = df[df["attendance_status"] == "Present"]
    counts = present.groupby("hour").size().to_dict()
    return [counts.get(h, 1) for h in config.OPERATING_HOURS]


def hourly_weights_by_daytype(df: pd.DataFrame) -> dict:
    """Sama seperti hourly_weights(), tapi dipisah untuk hari kerja (Senin-
    Jumat) dan akhir pekan (Sabtu-Minggu), memakai kolom visit_date.

    TAMBAHAN -- tidak mengubah hourly_weights() asli, supaya dashboard &
    eksperimen Bab IV yang sudah ada tetap memakai bobot gabungan seperti
    semula. Fungsi ini dipakai khusus oleh analisis weekday/weekend.
    """
    d = df.copy()
    d["_dow"] = pd.to_datetime(d["visit_date"]).dt.dayofweek  # 0=Senin ... 6=Minggu
    present = d[d["attendance_status"] == "Present"]

    weekday_present = present[present["_dow"] < 5]
    weekend_present = present[present["_dow"] >= 5]

    weekday_counts = weekday_present.groupby("hour").size().to_dict()
    weekend_counts = weekend_present.groupby("hour").size().to_dict()

    return {
        "weekday": [weekday_counts.get(h, 1) for h in config.OPERATING_HOURS],
        "weekend": [weekend_counts.get(h, 1) for h in config.OPERATING_HOURS],
    }


def generate_busy_day_bookings(weights: List[float], n_bookings: int = None,
                                peak_skew: float = None, rng: random.Random = None) -> List[int]:
    """Membangkitkan daftar jam booking untuk skenario hari sibuk.

    Bobot dipangkatkan dengan `peak_skew` supaya kontras jam ramai/sepi
    lebih terasa, lalu dipakai untuk sampling acak berbobot.
    Mengembalikan list berisi jam booking (bukan objek booking penuh --
    id booking cukup diwakili oleh posisinya di list).

    CATATAN -- fungsi ini KHUSUS untuk skenario simulasi (Bab IV: Normal /
    Jam Sibuk / Konflik Jadwal, dipakai run_experiments.py &
    export_dashboard_data.py). Kalau sudah ada data booking ASLI, pakai
    load_real_bookings() + booking_hours_from_log() di bawah, bukan fungsi
    ini -- generate_busy_day_bookings() sengaja TIDAK diubah supaya hasil
    eksperimen Bab IV yang sudah tercatat di skripsi tetap reproducible.
    """
    n_bookings = n_bookings or config.BUSY_DAY_BOOKINGS
    peak_skew = peak_skew if peak_skew is not None else config.PEAK_SKEW
    rng = rng or random.Random()

    skewed = [w ** peak_skew for w in weights]
    return rng.choices(config.OPERATING_HOURS, weights=skewed, k=n_bookings)


# ============================================================================
# --- Jalur DATA BOOKING ASLI (real) -----------------------------------------
# Bagian di bawah ini TIDAK dipakai oleh run_experiments.py / dashboard Bab IV
# (yang tetap memakai dataset proxy + generate_busy_day_bookings di atas, demi
# reproducibility hasil skripsi). Fungsi-fungsi ini untuk dipakai TERPISAH,
# saat sistem sudah punya log booking sungguhan (mis. hasil export Google
# Form/Sheet booking gym), lewat script semacam run_live_example.py.
# ============================================================================

def clean_booking_dataframe(df: pd.DataFrame, date_column: str, hour_column: str) -> pd.DataFrame:
    """Logika pembersihan tanggal/jam yang DIPAKAI BERSAMA oleh semua sumber
    data booking asli -- load_real_bookings() (CSV) di bawah, dan
    sync_google_sheet.py (Google Sheets) di root project. Satu tempat saja,
    supaya perilaku "baris mana yang dianggap kotor/valid" konsisten di
    semua sumber, tidak ditulis ulang terpisah-pisah dan gampang ketinggalan
    sinkron kalau salah satu diubah di kemudian hari.

    df sudah harus punya kolom date_column & hour_column (mentah, format
    apa saja); hasilnya df yang sama ditambah kolom _date (datetime) dan
    _hour (int, sudah difilter ke config.OPERATING_HOURS).
    """
    if date_column not in df.columns or hour_column not in df.columns:
        raise ValueError(
            f"Kolom '{date_column}' dan/atau '{hour_column}' tidak ditemukan. "
            f"Kolom yang tersedia: {list(df.columns)}. Sesuaikan parameter "
            "date_column/hour_column dengan nama kolom aslinya."
        )

    df = df.copy()
    df["_date"] = pd.to_datetime(df[date_column], errors="coerce")

    def _parse_hour(value):
        if pd.isna(value) or str(value).strip() == "":
            return None
        s = str(value).strip().replace(".", ":")
        try:
            return int(s.split(":")[0]) if ":" in s else int(float(s))
        except ValueError:
            return None

    df["_hour"] = df[hour_column].apply(_parse_hour)

    n_before = len(df)
    df = df.dropna(subset=["_date", "_hour"]).copy()
    df["_hour"] = df["_hour"].astype(int)
    df = df[df["_hour"].isin(config.OPERATING_HOURS)]
    n_dropped = n_before - len(df)
    if n_dropped:
        print(f"[clean_booking_dataframe] {n_dropped} baris dilewati "
              f"(tanggal/jam kosong, tidak valid, atau di luar jam operasional).")

    return df


def load_real_bookings(csv_path: str, date_column: str = "tanggal_booking",
                        hour_column: str = "jam_booking") -> pd.DataFrame:
    """Memuat log booking ASLI dari CSV dan menyiapkannya untuk dipakai
    fungsi booking_hours_from_log() / rolling_hourly_weights() di bawah.

    Kolom yang dibutuhkan (nama kolom bisa beda -- tinggal isi parameter
    date_column / hour_column sesuai nama kolom asli hasil export Google
    Form/Sheet kamu, TIDAK perlu ubah isi CSV-nya):
        - date_column : tanggal booking, format apa saja yang bisa dibaca
                        pandas (mis. "2026-07-14" atau "14/07/2026").
        - hour_column : jam booking -- boleh angka (8) ATAU string jam
                        ("08:00", "08.00"), dua-duanya otomatis dikonversi
                        jadi integer jam operasional.

    Baris dengan tanggal/jam yang tidak valid atau di luar jam operasional
    gym (lihat config.OPERATING_HOURS) otomatis dibuang, dengan pesan di
    konsol supaya ketahuan kalau ada data kotor yang perlu dicek manual.
    """
    df = pd.read_csv(csv_path)
    return clean_booking_dataframe(df, date_column, hour_column)


def booking_hours_from_log(df: pd.DataFrame, start_date=None, end_date=None) -> List[int]:
    """Ambil daftar jam booking (List[int]) dari log booking asli yang sudah
    dimuat load_real_bookings() -- hasilnya siap dipakai LANGSUNG sebagai
    argumen scheduler.demand_by_slot() / scheduler.optimize_schedule(),
    tanpa lewat generate_busy_day_bookings() lagi.

    start_date/end_date (opsional, inklusif) membatasi periode -- misal
    booking untuk "hari ini" saja saat mau menjalankan optimasi harian.
    """
    d = df
    if start_date is not None:
        d = d[d["_date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        d = d[d["_date"] <= pd.to_datetime(end_date)]
    return d["_hour"].astype(int).tolist()


def rolling_hourly_weights(df: pd.DataFrame, as_of=None, window_days: int = 28) -> List[float]:
    """Versi hourly_weights() yang dihitung dari ROLLING WINDOW log booking
    asli (default: 4 minggu/28 hari terakhir sebelum `as_of`), bukan dari
    seluruh histori sekaligus lalu dipakai selamanya.

    Panggil ulang fungsi ini tiap kali mau menjalankan optimasi baru (mis.
    dijadwalkan tiap malam lewat cron, atau tiap kali admin buka dashboard)
    supaya bobot jam ramai ikut menyesuaikan pola terbaru -- pola jam ramai
    masa ujian bisa beda jauh dari masa liburan, dan window 4 minggu bikin
    bobotnya "lupa" pola lama secara bertahap alih-alih membeku di histori.

    as_of default-nya tanggal booking terbaru yang ada di df (dipakai kalau
    mau lihat window "s.d. hari ini"); isi manual kalau mau hitung ulang
    bobot per titik waktu tertentu di masa lalu.
    """
    as_of = pd.to_datetime(as_of) if as_of is not None else df["_date"].max()
    window_start = as_of - pd.Timedelta(days=window_days)

    recent = df[(df["_date"] > window_start) & (df["_date"] <= as_of)]
    counts = recent.groupby("_hour").size().to_dict()
    return [counts.get(h, 1) for h in config.OPERATING_HOURS]