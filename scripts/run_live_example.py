"""
Contoh alur pakai DATA BOOKING ASLI (bukan simulasi) untuk menjalankan
optimasi -- pelengkap run_experiments.py (yang tetap dipakai untuk Bab IV
dengan dataset proxy). Skrip ini untuk dipakai belakangan, setelah sistem
booking sungguhan (mis. Google Form/Sheet) sudah menghasilkan log booking.

Tidak ada satupun bagian dari fuzzy_logic.py / pso.py / scheduler.py /
metrics.py yang diubah untuk skrip ini -- hanya SUMBER datanya yang beda
(booking asli, bukan generate_busy_day_bookings()).

Format CSV yang diharapkan minimal 2 kolom (nama kolom bisa disesuaikan,
lihat parameter date_column/hour_column di load_real_bookings):
    tanggal_booking, jam_booking
    2026-07-14, 08:00
    2026-07-14, 17
    ...

Jalankan:
    python run_live_example.py booking_log.csv
    python run_live_example.py booking_log.csv --tanggal 2026-07-14
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # biar gym_scheduler ketemu dari scripts/

from gym_scheduler.data import load_real_bookings, booking_hours_from_log, rolling_hourly_weights
from gym_scheduler.scheduler import optimize_schedule
from gym_scheduler.recommendations import status_per_slot, redistribution_summary, overall_recommendation


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", help="Path ke file CSV log booking asli")
    parser.add_argument("--tanggal", default=None,
                         help="Tanggal yang mau dioptimasi, mis. 2026-07-14. "
                              "Kalau kosong, pakai SEMUA booking di file.")
    parser.add_argument("--window-days", type=int, default=28,
                         help="Panjang rolling window (hari) untuk hitung bobot jam ramai (default: 28)")
    parser.add_argument("--date-column", default="tanggal_booking",
                         help="Nama kolom tanggal di CSV (default: tanggal_booking)")
    parser.add_argument("--hour-column", default="jam_booking",
                         help="Nama kolom jam di CSV (default: jam_booking)")
    parser.add_argument("--out", default=None,
                         help="Kalau diisi, hasil disimpan sebagai JSON ke path ini (mis. untuk dashboard)")
    args = parser.parse_args()

    df = load_real_bookings(args.csv_path, date_column=args.date_column, hour_column=args.hour_column)
    if len(df) == 0:
        print("Tidak ada baris valid di file booking ini -- cek nama kolom "
              "(lihat docstring load_real_bookings) atau isi filenya.")
        return

    # Bobot jam ramai dari rolling window -- dihitung ULANG tiap kali skrip
    # ini dijalankan (bukan sekali lalu dipakai selamanya). Nilainya di sini
    # untuk keperluan laporan/pemantauan tren; optimasi di bawah tetap
    # langsung memakai booking_hours (jumlah booking sungguhan per jam),
    # bukan bobot ini.
    weights = rolling_hourly_weights(df, window_days=args.window_days)
    print(f"Bobot jam ramai ({args.window_days} hari terakhir s.d. "
          f"{df['_date'].max().date()}):")
    for hour, w in zip(range(5, 23), weights):
        print(f"  {hour:02d}:00 -> {w}")

    booking_hours = booking_hours_from_log(df, start_date=args.tanggal, end_date=args.tanggal)
    if not booking_hours:
        print(f"\nTidak ada booking pada periode yang diminta"
              f"{' (' + args.tanggal + ')' if args.tanggal else ''}.")
        return

    print(f"\nMenjalankan optimasi untuk {len(booking_hours)} booking...")
    result = optimize_schedule(booking_hours)
    before, after = result["before"], result["after"]

    print("\n=== Demand per slot ===")
    print("Sebelum :", before["demand"])
    print("Sesudah :", after["demand"])

    print("\n=== Metrik ===")
    print("Sebelum :", before["metrics"])
    print("Sesudah :", after["metrics"])

    redistribution = redistribution_summary(before["demand"], after["demand"])
    print("\n=== Rekomendasi ===")
    print(overall_recommendation(before["metrics"], after["metrics"], redistribution))

    if args.out:
        payload = {
            "tanggal": args.tanggal,
            "rolling_weights": weights,
            "before": before,
            "after": after,
            "redistribution": redistribution,
            "status_per_slot": status_per_slot(before["demand"]),
        }
        out_path = Path(args.out)
        out_path.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nHasil disimpan ke: {out_path}")


if __name__ == "__main__":
    main()
