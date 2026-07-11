"""
Skrip pengujian untuk Bab IV (Hasil dan Pembahasan).

Mengikuti rancangan eksperimen pada Bab III skripsi: tiga skenario
pengujian -- (1) kondisi normal/penggunaan merata, (2) jam sibuk/kepadatan
tinggi, (3) konflik jadwal/beban berlebih -- masing-masing diulang
beberapa kali (REPEATS) supaya hasil (rata-rata & standar deviasi) lebih
representatif, bukan hasil dari satu kali coba-coba saja.

Parameter yang direkam mengikuti yang disebutkan di Bab III:
    - nilai fungsi objektif (fitness value) PSO
    - tingkat konvergensi algoritma
    - jumlah konflik jadwal yang berhasil dieliminasi
    - distribusi/utilisasi penggunaan fasilitas

Output:
    experiment_results/scenario_summary.csv   -> tabel ringkasan (mean & std)
    experiment_results/convergence.png        -> kurva konvergensi PSO
    experiment_results/before_after.png       -> grafik metrik sebelum/sesudah
    experiment_results/occupancy_examples.png -> contoh okupansi per slot

Jalankan dengan:
    python run_experiments.py
"""

import random
import statistics
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gym_scheduler import config
from gym_scheduler.data import load_dataset, hourly_weights, generate_busy_day_bookings
from gym_scheduler.scheduler import optimize_schedule

OUT_DIR = Path("experiment_results")
OUT_DIR.mkdir(exist_ok=True)

REPEATS = 30

# Tiga skenario ini mengikuti persis rancangan eksperimen pada Bab III.
SCENARIOS = {
    "Normal (penggunaan merata)": {"n_bookings": 60, "peak_skew": 0.8},
    "Jam sibuk (kepadatan tinggi)": {"n_bookings": 90, "peak_skew": 2.2},
    "Konflik jadwal (beban berlebih)": {"n_bookings": 130, "peak_skew": 2.6},
}


def run_scenario(name: str, params: dict, weights, base_seed: int = 1000):
    """Menjalankan satu skenario sebanyak REPEATS kali dan mengumpulkan
    metrik dari tiap pengulangan."""
    records = []
    representative_history = None

    for i in range(REPEATS):
        seed = base_seed + i
        rng = random.Random(seed)
        booking_hours = generate_busy_day_bookings(
            weights, n_bookings=params["n_bookings"], peak_skew=params["peak_skew"], rng=rng
        )

        t0 = time.perf_counter()
        # riwayat konvergensi hanya direkam pada pengulangan pertama tiap
        # skenario (representatif) -- cukup satu kurva per skenario
        result = optimize_schedule(booking_hours, rng=rng, track_history=(i == 0))
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if i == 0:
            representative_history = result["pso_history"]
            representative_demand = (result["before"]["demand"], result["after"]["demand"])

        b, a = result["before"]["metrics"], result["after"]["metrics"]
        records.append({
            "conflicts_before": b["conflicts"], "conflicts_after": a["conflicts"],
            "utilization_before": b["utilization_pct"], "utilization_after": a["utilization_pct"],
            "empty_before": b["empty_slot_pct"], "empty_after": a["empty_slot_pct"],
            "wait_before": b["avg_wait_minutes"], "wait_after": a["avg_wait_minutes"],
            "time_ms": elapsed_ms,
        })

    return records, representative_history, representative_demand


def summarize(records: list) -> dict:
    keys = records[0].keys()
    summary = {}
    for k in keys:
        values = [r[k] for r in records]
        summary[f"{k}_mean"] = round(statistics.mean(values), 2)
        summary[f"{k}_std"] = round(statistics.pstdev(values), 2)
    return summary


def main():
    df = load_dataset("daily_gym_attendance_workout_data.csv")
    weights = hourly_weights(df)

    all_summaries = {}
    all_histories = {}
    all_demands = {}

    for name, params in SCENARIOS.items():
        print(f"Menjalankan skenario: {name} ({REPEATS}x pengulangan)...")
        records, history, demand_pair = run_scenario(name, params, weights)
        all_summaries[name] = summarize(records)
        all_histories[name] = history
        all_demands[name] = demand_pair

    write_summary_csv(all_summaries)
    plot_before_after(all_summaries)
    plot_convergence(all_histories)
    plot_occupancy_examples(all_demands)
    print(f"\nSelesai. Hasil tersimpan di folder: {OUT_DIR}/")


def write_summary_csv(all_summaries: dict):
    import csv
    path = OUT_DIR / "scenario_summary.csv"
    fieldnames = ["scenario"] + list(next(iter(all_summaries.values())).keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for name, summary in all_summaries.items():
            writer.writerow({"scenario": name, **summary})
    print(f"- Tabel ringkasan  : {path}")


def plot_before_after(all_summaries: dict):
    metrics = [
        ("conflicts", "Konflik Booking", ""),
        ("utilization", "Utilisasi Slot", "%"),
        ("empty", "Slot Kosong", "%"),
        ("wait", "Rata-rata Waktu Tunggu", " menit"),
    ]
    scenarios = list(all_summaries.keys())

    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    x = range(len(scenarios))
    width = 0.35

    for ax, (key, title, unit) in zip(axes, metrics):
        before = [all_summaries[s][f"{key}_before_mean"] for s in scenarios]
        after = [all_summaries[s][f"{key}_after_mean"] for s in scenarios]
        before_err = [all_summaries[s][f"{key}_before_std"] for s in scenarios]
        after_err = [all_summaries[s][f"{key}_after_std"] for s in scenarios]

        ax.bar([i - width / 2 for i in x], before, width, yerr=before_err,
               label="Sebelum", color="#C2664B", capsize=3)
        ax.bar([i + width / 2 for i in x], after, width, yerr=after_err,
               label="Sesudah", color="#0D8C72", capsize=3)
        ax.set_title(f"{title} ({unit.strip() or 'jumlah'})", fontsize=11)
        ax.set_xticks(list(x))
        ax.set_xticklabels([s.split(" (")[0] for s in scenarios], fontsize=9, rotation=10)
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(f"Perbandingan Metrik Sebelum vs Sesudah Optimasi (rata-rata dari {REPEATS} pengulangan, error bar = std. deviasi)",
                 fontsize=11)
    fig.tight_layout()
    path = OUT_DIR / "before_after.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"- Grafik sebelum/sesudah : {path}")


def plot_convergence(all_histories: dict):
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    colors = {"Normal (penggunaan merata)": "#4FB3A0",
              "Jam sibuk (kepadatan tinggi)": "#0D8C72",
              "Konflik jadwal (beban berlebih)": "#B98520"}

    for name, history in all_histories.items():
        if len(history) <= 1:
            continue
        ax.plot(range(1, len(history) + 1), history, label=name.split(" (")[0],
                color=colors.get(name), linewidth=2)

    ax.set_xlabel("Iterasi ke-")
    ax.set_ylabel("Nilai fitness terbaik (gbest)")
    ax.set_title(f"Kurva Konvergensi PSO per Skenario (w={config.W}, c1=c2={config.C1}, "
                 f"partikel={config.SWARM_SIZE})", fontsize=10)
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = OUT_DIR / "convergence.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"- Kurva konvergensi : {path}")


def plot_occupancy_examples(all_demands: dict):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), sharey=True)
    labels = [f"{h}:00" for h in config.OPERATING_HOURS]
    xpos = range(len(labels))

    for ax, (name, (before, after)) in zip(axes, all_demands.items()):
        width = 0.35
        ax.bar([i - width / 2 for i in xpos], before, width, label="Sebelum", color="#C2664B")
        ax.bar([i + width / 2 for i in xpos], after, width, label="Sesudah", color="#0D8C72")
        ax.axhline(config.CAPACITY_PER_SLOT, color="#657267", linestyle="--", linewidth=1.2,
                   label="Kapasitas")
        ax.set_title(name.split(" (")[0], fontsize=10)
        ax.set_xticks(list(xpos))
        ax.set_xticklabels(labels, fontsize=7, rotation=90)
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Contoh Okupansi per Slot Jam (1 pengulangan representatif per skenario)", fontsize=11)
    fig.tight_layout()
    path = OUT_DIR / "occupancy_examples.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"- Contoh okupansi : {path}")


if __name__ == "__main__":
    main()
