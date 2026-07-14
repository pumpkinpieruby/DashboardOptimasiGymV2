"""
Fuzzy Logic: klasifikasi tingkat kepadatan slot.

Variabel input : rasio = jumlah booking pada slot / kapasitas slot
Variabel output : derajat keanggotaan pada 3 himpunan fuzzy
                  - Rendah  (kurva bahu kiri)
                  - Sedang  (kurva segitiga)
                  - Tinggi  (kurva bahu kanan)

Ketiga jenis kurva ini adalah yang dibahas pada Bab II skripsi. Nilai
"rasio" bisa > 1 (artinya jumlah booking melebihi kapasitas slot).
"""

from typing import List


def membership_rendah(ratio: float) -> float:
    """Kurva bahu kiri: penuh (1) saat slot jauh dari penuh, turun ke 0."""
    if ratio <= 0.3:
        return 1.0
    if ratio >= 0.7:
        return 0.0
    return (0.7 - ratio) / 0.4


def membership_sedang(ratio: float) -> float:
    """Kurva segitiga, puncak di rasio = 0.6."""
    if ratio <= 0.3 or ratio >= 0.9:
        return 0.0
    if ratio <= 0.6:
        return (ratio - 0.3) / 0.3
    return (0.9 - ratio) / 0.3


def membership_tinggi(ratio: float) -> float:
    """Kurva bahu kanan: 0 saat longgar, naik ke 1 saat penuh/melebihi kapasitas."""
    if ratio <= 0.6:
        return 0.0
    if ratio >= 1.0:
        return 1.0
    return (ratio - 0.6) / 0.4


def classify_slot(demand: int, capacity: int) -> dict:
    """Fuzzifikasi satu slot. Mengembalikan derajat keanggotaan tiap himpunan
    beserta label linguistik dengan derajat keanggotaan tertinggi (untuk
    ditampilkan / dilaporkan, bukan untuk perhitungan fitness)."""
    ratio = demand / capacity
    memberships = {
        "rendah": membership_rendah(ratio),
        "sedang": membership_sedang(ratio),
        "tinggi": membership_tinggi(ratio),
    }

    if memberships["tinggi"] >= memberships["sedang"] and memberships["tinggi"] >= memberships["rendah"]:
        label = "tinggi"
    elif memberships["sedang"] >= memberships["rendah"]:
        label = "sedang"
    else:
        label = "rendah"

    return {"ratio": ratio, "memberships": memberships, "label": label}


def fuzzy_high_penalty(demand: List[int], capacity: int) -> float:
    """Total derajat keanggotaan 'Tinggi' di seluruh slot.

    Dipakai sebagai salah satu komponen fungsi fitness PSO (lihat pso.py):
    slot yang sudah padat ('Tinggi') akan dihindari sebagai tujuan
    pemindahan booking.
    """
    return sum(membership_tinggi(d / capacity) for d in demand)
