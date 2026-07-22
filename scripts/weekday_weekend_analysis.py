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
    """
    n_bookings = n_bookings or config.BUSY_DAY_BOOKINGS
    peak_skew = peak_skew if peak_skew is not None else config.PEAK_SKEW
    rng = rng or random.Random()

    skewed = [w ** peak_skew for w in weights]
    return rng.choices(config.OPERATING_HOURS, weights=skewed, k=n_bookings)