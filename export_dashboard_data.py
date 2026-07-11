"""
Mengekspor seluruh data yang dibutuhkan dashboard (dashboard_optimasi_gym.html)
ke satu file JSON: experiment_results/dashboard_data.json

File ini TIDAK mengubah apa pun di package gym_scheduler/ atau run_experiments.py
-- hanya mengimpor & memanggil ulang fungsi-fungsi yang sudah ada (SCENARIOS,
run_scenario, summarize dari run_experiments.py) supaya angkanya taat asas
100% sama dengan yang dihasilkan run_experiments.py (scenario_summary.csv,
before_after.png, dst). Tambahannya di sini hanya: hasil per-slot (demand),
klasifikasi fuzzy per-slot, dan riwayat konvergensi PSO ikut disimpan dalam
bentuk JSON supaya bisa digambar ulang secara interaktif di browser
(sumber PNG di run_experiments.py tetap sebagai cadangan statis).

Jalankan SETELAH run_experiments.py (atau berdiri sendiri, karena skrip ini
menjalankan ulang skenario yang sama dengan seed yang sama):

    python export_dashboard_data.py
"""

import json
from pathlib import Path

from gym_scheduler import config
from gym_scheduler.data import load_dataset, dataset_summary, hourly_weights
from gym_scheduler.fuzzy_logic import classify_slot
from gym_scheduler.recommendations import status_per_slot, redistribution_summary, overall_recommendation

# Impor ulang skenario & fungsi dari run_experiments.py supaya persis sama
# (nama skenario, n_bookings, peak_skew, jumlah pengulangan, base_seed).
from run_experiments import SCENARIOS, REPEATS, run_scenario, summarize

OUT_PATH = Path("experiment_results") / "dashboard_data.json"


def build_scenario_payload(name: str, params: dict, weights):
    records, history, (demand_before, demand_after) = run_scenario(name, params, weights)
    summary = summarize(records)

    before_metrics = {
        "conflicts": summary["conflicts_before_mean"],
        "utilization_pct": summary["utilization_before_mean"],
    }
    after_metrics = {
        "conflicts": summary["conflicts_after_mean"],
        "utilization_pct": summary["utilization_after_mean"],
    }
    redistribution = redistribution_summary(demand_before, demand_after)

    return {
        "params": params,
        "repeats": REPEATS,
        "summary": summary,                      # mean & std tiap metrik (30x pengulangan)
        "convergence": history,                   # kurva fitness gbest per iterasi (1 run representatif)
        "demand_before": demand_before,           # okupansi per slot, 1 run representatif
        "demand_after": demand_after,
        "fuzzy_before": [classify_slot(d, config.CAPACITY_PER_SLOT) for d in demand_before],
        "fuzzy_after": [classify_slot(d, config.CAPACITY_PER_SLOT) for d in demand_after],
        "recommendations": {
            "status_per_slot": status_per_slot(demand_before),
            "redistribution": redistribution,
            "summary_text": overall_recommendation(before_metrics, after_metrics, redistribution),
        },
    }


def main():
    df = load_dataset("daily_gym_attendance_workout_data.csv")
    weights = hourly_weights(df)

    payload = {
        "config": {
            "operating_hours": config.OPERATING_HOURS,
            "capacity_per_slot": config.CAPACITY_PER_SLOT,
            "turnover_minutes": config.TURNOVER_MINUTES,
            "empty_threshold_ratio": config.EMPTY_THRESHOLD_RATIO,
            "swarm_size": config.SWARM_SIZE,
            "iterations": config.ITERATIONS,
            "w": config.W,
            "c1": config.C1,
            "c2": config.C2,
            "weight_conflict": config.WEIGHT_CONFLICT,
            "weight_variance": config.WEIGHT_VARIANCE,
            "weight_fuzzy": config.WEIGHT_FUZZY,
        },
        "dataset_summary": dataset_summary(df),
        "scenarios": {},
    }

    for name, params in SCENARIOS.items():
        print(f"Menjalankan ulang skenario: {name} ({REPEATS}x, untuk ekspor JSON)...")
        payload["scenarios"][name] = build_scenario_payload(name, params, weights)

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nSelesai. Data dashboard tersimpan di: {OUT_PATH}")


if __name__ == "__main__":
    main()
