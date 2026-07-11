"""
FastAPI engine untuk model Fuzzy Logic + PSO.

Sesuai arsitektur pada Bab III skripsi: Laravel (Blade + Bootstrap 5)
berperan sebagai lapisan antarmuka & manajemen data, sedangkan optimasi
penjadwalan dihitung di sini (Python/FastAPI) dan hasilnya dikembalikan
sebagai JSON untuk ditampilkan Laravel.

Menjalankan servernya:
    uvicorn gym_scheduler.api:app --reload --port 8000

Contoh pemanggilan endpoint:
    POST /optimize
    {
        "n_bookings": 80,
        "capacity_per_slot": 5,
        "seed": 42
    }
"""

import random

from fastapi import FastAPI
from pydantic import BaseModel

from . import config
from .data import load_dataset, dataset_summary, hourly_weights, generate_busy_day_bookings
from .scheduler import optimize_schedule

app = FastAPI(title="Gym Scheduler Optimization Engine", version="1.0.0")

DATASET_PATH = "daily_gym_attendance_workout_data.csv"


class OptimizeRequest(BaseModel):
    n_bookings: int = config.BUSY_DAY_BOOKINGS
    seed: int | None = None
    track_history: bool = False

    # Catatan: kapasitas per slot SENGAJA tidak dibuat bisa di-override lewat
    # request. config.CAPACITY_PER_SLOT dipakai banyak fungsi sebagai nilai
    # global, jadi mengubahnya di tengah request bisa bentrok kalau ada
    # beberapa request datang bersamaan (concurrent). Untuk keperluan
    # pengujian dengan kapasitas berbeda-beda, pakai run_experiments.py yang
    # jalan satu per satu (sekuensial), bukan lewat endpoint ini.


@app.get("/dataset-summary")
def get_dataset_summary():
    """Statistik deskriptif dataset -- dipakai untuk kartu KPI & grafik
    di halaman dashboard Laravel."""
    df = load_dataset(DATASET_PATH)
    return dataset_summary(df)


@app.post("/optimize")
def optimize(req: OptimizeRequest):
    """Membangkitkan skenario hari sibuk dari pola data asli, lalu
    menjalankan Fuzzy Logic + PSO dan mengembalikan metrik sebelum/sesudah."""
    df = load_dataset(DATASET_PATH)
    weights = hourly_weights(df)
    rng = random.Random(req.seed)
    booking_hours = generate_busy_day_bookings(weights, n_bookings=req.n_bookings, rng=rng)

    result = optimize_schedule(booking_hours, rng=rng, track_history=req.track_history)
    return result


@app.get("/health")
def health():
    return {"status": "ok"}
