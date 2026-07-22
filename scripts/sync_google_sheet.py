

import argparse
import sys
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # biar gym_scheduler ketemu dari scripts/

from gym_scheduler import config
from gym_scheduler.data import clean_booking_dataframe, booking_hours_from_log, rolling_hourly_weights
from gym_scheduler.scheduler import optimize_schedule
from gym_scheduler.recommendations import status_per_slot, redistribution_summary, overall_recommendation

# --- ISI SESUAI SPREADSHEET ASLI KAMU ---------------------------------------
SPREADSHEET_ID = "1tyTTlTHipoQ2Wm3ZbDzkzGcNqd5kcf3UbNCQTjQJD7E"
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "service_account.json"
BOOKING_SHEET_NAME = "Booking"      # nama tab default hasil Google Form
DATE_COLUMN = "Tanggal Booking"              # sesuaikan nama kolom Form kamu
HOUR_COLUMN = "Jam Booking"                  # sesuaikan nama kolom Form kamu
OUTPUT_SHEET_NAME = "Status Live"            # tab baru buat hasil (dibuat otomatis kalau belum ada)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
# -----------------------------------------------------------------------------


def get_client() -> gspread.Client:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"{CREDENTIALS_PATH.name} tidak ditemukan. Lihat docstring di atas "
            "bagian SETUP -- perlu bikin Service Account dulu di Google Cloud Console."
        )
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
    return gspread.authorize(creds)


def records_to_bookings_df(records: list) -> pd.DataFrame:
    """records = hasil worksheet.get_all_records() (list of dict, 1 dict per
    baris form). Dikonversi ke DataFrame lalu dibersihkan pakai fungsi yang
    SAMA PERSIS dengan yang dipakai jalur CSV (load_real_bookings) --
    lihat clean_booking_dataframe() di gym_scheduler/data.py."""
    df = pd.DataFrame(records)
    return clean_booking_dataframe(df, DATE_COLUMN, HOUR_COLUMN)


# Baris tabel per-jam SELALU mulai persis di baris ke-7 (index 6, 0-based)
# di layout write_status_to_sheet() di bawah -- konstanta ini dipakai lagi
# oleh apply_status_colors() & add_occupancy_chart() supaya rentang warna
# dan sumber data chart selalu tepat walau jumlah baris metadata di atas
# berubah nanti.
HEADER_ROW_INDEX = 5   # 0-based -- baris ["Jam","Jumlah Booking",...]

# Warna disamakan dengan palet dashboard_optimasi_gym.html yang sudah ada,
# supaya identitas visual project konsisten di semua tampilan (HTML lama,
# API baru, dan sheet ini).
STATUS_COLORS = {
    "Kritis":          ("#fbe6e1", "#a8432a"),
    "Perlu Perhatian": ("#fdf0dc", "#b0752b"),
    "Kurang Optimal":  ("#f6f5f2", "#7a756d"),
    "Ideal":           ("#e0f2f0", "#1f6f5c"),
}


def _hex_to_rgb01(hex_color: str) -> dict:
    """'#fbe6e1' -> {'red': .., 'green': .., 'blue': ..} (skala 0-1, format
    yang diminta Sheets API, bukan 0-255)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return {"red": r, "green": g, "blue": b}


def apply_status_colors(ws: gspread.Worksheet, status_rows: list):
    """Warnai tiap baris tabel (kolom A-E) sesuai kategori status-nya
    (Kritis=merah muda, Perlu Perhatian=kuning, Ideal=hijau, dst) -- biar
    pengunjung bisa langsung lihat sekilas tanpa baca teks."""
    formats = []
    for i, row in enumerate(status_rows):
        bg_hex, text_hex = STATUS_COLORS.get(row["status"], ("#ffffff", "#242321"))
        row_number = HEADER_ROW_INDEX + 2 + i  # +2: 1-based A1 notation + lewati baris header
        formats.append({
            "range": f"A{row_number}:E{row_number}",
            "format": {
                "backgroundColor": _hex_to_rgb01(bg_hex),
                "textFormat": {"foregroundColor": _hex_to_rgb01(text_hex)},
            },
        })
    ws.batch_format(formats)


def _delete_existing_charts(sh: gspread.Spreadsheet, sheet_id: int):
    """Hapus chart lama di tab ini sebelum bikin yang baru -- supaya chart
    TIDAK numpuk tiap kali script dijalankan ulang (mis. tiap 15 menit
    lewat cron)."""
    meta = sh.fetch_sheet_metadata()
    requests = []
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        for chart in sheet.get("charts", []):
            requests.append({"deleteEmbeddedObject": {"objectId": chart["chartId"]}})
    if requests:
        sh.batch_update({"requests": requests})


def add_occupancy_chart(sh: gspread.Spreadsheet, ws: gspread.Worksheet, n_rows: int):
    """Tambahkan grafik batang okupansi per jam (kolom = jumlah booking,
    garis = kapasitas) sebagai chart ASLI Google Sheets -- bukan gambar
    statis, jadi tetap bisa di-zoom/hover di browser pengunjung.

    Chart ditaruh DI BAWAH tabel (bukan di sampingnya) -- supaya tidak
    pernah menutupi metadata (baris 1-4) atau tabel status per-jam,
    berapa pun lebar kolom A-E saat itu di sheet tujuan."""
    sheet_id = ws.id
    data_start = HEADER_ROW_INDEX          # baris header (dipakai sebagai label kolom chart)
    data_end = HEADER_ROW_INDEX + 1 + n_rows  # exclusive, sampai baris data terakhir
    # Baris terakhir yang ditulis write_status_to_sheet() itu "Rekomendasi",
    # ada di data_end + 1 (0-based) -- lihat urutan `rows` di sana. Anchor
    # chart 2 baris di bawah itu (data_end + 3) supaya ada jarak kosong,
    # dan kolom A (0) supaya rata kiri, bukan menggantung di tengah.
    chart_anchor_row = data_end + 3

    def _range(col_start, col_end):
        return {
            "sources": [{
                "sheetId": sheet_id,
                "startRowIndex": data_start,
                "endRowIndex": data_end,
                "startColumnIndex": col_start,
                "endColumnIndex": col_end,
            }]
        }

    chart_request = {
        "requests": [{
            "addChart": {
                "chart": {
                    "spec": {
                        "title": "Okupansi per Jam (booking vs kapasitas)",
                        "basicChart": {
                            "chartType": "COMBO",
                            "legendPosition": "BOTTOM_LEGEND",
                            "axis": [
                                {"position": "BOTTOM_AXIS", "title": "Jam"},
                                {"position": "LEFT_AXIS", "title": "Jumlah Orang"},
                            ],
                            "domains": [{"domain": {"sourceRange": _range(0, 1)}}],  # kolom Jam
                            "series": [
                                {"series": {"sourceRange": _range(1, 2)}, "type": "COLUMN"},  # Jumlah Booking
                                {"series": {"sourceRange": _range(2, 3)}, "type": "LINE"},    # Kapasitas
                            ],
                            "headerCount": 1,
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {"sheetId": sheet_id, "rowIndex": chart_anchor_row, "columnIndex": 0},
                            "widthPixels": 640,
                            "heightPixels": 340,
                        }
                    },
                }
            }
        }]
    }

    _delete_existing_charts(sh, sheet_id)
    sh.batch_update(chart_request)


def write_status_to_sheet(sh: gspread.Spreadsheet, tanggal: str, status_rows: list, rekomendasi: str,
                           jumlah_booking: int) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(OUTPUT_SHEET_NAME)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=OUTPUT_SHEET_NAME, rows=40, cols=8)

    rows = [
        ["Status Jadwal Gym -- diperbarui otomatis"],
        ["Terakhir diperbarui", str(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"))],
        ["Tanggal", tanggal],
        ["Jumlah booking", jumlah_booking],
        [],
        ["Jam", "Jumlah Booking", "Kapasitas", "Status", "Saran"],
    ]
    for r in status_rows:
        rows.append([f"{r['hour']:02d}:00", r["demand"], config.CAPACITY_PER_SLOT, r["status"], r["saran"]])
    rows.append([])
    rows.append(["Rekomendasi", rekomendasi])

    ws.update(values=rows, range_name="A1")

    try:
        apply_status_colors(ws, status_rows)
    except Exception as e:
        print(f"[peringatan] Gagal mewarnai baris status ({e}) -- data teks tetap tersimpan normal.")

    try:
        add_occupancy_chart(sh, ws, n_rows=len(status_rows))
    except Exception as e:
        print(f"[peringatan] Gagal membuat chart ({e}) -- data teks & warna tetap tersimpan normal.")

    return ws


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tanggal", default=None, help="Tanggal yang mau dioptimasi (default: hari ini)")
    args = parser.parse_args()
    tanggal = args.tanggal or str(pd.Timestamp.now().date())

    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws_booking = sh.worksheet(BOOKING_SHEET_NAME)

    df = records_to_bookings_df(ws_booking.get_all_records())
    if len(df) == 0:
        print("Tidak ada baris booking valid di sheet. Cek DATE_COLUMN/HOUR_COLUMN "
              "sudah sesuai nama kolom Form kamu.")
        return

    booking_hours = booking_hours_from_log(df, start_date=tanggal, end_date=tanggal)
    if not booking_hours:
        print(f"Tidak ada booking untuk tanggal {tanggal}.")
        return

    result = optimize_schedule(booking_hours)
    before, after = result["before"], result["after"]
    redistribution = redistribution_summary(before["demand"], after["demand"])
    rekomendasi = overall_recommendation(before["metrics"], after["metrics"], redistribution)
    status_rows = status_per_slot(before["demand"])

    write_status_to_sheet(sh, tanggal, status_rows, rekomendasi, len(booking_hours))
    print(f"Selesai. Tab '{OUTPUT_SHEET_NAME}' sudah diperbarui untuk tanggal {tanggal} "
          f"({len(booking_hours)} booking, {before['metrics']['conflicts']} -> "
          f"{after['metrics']['conflicts']} konflik).")


if __name__ == "__main__":
    main()