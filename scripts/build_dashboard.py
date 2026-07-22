"""
Menggabungkan experiment_results/dashboard_data.json ke dalam
dashboard_template.html sehingga menghasilkan 1 file HTML mandiri
(dashboard_optimasi_gym.html) yang bisa langsung dibuka di browser --
tanpa server, tanpa fetch, karena datanya sudah tertanam di dalam file.

Jalankan setelah export_dashboard_data.py:
    python export_dashboard_data.py
    python build_dashboard.py
"""

import json
from pathlib import Path

DATA_JSON = Path("experiment_results") / "dashboard_data.json"
WW_DATA_JSON = Path("experiment_results") / "weekday_weekend_data.json"
TEMPLATE_HTML = Path("dashboard") / "dashboard_template.html"
CHARTJS_LIB = Path("dashboard") / "vendor_chart.umd.min.js"   # library Chart.js (MIT license), ditanam langsung
GYM_SCHEDULER_JS = Path("dashboard") / "gym_scheduler.js"     # port JS dari gym_scheduler/ -- fitur "upload & jalankan"
OUTPUT_HTML = Path("dashboard") / "dashboard_optimasi_gym.html"

with open(DATA_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

with open(WW_DATA_JSON, "r", encoding="utf-8") as f:
    ww_data = json.load(f)

with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
    template = f.read()

with open(CHARTJS_LIB, "r", encoding="utf-8") as f:
    chartjs_code = f.read()

with open(GYM_SCHEDULER_JS, "r", encoding="utf-8") as f:
    gym_scheduler_js_code = f.read()

# Chart.js & gym_scheduler.js DITANAM langsung ke dalam file (bukan <script
# src="...">) supaya dashboard tetap jalan walau dibuka tanpa internet atau
# di jaringan yang memblokir CDN (mis. beberapa jaringan kampus/kantor).
final_html = template.replace("__CHARTJS_LIB__", chartjs_code)
final_html = final_html.replace("__GYM_SCHEDULER_JS__", gym_scheduler_js_code)
final_html = final_html.replace("__DATA_JSON__", json.dumps(data))
final_html = final_html.replace("__WW_DATA_JSON__", json.dumps(ww_data))

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"Dashboard berhasil dibuat: {OUTPUT_HTML}")
