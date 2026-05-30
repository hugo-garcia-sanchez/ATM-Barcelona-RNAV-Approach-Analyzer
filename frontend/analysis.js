/**
 * Analysis tab — separations, turns, NADP, thresholds.
 * Pulls from the MVP endpoints, renders Chart.js views and tables.
 */

(function () {
  const charts = {};

  function $(id) { return document.getElementById(id); }

  function setAnaStatus(msg, busy = false) {
    const el = $("anaStatus");
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle("busy", busy);
  }

  function ensureToastArea() {
    let area = document.getElementById("toastArea");
    if (!area) {
      area = document.createElement("div");
      area.id = "toastArea";
      area.className = "toast-area";
      document.body.appendChild(area);
    }
    return area;
  }

  function showToast(message, variant = "info", timeoutMs = 3500) {
    const area = ensureToastArea();
    const toast = document.createElement("div");
    toast.className = `toast ${variant}`;
    toast.textContent = message;
    area.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    window.setTimeout(() => {
      toast.classList.remove("show");
      window.setTimeout(() => toast.remove(), 200);
    }, timeoutMs);
  }

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes)) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
  }

  function getFilenameFromDisposition(headerValue) {
    if (!headerValue) return null;
    const match = /filename="?([^";]+)"?/i.exec(headerValue);
    return match ? match[1] : null;
  }

  function safeFilenameFromKey(key) {
    return `${String(key).toLowerCase().replace(/[^a-z0-9._-]+/g, "-")}.csv`;
  }

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function hasDesktopCsvSaver() {
    return !!(window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_csv === "function");
  }

  async function saveWithDesktopApi(filename, blob) {
    const text = await blob.text();
    return await window.pywebview.api.save_csv(filename, text);
  }

  async function openSavePicker(filename) {
    return await window.showSaveFilePicker({
      suggestedName: filename,
      types: [{
        description: "CSV",
        accept: { "text/csv": [".csv"] },
      }],
    });
  }

  async function writeToHandle(handle, blob) {
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
  }

  async function handleCsvDownload(link, label, key) {
    const url = link.getAttribute("href");
    if (!url || url === "#") {
      showToast("CSV no disponible. Ejecuta el analisis primero.", "warning");
      return;
    }

    setAnaStatus(`Descargando ${label}...`, true);
    try {
      const suggestedName = safeFilenameFromKey(key);

      const response = await fetch(url);
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const err = await response.json();
          detail = err.detail || detail;
        } catch (_) {
          try {
            const text = await response.text();
            if (text) detail = text;
          } catch (_) {}
        }
        throw new Error(detail);
      }

      const blob = await response.blob();
      const sizeText = formatBytes(blob.size);
      const outputFile = response.headers.get("X-Output-File");
      const responseFilename =
        getFilenameFromDisposition(response.headers.get("content-disposition")) ||
        outputFile ||
        suggestedName;

      let savedName = responseFilename;
      if (hasDesktopCsvSaver()) {
        const result = await saveWithDesktopApi(responseFilename, blob);
        if (result && result.status === "cancelled") {
          showToast("Guardado cancelado.", "warning");
          setAnaStatus("Guardado cancelado.", false);
          return;
        }
        if (result && result.status === "error") {
          throw new Error(result.message || "No se pudo guardar el CSV");
        }
        savedName = (result && result.path) ? result.path : responseFilename;
      } else if (window.showSaveFilePicker) {
        try {
          const pickerHandle = await openSavePicker(responseFilename);
          await writeToHandle(pickerHandle, blob);
          savedName = pickerHandle.name || responseFilename;
        } catch (pickerErr) {
          if (pickerErr && pickerErr.name === "AbortError") {
            showToast("Guardado cancelado.", "warning");
            setAnaStatus("Guardado cancelado.", false);
            return;
          }
          throw pickerErr;
        }
      } else {
        triggerDownload(blob, responseFilename);
      }

      let toastMsg = `CSV listo (${sizeText}) · archivo: ${savedName}`;
      if (outputFile) toastMsg += ` · servidor: ${outputFile}`;
      showToast(toastMsg, "success");
      setAnaStatus("CSV descargado.", false);
    } catch (err) {
      console.error(err);
      showToast(`Error: ${err.message}`, "error", 5000);
      setAnaStatus(`Error CSV: ${err.message}`, false);
    }
  }

  function wireCsvDownloads() {
    const links = [
      { id: "csvCombined", label: "combined", key: "combined-results" },
      { id: "csvSeparations", label: "separations", key: "separations" },
      { id: "csvTurns", label: "turns", key: "turns" },
      { id: "csvNadp", label: "nadp", key: "nadp" },
      { id: "csvThresholds", label: "thresholds", key: "thresholds" },
    ];

    links.forEach(({ id, label, key }) => {
      const link = $(id);
      if (!link) return;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        handleCsvDownload(link, label, key);
      });
    });
  }

  function destroyChart(key) {
    if (charts[key]) {
      charts[key].destroy();
      delete charts[key];
    }
  }

  function makeChart(canvasId, config) {
    const ctx = $(canvasId);
    if (!ctx) return;
    destroyChart(canvasId);
    charts[canvasId] = new Chart(ctx, config);
  }

  function histogramBins(values, binCount = 20) {
    const v = values.filter((x) => Number.isFinite(x));
    if (v.length === 0) return { labels: [], counts: [] };
    const min = Math.min(...v);
    const max = Math.max(...v);
    if (min === max) return { labels: [min.toFixed(2)], counts: [v.length] };
    const w = (max - min) / binCount;
    const counts = new Array(binCount).fill(0);
    v.forEach((x) => {
      let i = Math.floor((x - min) / w);
      if (i >= binCount) i = binCount - 1;
      counts[i] += 1;
    });
    const labels = counts.map((_, i) => (min + i * w).toFixed(2));
    return { labels, counts };
  }

  // ------------------------------------------------------------------
  // Separations
  // ------------------------------------------------------------------
  async function renderSeparations() {
    const data = await api.getSeparations();
    const rows = data.rows || [];
    const radarVals = rows.map((r) => r.radar_twr_nm).filter((x) => x != null);
    const hist = histogramBins(radarVals, 20);

    makeChart("chartSepHist", {
      type: "bar",
      data: {
        labels: hist.labels,
        datasets: [{
          label: "Radar TWR (NM)",
          data: hist.counts,
          backgroundColor: "#0077B6",
        }],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: "Histogram — radar TWR separation (NM)" },
          legend: { display: false },
        },
        scales: { x: { title: { display: true, text: "NM" } }, y: { title: { display: true, text: "Pairs" } } },
      },
    });

    const m = data.metrics || {};
    const total = data.total_pairs || rows.length;
    const pct = (n) => total ? ((n / total) * 100).toFixed(1) : "0.0";
    makeChart("chartSepViol", {
      type: "bar",
      data: {
        labels: ["Radar TWR", "Wake TWR", "Wake TMA", "LoA"],
        datasets: [{
          label: "% violations",
          data: [
            +pct(m.radar_twr_losses || 0),
            +pct(m.wake_twr_losses || 0),
            +pct(m.wake_tma_losses || 0),
            +pct(m.loa_losses || 0),
          ],
          backgroundColor: ["#E63946", "#F4A261", "#E9C46A", "#2A9D8F"],
        }],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: `Separation violations (% of ${total} pairs)` },
          legend: { display: false },
        },
        scales: { y: { beginAtZero: true, title: { display: true, text: "%" } } },
      },
    });

    const summary = $("sepSummary");
    if (summary) {
      summary.innerHTML = `
        <strong>${total}</strong> consecutive pairs ·
        radar losses: <strong>${m.radar_twr_losses || 0}</strong> ·
        wake TWR losses: <strong>${m.wake_twr_losses || 0}</strong> ·
        wake TMA losses: <strong>${m.wake_tma_losses || 0}</strong> ·
        LoA losses: <strong>${m.loa_losses || 0}</strong>
      `;
    }

    const a = $("csvSeparations");
    if (a) a.href = api.csvURL("separations");
  }

  // ------------------------------------------------------------------
  // Turn detection
  // ------------------------------------------------------------------
  async function renderTurns() {
    const data = await api.getTurns();
    const rows = data.rows || [];
    const detected = rows.filter((r) => r.turn_start_time);
    const dists = detected.map((r) => r.turn_start_dist_thr_nm).filter((x) => x != null);
    const hist = histogramBins(dists, 15);

    makeChart("chartTurnDist", {
      type: "bar",
      data: {
        labels: hist.labels,
        datasets: [{
          label: "Distance to THR at turn start (NM)",
          data: hist.counts,
          backgroundColor: "#2A9D8F",
        }],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: `Turn-start distance from THR — ${detected.length}/${rows.length} departures` },
          legend: { display: false },
        },
        scales: { x: { title: { display: true, text: "NM" } }, y: { title: { display: true, text: "Departures" } } },
      },
    });

    const tbody = $("turnsBody");
    if (tbody) {
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="center-text">No 24L departures.</td></tr>';
      } else {
        tbody.innerHTML = rows.map((r) => `
          <tr>
            <td>${r.callsign ?? "-"}</td>
            <td>${r.sid ?? "-"}</td>
            <td>${r.aircraft_type ?? "-"}</td>
            <td>${r.turn_start_time ? new Date(r.turn_start_time).toLocaleTimeString() : "-"}</td>
            <td>${r.turn_start_alt_ft != null ? Math.round(r.turn_start_alt_ft) : "-"}</td>
            <td>${r.turn_start_ias_kt != null ? Math.round(r.turn_start_ias_kt) : "-"}</td>
            <td>${r.turn_start_dist_thr_nm != null ? r.turn_start_dist_thr_nm.toFixed(2) : "-"}</td>
            <td>${r.detection_method ?? "-"}</td>
            <td>${r.crosses_r234 ? "✓" : "—"}</td>
          </tr>
        `).join("");
      }
    }

    const a = $("csvTurns");
    if (a) a.href = api.csvURL("turns");
  }

  // ------------------------------------------------------------------
  // NADP
  // ------------------------------------------------------------------
  async function renderNadp() {
    const thr = parseFloat($("nadpThreshold")?.value || "30") || 30;
    const data = await api.getNadp(thr);
    const rows = data.rows || [];
    const m = data.metrics || {};

    makeChart("chartNadpPie", {
      type: "doughnut",
      data: {
        labels: ["NADP1", "NADP2", "Unclassified"],
        datasets: [{
          data: [m.nadp1 || 0, m.nadp2 || 0, m.unclassified || 0],
          backgroundColor: ["#0077B6", "#E63946", "#999999"],
        }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: `NADP split (Δ-IAS threshold = ${thr} kt)` } },
      },
    });

    const deltas = rows.map((r) => r.delta_ias_kt).filter((x) => x != null);
    const hist = histogramBins(deltas, 15);
    makeChart("chartNadpDelta", {
      type: "bar",
      data: {
        labels: hist.labels,
        datasets: [{
          label: "ΔIAS 800→3000 ft (kt)",
          data: hist.counts,
          backgroundColor: "#F4A261",
        }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "ΔIAS histogram (800 → 3000 ft)" }, legend: { display: false } },
        scales: { x: { title: { display: true, text: "kt" } }, y: { title: { display: true, text: "Departures" } } },
      },
    });

    const tbody = $("nadpBody");
    if (tbody) {
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="center-text">No 24L departures.</td></tr>';
      } else {
        tbody.innerHTML = rows.map((r) => `
          <tr>
            <td>${r.callsign ?? "-"}</td>
            <td>${r.sid ?? "-"}</td>
            <td>${r.aircraft_type ?? "-"}</td>
            <td>${r.ias_at_800ft != null ? r.ias_at_800ft.toFixed(0) : "-"}</td>
            <td>${r.ias_at_3000ft != null ? r.ias_at_3000ft.toFixed(0) : "-"}</td>
            <td>${r.delta_ias_kt != null ? r.delta_ias_kt.toFixed(1) : "-"}</td>
            <td>${r.nadp ?? "-"}</td>
          </tr>
        `).join("");
      }
    }

    const a = $("csvNadp");
    if (a) a.href = api.csvURL("nadp", { threshold_kt: thr });
  }

  // ------------------------------------------------------------------
  // Thresholds
  // ------------------------------------------------------------------
  async function renderThresholds() {
    const data = await api.getThresholds();
    const rows = data.rows || [];
    const summary = data.summary || {};

    const alts = rows.map((r) => r.cross_alt_ft).filter((x) => x != null);
    const ias = rows.map((r) => r.cross_ias_kt).filter((x) => x != null);

    const histAlt = histogramBins(alts, 15);
    const histIas = histogramBins(ias, 15);

    makeChart("chartThrAlt", {
      type: "bar",
      data: {
        labels: histAlt.labels,
        datasets: [{ label: "Altitude at THR (ft)", data: histAlt.counts, backgroundColor: "#264653" }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "Altitude at threshold pass" }, legend: { display: false } },
        scales: { x: { title: { display: true, text: "ft" } }, y: { title: { display: true, text: "Departures" } } },
      },
    });

    makeChart("chartThrIas", {
      type: "bar",
      data: {
        labels: histIas.labels,
        datasets: [{ label: "IAS at THR (kt)", data: histIas.counts, backgroundColor: "#E76F51" }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: "IAS at threshold pass" }, legend: { display: false } },
        scales: { x: { title: { display: true, text: "kt" } }, y: { title: { display: true, text: "Departures" } } },
      },
    });

    const sum = $("thrSummary");
    if (sum) {
      const parts = Object.entries(summary).map(([rwy, s]) =>
        `${rwy}: <strong>${s.total}</strong> deps · turned-before-THR <strong>${s.pct_turned_before_thr}%</strong>` +
        (s.ias_mean_kt != null ? ` · mean IAS ${s.ias_mean_kt.toFixed(0)} kt` : "") +
        (s.alt_mean_ft != null ? ` · mean alt ${s.alt_mean_ft.toFixed(0)} ft` : "")
      );
      sum.innerHTML = parts.length ? parts.join(" · ") : "No threshold passes detected.";
    }

    const a = $("csvThresholds");
    if (a) a.href = api.csvURL("thresholds");
    const combined = $("csvCombined");
    if (combined) combined.href = api.csvURL("combined-results");
  }

  // ------------------------------------------------------------------
  // Orchestration
  // ------------------------------------------------------------------
  async function runAll() {
    setAnaStatus("Running analyses…", true);
    try {
      await renderSeparations();
      await renderTurns();
      await renderNadp();
      await renderThresholds();
      setAnaStatus("Done.", false);
    } catch (err) {
      console.error(err);
      setAnaStatus(`Error: ${err.message}`, false);
    }
  }

  function init() {
    const btn = $("anaRunBtn");
    if (btn) btn.addEventListener("click", runAll);
    wireCsvDownloads();
    const thr = $("nadpThreshold");
    if (thr) {
      thr.addEventListener("change", () => {
        renderNadp().catch((e) => setAnaStatus(`NADP error: ${e.message}`, false));
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
