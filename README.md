# Dashboard Optimasi Gym

## Struktur folder
```
├── gym_scheduler/        # Logic inti: fuzzy logic + PSO (jangan diubah)
├── data/                 # Dataset & contoh log booking
├── scripts/              # Semua script yang dijalankan manual
├── dashboard/            # Template, output HTML, dan library Chart.js
├── experiment_results/   # Output otomatis dari run_experiments.py / export_*.py
├── gym_capacity_config.json.example   # Salin jadi gym_capacity_config.json kalau mau override kapasitas
├── service_account.json  # Kredensial Google Sheets (JANGAN pernah di-share/upload ke tempat publik)
├── requirements.txt
└── requirements-sheets.txt
```

## Cara jalanin (SELALU dari folder root ini, bukan dari dalam scripts/)

```bash
pip install -r requirements.txt

# 1. Generate data eksperimen (grafik + tabel ringkasan)
python scripts/run_experiments.py

# 2. Export data untuk dashboard (JSON)
python scripts/export_dashboard_data.py
python scripts/export_weekday_weekend_data.py

# 3. Gabungkan jadi 1 file HTML mandiri
python scripts/build_dashboard.py
# -> hasilnya: dashboard/dashboard_optimasi_gym.html (buka langsung di browser)

# Opsional: sinkron dari Google Sheet (alternatif live-update tanpa server)
pip install -r requirements-sheets.txt
python scripts/sync_google_sheet.py

# Opsional: proses log booking asli (bukan data simulasi)
python scripts/run_live_example.py data/sample_booking_log.csv
```

## Catatan
- Folder `api/` (FastAPI real-time) sudah dihapus karena alur booking real
  dipakai lewat Google Sheet (`scripts/sync_google_sheet.py`), yang memang
  dibuat sebagai alternatif `api/` yang tidak butuh server nyala terus.
- `service_account.json` berisi kredensial asli — sudah ada di `.gitignore`,
  pastikan tetap begitu dan jangan ikut ter-zip/share ke luar.
