"""
Demo sederhana lewat command line -- tidak butuh FastAPI, cukup
pandas + numpy. Jalankan dengan:

    python cli_demo.py

Cocok untuk mengecek model bekerja dengan benar sebelum dipasang di
belakang FastAPI / Laravel.
"""

import random

from gym_scheduler import config
from gym_scheduler.data import load_dataset, dataset_summary, hourly_weights, generate_busy_day_bookings
from gym_scheduler.scheduler import optimize_schedule


def main():
    df = load_dataset("daily_gym_attendance_workout_data.csv")

    print("=== Statistik Dataset ===")
    summary = dataset_summary(df)
    for k, v in summary.items():
        if isinstance(v, dict):
            continue
        print(f"{k}: {v}")

    weights = hourly_weights(df)
    rng = random.Random(42)  # seed tetap supaya hasil bisa direproduksi
    booking_hours = generate_busy_day_bookings(weights, rng=rng)

    result = optimize_schedule(booking_hours, rng=rng)

    b, a = result["before"]["metrics"], result["after"]["metrics"]
    print("\n=== Hasil Optimasi (Fuzzy Logic + PSO) ===")
    print(f"{'Metrik':<24}{'Sebelum':>12}{'Sesudah':>12}")
    print(f"{'Konflik Booking':<24}{b['conflicts']:>12}{a['conflicts']:>12}")
    print(f"{'Utilisasi Slot (%)':<24}{b['utilization_pct']:>12}{a['utilization_pct']:>12}")
    print(f"{'Slot Kosong (%)':<24}{b['empty_slot_pct']:>12}{a['empty_slot_pct']:>12}")
    print(f"{'Rata-rata Tunggu (mnt)':<24}{b['avg_wait_minutes']:>12}{a['avg_wait_minutes']:>12}")

    print("\nDemand per slot (jam 05:00-22:00):")
    print("Sebelum :", result["before"]["demand"])
    print("Sesudah :", result["after"]["demand"])


if __name__ == "__main__":
    main()
