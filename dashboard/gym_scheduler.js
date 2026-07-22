/* ============================================================================
   gym_scheduler.js
   ----------------------------------------------------------------------------
   Port JavaScript dari package Python gym_scheduler/ (fuzzy_logic.py, pso.py,
   scheduler.py, metrics.py, recommendations.py, dan sebagian data.py).

   TUJUAN: supaya dashboard bisa punya fitur "upload file -> jalankan optimasi
   beneran di browser", TANPA nambah server/API/database -- tetap 1 file HTML
   mandiri seperti sebelumnya (lihat scripts/build_dashboard.py).

   PENTING -- SUMBER KEBENARAN tetap package Python di gym_scheduler/. File
   ini HARUS selalu logic-nya SAMA PERSIS dengan versi Python (rumus, urutan
   langkah, angka parameter). Kalau ada perubahan di gym_scheduler/*.py,
   file ini juga harus diupdate manual (tidak ada auto-sync).

   Semua angka default di sini disalin dari gym_scheduler/config.py.
   ============================================================================ */

const GymScheduler = (() => {
  "use strict";

  /* ==========================================================================
     CONFIG -- sama persis dengan gym_scheduler/config.py
     ========================================================================== */
  const config = {
    OPERATING_HOURS: Array.from({ length: 18 }, (_, i) => i + 5), // 05:00 s.d. 22:00
    N_SLOTS: 18,
    CAPACITY_PER_SLOT: 5,
    TURNOVER_MINUTES: 20,
    EMPTY_THRESHOLD_RATIO: 0.4,
    BUSY_DAY_BOOKINGS: 80,
    PEAK_SKEW: 1.8,
    SWARM_SIZE: 25,
    ITERATIONS: 60,
    W: 0.7,
    C1: 2.0,
    C2: 2.0,
    WEIGHT_CONFLICT: 100,
    WEIGHT_VARIANCE: 5,
    WEIGHT_FUZZY: 3,
  };

  /* ==========================================================================
     FUZZY LOGIC -- sama persis dengan gym_scheduler/fuzzy_logic.py
     ========================================================================== */

  // Kurva bahu kiri: penuh (1) saat slot jauh dari penuh, turun ke 0.
  function membershipRendah(ratio) {
    if (ratio <= 0.3) return 1.0;
    if (ratio >= 0.7) return 0.0;
    return (0.7 - ratio) / 0.4;
  }

  // Kurva segitiga, puncak di rasio = 0.6.
  function membershipSedang(ratio) {
    if (ratio <= 0.3 || ratio >= 0.9) return 0.0;
    if (ratio <= 0.6) return (ratio - 0.3) / 0.3;
    return (0.9 - ratio) / 0.3;
  }

  // Kurva bahu kanan: 0 saat longgar, naik ke 1 saat penuh/melebihi kapasitas.
  function membershipTinggi(ratio) {
    if (ratio <= 0.6) return 0.0;
    if (ratio >= 1.0) return 1.0;
    return (ratio - 0.6) / 0.4;
  }

  // Fuzzifikasi satu slot -> derajat keanggotaan + label linguistik.
  function classifySlot(demand, capacity) {
    const ratio = demand / capacity;
    const memberships = {
      rendah: membershipRendah(ratio),
      sedang: membershipSedang(ratio),
      tinggi: membershipTinggi(ratio),
    };
    let label;
    if (memberships.tinggi >= memberships.sedang && memberships.tinggi >= memberships.rendah) {
      label = "tinggi";
    } else if (memberships.sedang >= memberships.rendah) {
      label = "sedang";
    } else {
      label = "rendah";
    }
    return { ratio, memberships, label };
  }

  // Total derajat keanggotaan "Tinggi" di seluruh slot -- komponen fitness PSO.
  function fuzzyHighPenalty(demand, capacity) {
    let total = 0;
    for (const d of demand) total += membershipTinggi(d / capacity);
    return total;
  }

  /* ==========================================================================
     PSO -- sama persis dengan gym_scheduler/pso.py
     ========================================================================== */

  function fitness(slotIndices, baseDemand) {
    const demand = baseDemand.slice(); // copy, base_demand tidak boleh ikut berubah
    for (const s of slotIndices) demand[s] += 1;

    // Komponen 1: total kelebihan kapasitas di seluruh slot.
    let overCapacity = 0;
    for (const d of demand) overCapacity += Math.max(d - config.CAPACITY_PER_SLOT, 0);

    // Komponen 2: variansi sebaran demand antar slot.
    const mean = demand.reduce((a, b) => a + b, 0) / demand.length;
    let variance = 0;
    for (const d of demand) variance += (d - mean) ** 2;
    variance /= demand.length;

    // Komponen 3: penalti fuzzy (hindari slot yang sudah "Tinggi").
    const fuzzyPenalty = fuzzyHighPenalty(demand, config.CAPACITY_PER_SLOT);

    return (
      overCapacity * config.WEIGHT_CONFLICT +
      variance * config.WEIGHT_VARIANCE +
      fuzzyPenalty * config.WEIGHT_FUZZY
    );
  }

  // 1 "tebakan solusi" yang bergerak mencari solusi terbaik (meniru kawanan burung).
  class Particle {
    constructor(nVars, nSlots) {
      this.position = Array.from({ length: nVars }, () => Math.random() * (nSlots - 1));
      this.velocity = Array.from(
        { length: nVars },
        () => (Math.random() * 2 - 1) * (nSlots / 2)
      );
      this.pbest = this.position.slice();
      this.pbestFitness = Infinity;
    }
  }

  // Ubah posisi (angka desimal) jadi index slot valid (bilangan bulat, 0..nSlots-1).
  function roundedSlots(position, nSlots) {
    return position.map((x) => Math.min(nSlots - 1, Math.max(0, Math.round(x))));
  }

  function runPso(movableCount, baseDemand, trackHistory) {
    const nSlots = config.N_SLOTS;

    // Kalau tidak ada booking yang perlu dipindah, tidak perlu jalankan PSO.
    if (movableCount === 0) return { targetSlots: [], history: [0.0] };

    const particles = Array.from({ length: config.SWARM_SIZE }, () => new Particle(movableCount, nSlots));

    let gbest = null;
    let gbestFitness = Infinity;
    const history = [];

    for (let iter = 0; iter < config.ITERATIONS; iter++) {
      // --- TAHAP 1: EVALUASI ---
      for (const p of particles) {
        const slots = roundedSlots(p.position, nSlots);
        const f = fitness(slots, baseDemand);

        if (f < p.pbestFitness) {
          p.pbestFitness = f;
          p.pbest = p.position.slice();
        }
        if (f < gbestFitness) {
          gbestFitness = f;
          gbest = p.position.slice();
        }
      }
      if (trackHistory) history.push(gbestFitness);

      // --- TAHAP 2: PERGERAKAN ---
      for (const p of particles) {
        for (let i = 0; i < movableCount; i++) {
          const r1 = Math.random();
          const r2 = Math.random();

          p.velocity[i] =
            config.W * p.velocity[i] +
            config.C1 * r1 * (p.pbest[i] - p.position[i]) +
            config.C2 * r2 * (gbest[i] - p.position[i]);

          p.velocity[i] = Math.max(-nSlots / 2, Math.min(nSlots / 2, p.velocity[i]));
          p.position[i] += p.velocity[i];
          p.position[i] = Math.max(0, Math.min(nSlots - 1, p.position[i]));
        }
      }
    }

    return { targetSlots: roundedSlots(gbest, nSlots), history };
  }

  /* ==========================================================================
     METRICS -- sama persis dengan gym_scheduler/metrics.py
     ========================================================================== */

  function evaluateMetrics(demand) {
    const totalCapacity = config.CAPACITY_PER_SLOT * demand.length;

    let used = 0;
    for (const d of demand) used += Math.min(d, config.CAPACITY_PER_SLOT);
    const utilizationPct = (used / totalCapacity) * 100;

    const emptyThreshold = config.EMPTY_THRESHOLD_RATIO * config.CAPACITY_PER_SLOT;
    let jumlahSlotKosong = 0;
    for (const d of demand) if (d < emptyThreshold) jumlahSlotKosong++;
    const emptySlotPct = (jumlahSlotKosong / demand.length) * 100;

    let conflicts = 0;
    for (const d of demand) conflicts += Math.max(d - config.CAPACITY_PER_SLOT, 0);

    // Simulasi waktu tunggu (antrean bergelombang, lihat metrics.py untuk penjelasan).
    const waits = [];
    for (const d of demand) {
      if (d > config.CAPACITY_PER_SLOT) {
        const excess = d - config.CAPACITY_PER_SLOT;
        for (let k = 1; k <= excess; k++) {
          const gelombangKe = Math.ceil(k / config.CAPACITY_PER_SLOT);
          waits.push(gelombangKe * config.TURNOVER_MINUTES);
        }
      }
    }
    const avgWaitMinutes = waits.length ? waits.reduce((a, b) => a + b, 0) / waits.length : 0.0;

    return {
      utilization_pct: Math.round(utilizationPct * 10) / 10,
      empty_slot_pct: Math.round(emptySlotPct * 10) / 10,
      conflicts: conflicts,
      avg_wait_minutes: Math.round(avgWaitMinutes * 10) / 10,
    };
  }

  /* ==========================================================================
     SCHEDULER -- sama persis dengan gym_scheduler/scheduler.py
     ========================================================================== */

  function demandBySlot(bookingHours) {
    const demand = new Array(config.N_SLOTS).fill(0);
    for (const h of bookingHours) {
      demand[config.OPERATING_HOURS.indexOf(h)] += 1;
    }
    return demand;
  }

  function splitMovable(bookingHours) {
    const bySlot = {};
    for (const h of bookingHours) {
      if (!(h in bySlot)) bySlot[h] = [];
      bySlot[h].push(h);
    }
    const fixed = [];
    let movableCount = 0;
    for (const key in bySlot) {
      const group = bySlot[key];
      fixed.push(...group.slice(0, config.CAPACITY_PER_SLOT));
      movableCount += Math.max(0, group.length - config.CAPACITY_PER_SLOT);
    }
    return { fixed, movableCount };
  }

  function repairHardConstraint(demand) {
    const d = demand.slice();
    for (let iter = 0; iter < 2000; iter++) {
      let overIdx = null;
      for (let i = 0; i < d.length; i++) {
        if (d[i] > config.CAPACITY_PER_SLOT) {
          overIdx = i;
          break;
        }
      }
      if (overIdx === null) break;

      let underIdx = 0;
      for (let i = 1; i < d.length; i++) if (d[i] < d[underIdx]) underIdx = i;

      if (d[underIdx] >= config.CAPACITY_PER_SLOT) break;

      d[overIdx] -= 1;
      d[underIdx] += 1;
    }
    return d;
  }

  function optimizeSchedule(bookingHours, trackHistory = false) {
    // --- Langkah 1: kondisi SEBELUM optimasi ---
    const beforeDemand = demandBySlot(bookingHours);
    const beforeMetrics = evaluateMetrics(beforeDemand);

    // --- Langkah 2: pisahkan booking yang perlu dipindah ---
    const { fixed, movableCount } = splitMovable(bookingHours);
    const baseDemand = demandBySlot(fixed);

    // --- Langkah 3: Fuzzy Logic + PSO ---
    const { targetSlots, history } = runPso(movableCount, baseDemand, trackHistory);

    // --- Langkah 4: terapkan hasil PSO, lalu perbaiki (hard constraint) ---
    let afterDemand = baseDemand.slice();
    for (const s of targetSlots) afterDemand[s] += 1;
    afterDemand = repairHardConstraint(afterDemand);

    // --- Langkah 5: kondisi SESUDAH optimasi ---
    const afterMetrics = evaluateMetrics(afterDemand);

    // --- Langkah 6: klasifikasi fuzzy per slot ---
    const fuzzyBefore = beforeDemand.map((d) => classifySlot(d, config.CAPACITY_PER_SLOT));
    const fuzzyAfter = afterDemand.map((d) => classifySlot(d, config.CAPACITY_PER_SLOT));

    return {
      operating_hours: config.OPERATING_HOURS,
      before: { demand: beforeDemand, metrics: beforeMetrics, fuzzy: fuzzyBefore },
      after: { demand: afterDemand, metrics: afterMetrics, fuzzy: fuzzyAfter },
      pso_history: history,
    };
  }

  /* ==========================================================================
     RECOMMENDATIONS -- sama persis dengan gym_scheduler/recommendations.py
     ========================================================================== */

  const CRITICAL_RATIO = 1.0;
  const WATCH_RATIO = 0.7;
  const LOW_RATIO = 0.3;

  function slotStatus(ratio) {
    if (ratio > CRITICAL_RATIO) {
      return {
        status: "Kritis",
        severity: 3,
        saran:
          "Melebihi kapasitas -- pertimbangkan menambah kapasitas/alat pada jam ini, " +
          "menambah staf, atau mengarahkan sebagian anggota ke jam alternatif yang lebih longgar.",
      };
    }
    if (ratio > WATCH_RATIO) {
      return {
        status: "Perlu Perhatian",
        severity: 2,
        saran:
          "Mendekati kapasitas -- pantau tren booking pada jam ini; berpotensi jadi " +
          "konflik jika jumlah anggota terus bertambah.",
      };
    }
    if (ratio < LOW_RATIO) {
      return {
        status: "Kurang Optimal",
        severity: 1,
        saran:
          "Okupansi rendah -- berpotensi untuk promosi (diskon jam tertentu, kelas komunitas, " +
          "sesi khusus) atau dijadwalkan untuk maintenance alat.",
      };
    }
    return { status: "Ideal", severity: 0, saran: "Okupansi seimbang, tidak perlu tindakan khusus." };
  }

  function statusPerSlot(demandBefore) {
    const result = [];
    config.OPERATING_HOURS.forEach((hour, i) => {
      const demand = demandBefore[i];
      const fuzzy = classifySlot(demand, config.CAPACITY_PER_SLOT);
      const status = slotStatus(fuzzy.ratio);
      result.push({
        hour,
        demand,
        ratio: Math.round(fuzzy.ratio * 100) / 100,
        fuzzy_label: fuzzy.label,
        status: status.status,
        severity: status.severity,
        saran: status.saran,
      });
    });
    return result;
  }

  function redistributionSummary(demandBefore, demandAfter) {
    const reduceHours = [];
    const addHours = [];
    config.OPERATING_HOURS.forEach((hour, i) => {
      const delta = demandAfter[i] - demandBefore[i];
      if (delta < 0) reduceHours.push({ hour, delta });
      else if (delta > 0) addHours.push({ hour, delta });
    });
    reduceHours.sort((a, b) => a.delta - b.delta);
    addHours.sort((a, b) => b.delta - a.delta);
    const totalMoved = reduceHours.reduce((acc, r) => acc - r.delta, 0);
    return { total_booking_dipindah: totalMoved, jam_dikurangi: reduceHours, jam_ditambah: addHours };
  }

  function overallRecommendation(beforeMetrics, afterMetrics, redistribution) {
    const moved = redistribution.total_booking_dipindah;
    const conflictDrop = Math.round((beforeMetrics.conflicts - afterMetrics.conflicts) * 100) / 100;
    const utilGain = Math.round((afterMetrics.utilization_pct - beforeMetrics.utilization_pct) * 100) / 100;

    const parts = [];

    if (moved > 0) {
      const jamDikurangi = redistribution.jam_dikurangi
        .slice(0, 3)
        .map((h) => `${String(h.hour).padStart(2, "0")}:00`)
        .join(", ");
      const jamDitambah = redistribution.jam_ditambah
        .slice(0, 3)
        .map((h) => `${String(h.hour).padStart(2, "0")}:00`)
        .join(", ");
      parts.push(
        `Sistem merekomendasikan pemindahan ${moved} booking dari jam padat ` +
          `(${jamDikurangi}) ke jam yang lebih longgar (${jamDitambah}).`
      );
    }

    if (conflictDrop > 0) {
      parts.push(`Langkah ini mengeliminasi ${conflictDrop} konflik penjadwalan.`);
    } else if (conflictDrop === 0 && beforeMetrics.conflicts > 0) {
      parts.push(
        `Namun ${afterMetrics.conflicts} konflik masih tersisa karena permintaan ` +
          `melebihi total kapasitas fasilitas sepanjang hari -- solusi jangka panjang perlu ` +
          `menambah kapasitas atau jam operasional, bukan hanya redistribusi jadwal.`
      );
    }

    if (utilGain > 0) {
      parts.push(`Utilisasi fasilitas meningkat ${utilGain.toFixed(1)} poin persentase.`);
    }

    return parts.length ? parts.join(" ") : "Distribusi booking sudah cukup merata, tidak ada pemindahan yang disarankan.";
  }

  function buildRecommendations(before, after) {
    const redistribution = redistributionSummary(before.demand, after.demand);
    return {
      status_per_slot: statusPerSlot(before.demand),
      redistribution,
      summary_text: overallRecommendation(before.metrics, after.metrics, redistribution),
    };
  }

  /* ==========================================================================
     CSV PARSING -- parser ringan (tanpa library luar), cukup untuk kebutuhan
     upload di dashboard. Menangani tanda kutip ganda & koma di dalam kolom.
     ========================================================================== */

  function parseCSV(text) {
    // Buang BOM kalau ada, & normalisasi newline.
    const clean = text.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const lines = clean.split("\n").filter((l) => l.length > 0);
    if (lines.length === 0) return { header: [], rows: [] };

    function parseLine(line) {
      const cells = [];
      let cur = "";
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (inQuotes) {
          if (c === '"' && line[i + 1] === '"') {
            cur += '"';
            i++;
          } else if (c === '"') {
            inQuotes = false;
          } else {
            cur += c;
          }
        } else if (c === '"') {
          inQuotes = true;
        } else if (c === ",") {
          cells.push(cur);
          cur = "";
        } else {
          cur += c;
        }
      }
      cells.push(cur);
      return cells.map((c) => c.trim());
    }

    const header = parseLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const cells = parseLine(lines[i]);
      const row = {};
      header.forEach((h, idx) => (row[h] = cells[idx] !== undefined ? cells[idx] : ""));
      rows.push(row);
    }
    return { header, rows };
  }

  /* ==========================================================================
     JALUR 1: LOG BOOKING ASLI -- sama seperti gym_scheduler/data.py bagian
     "DATA BOOKING ASLI" (clean_booking_dataframe, load_real_bookings,
     booking_hours_from_log) & scripts/run_live_example.py.
     ========================================================================== */

  // Sama seperti data._parse_hour() di Python.
  function parseHour(value) {
    if (value === null || value === undefined) return null;
    const s = String(value).trim().replace(/\./g, ":");
    if (s === "") return null;
    try {
      if (s.includes(":")) {
        const h = parseInt(s.split(":")[0], 10);
        return Number.isNaN(h) ? null : h;
      }
      const h = parseInt(parseFloat(s), 10);
      return Number.isNaN(h) ? null : h;
    } catch (e) {
      return null;
    }
  }

  // Parsing tanggal yang cukup toleran untuk format umum (YYYY-MM-DD,
  // DD/MM/YYYY, DD-MM-YYYY) -- mirip perilaku pd.to_datetime(errors="coerce").
  function parseDateLoose(value) {
    if (!value) return null;
    const s = String(value).trim();
    // Format ISO (YYYY-MM-DD) -- dicoba dulu, paling gak ambigu.
    let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) {
      const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
      return Number.isNaN(d.getTime()) ? null : d;
    }
    // Format DD/MM/YYYY atau DD-MM-YYYY.
    m = s.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})/);
    if (m) {
      const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
      return Number.isNaN(d.getTime()) ? null : d;
    }
    // Fallback: biar browser yang coba tebak.
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // Sama seperti data.clean_booking_dataframe() + load_real_bookings().
  function loadRealBookings(rows, dateColumn, hourColumn) {
    if (rows.length === 0) {
      throw new Error("File CSV kosong (tidak ada baris data).");
    }
    const availableColumns = Object.keys(rows[0]);
    if (!availableColumns.includes(dateColumn) || !availableColumns.includes(hourColumn)) {
      throw new Error(
        `Kolom '${dateColumn}' dan/atau '${hourColumn}' tidak ditemukan. ` +
          `Kolom yang tersedia: ${availableColumns.join(", ")}. Sesuaikan nama kolom tanggal/jam.`
      );
    }

    let nDropped = 0;
    const cleaned = [];
    for (const row of rows) {
      const date = parseDateLoose(row[dateColumn]);
      const hour = parseHour(row[hourColumn]);
      const valid = date !== null && hour !== null && config.OPERATING_HOURS.includes(hour);
      if (!valid) {
        nDropped++;
        continue;
      }
      cleaned.push({ date, hour });
    }
    return { cleaned, nDropped };
  }

  // Sama seperti data.booking_hours_from_log().
  function bookingHoursFromLog(cleaned, startDate, endDate) {
    let rows = cleaned;
    if (startDate) {
      const start = parseDateLoose(startDate);
      rows = rows.filter((r) => r.date >= start);
    }
    if (endDate) {
      const end = parseDateLoose(endDate);
      rows = rows.filter((r) => r.date <= end);
    }
    return rows.map((r) => r.hour);
  }

  /* ==========================================================================
     JALUR 2: DATASET KUNJUNGAN MENTAH -- sama seperti data.load_dataset(),
     data.hourly_weights(), data.generate_busy_day_bookings().
     ========================================================================== */

  function loadDataset(rows) {
    const requiredColumns = ["check_in_time", "attendance_status"];
    if (rows.length === 0) throw new Error("File CSV kosong (tidak ada baris data).");
    const availableColumns = Object.keys(rows[0]);
    for (const col of requiredColumns) {
      if (!availableColumns.includes(col)) {
        throw new Error(
          `Kolom '${col}' tidak ditemukan di file ini. Kolom yang tersedia: ${availableColumns.join(", ")}. ` +
            `File ini harus berformat sama seperti daily_gym_attendance_workout_data.csv.`
        );
      }
    }
    return rows.map((row) => ({
      ...row,
      hour: parseInt(String(row.check_in_time).split(":")[0], 10),
    }));
  }

  // Sama seperti data.hourly_weights(): bobot per jam dari kunjungan "Present" asli.
  function hourlyWeights(dataset) {
    const counts = {};
    for (const row of dataset) {
      if (row.attendance_status === "Present") {
        counts[row.hour] = (counts[row.hour] || 0) + 1;
      }
    }
    return config.OPERATING_HOURS.map((h) => counts[h] || 1); // jam tanpa data diberi bobot minimal 1
  }

  // Sama seperti random.choices(population, weights, k) di Python: sampling
  // acak berbobot dengan pengembalian (with replacement).
  function weightedChoices(population, weights, k) {
    const cumulative = [];
    let total = 0;
    for (const w of weights) {
      total += w;
      cumulative.push(total);
    }
    const result = [];
    for (let i = 0; i < k; i++) {
      const r = Math.random() * total;
      let idx = 0;
      while (idx < cumulative.length - 1 && r > cumulative[idx]) idx++;
      result.push(population[idx]);
    }
    return result;
  }

  // Sama seperti data.generate_busy_day_bookings().
  function generateBusyDayBookings(weights, nBookings, peakSkew) {
    nBookings = nBookings || config.BUSY_DAY_BOOKINGS;
    peakSkew = peakSkew === undefined ? config.PEAK_SKEW : peakSkew;
    const skewed = weights.map((w) => Math.pow(w, peakSkew));
    return weightedChoices(config.OPERATING_HOURS, skewed, nBookings);
  }

  /* ==========================================================================
     EXPORT
     ========================================================================== */

  return {
    config,
    classifySlot,
    optimizeSchedule,
    buildRecommendations,
    parseCSV,
    loadRealBookings,
    bookingHoursFromLog,
    loadDataset,
    hourlyWeights,
    generateBusyDayBookings,
  };
})();
