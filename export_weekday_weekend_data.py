"""
Mengekspor hasil eksperimen weekday vs weekend ke satu file JSON:
    experiment_results/weekday_weekend_data.json

TAMBAHAN -- tidak mengubah export_dashboard_data.py, run_experiments.py,
atau package gym_scheduler/ (kecuali fungsi baru hourly_weights_by_daytype()
yang sudah ditambahkan di data.py). Skrip ini memakai ulang run_scenario()
dan summarize() dari run_experiments.py persis seperti export_dashboard_data.py,
supaya angkanya taat asas 100% sama dengan metodologi Bab IV -- hanya bobot
jamnya (weights) yang diganti per tipe hari.

Jalankan SETELAH export_dashboard_data.py, SEBELUM build_dashboard.py:
    python export_dashboard_data.py
    python export_weekday_weekend_data.py
    python build_dashboard.py
"""

import json
from pathlib import Path

from gym_scheduler import config
from gym_scheduler.data import load_dataset, hourly_weights_by_daytype
from gym_scheduler.fuzzy_logic import classify_slot
from gym_scheduler.recommendations import status_per_slot, redistribution_summary, overall_recommendation

from run_experiments import SCENARIOS, REPEATS, run_scenario, summarize

OUT_PATH = Path("experiment_results") / "weekday_weekend_data.json"

DAY_TYPE_LABELS = {"weekday": "Hari Kerja (Senin\u2013Jumat)", "weekend": "Akhir Pekan (Sabtu\u2013Minggu)"}


def build_scenario_payload(name, params, weights, base_seed):
    records, history, (demand_before, demand_after) = run_scenario(name, params, weights, base_seed=base_seed)
    summary = summarize(records)

    before_metrics = {"conflicts": summary["conflicts_before_mean"], "utilization_pct": summary["utilization_before_mean"]}
    after_metrics = {"conflicts": summary["conflicts_after_mean"], "utilization_pct": summary["utilization_after_mean"]}
    redistribution = redistribution_summary(demand_before, demand_after)

    return {
        "params": params,
        "repeats": REPEATS,
        "summary": summary,
        "convergence": history,
        "demand_before": demand_before,
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
    weights_by_type = hourly_weights_by_daytype(df)

    payload = {"labels": DAY_TYPE_LABELS, "day_types": {}}

    # base_seed berbeda dari export_dashboard_data.py (1000) dan
    # sensitivity_analysis.py (5000) supaya tidak memakai urutan acak yang
    # persis sama; nilai ini konsisten dengan weekday_weekend_analysis.py.
    for day_type, weights in weights_by_type.items():
        print(f"Menjalankan ulang skenario untuk {day_type}...")
        payload["day_types"][day_type] = {}
        for name, params in SCENARIOS.items():
            payload["day_types"][day_type][name] = build_scenario_payload(
                name, params, weights, base_seed=7000
            )

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nSelesai. Data weekday/weekend tersimpan di: {OUT_PATH}")


if __name__ == "__main__":
    main()