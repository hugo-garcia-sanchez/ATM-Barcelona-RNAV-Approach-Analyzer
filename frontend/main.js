/**
 * ATM Barcelona RNAV Approach Analyzer - Frontend MVP
 */

// ============================================
// STATE MANAGEMENT
// ============================================

const state = {
  currentData: null,
  map: null,
  markers: {},
  allRecords: [], // All records fetched from backend
  displayRecords: [], // Filtered records
  currentPage: 1,
  pageSize: 100, // Show 100 rows per page for better performance
};

const elements = {
  statusText: document.getElementById("statusText"),
  spinner: document.getElementById("spinner"),
  uploadArea: document.getElementById("uploadArea"),
  fileInput: document.getElementById("fileInput"),
  browseBtn: document.getElementById("browseBtn"),
  clearBtn: document.getElementById("clearBtn"),
  datasetInfo: document.getElementById("datasetInfo"),
  minAlt: document.getElementById("minAlt"),
  maxAlt: document.getElementById("maxAlt"),
  minSpeed: document.getElementById("minSpeed"),
  maxSpeed: document.getElementById("maxSpeed"),
  timeFrom: document.getElementById("timeFrom"),
  timeTo: document.getElementById("timeTo"),
  callsignFilter: document.getElementById("callsignFilter"),
  filterBtn: document.getElementById("filterBtn"),
  clearFiltersBtn: document.getElementById("clearFiltersBtn"),
  filterPreviewCount: document.getElementById("filterPreviewCount"),
  recordCount: document.getElementById("recordCount"),
  tableBody: document.getElementById("tableBody"),
  pageInfo: document.getElementById("pageInfo"),
  prevPageBtn: document.getElementById("prevPageBtn"),
  nextPageBtn: document.getElementById("nextPageBtn"),
  exportBtn: document.getElementById("exportBtn"),
  mapContainer: document.getElementById("map"),
};

const RUNWAY_24L = { lat: 41.2858, lng: 2.0725, name: "RWY 24L" };
const RUNWAY_06R = { lat: 41.3045, lng: 2.1001, name: "RWY 06R" };

// ============================================
// UTILITY FUNCTIONS
// ============================================

function setStatus(message, isLoading = false) {
  elements.statusText.textContent = message;
  if (isLoading) {
    elements.spinner.classList.remove("hidden");
  } else {
    elements.spinner.classList.add("hidden");
  }
}

function formatCoordinate(value) {
  return Number(value).toFixed(4);
}

function formatAltitude(value) {
  return value ? Number(value).toLocaleString() : "-";
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatSpeed(value) {
  return value ? Number(value).toFixed(1) : "-";
}

// ============================================
// UPLOAD HANDLERS
// ============================================

function setupUploadHandlers() {
  // File input change
  elements.fileInput.addEventListener("change", (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  // Browse button
  elements.browseBtn.addEventListener("click", () => {
    elements.fileInput.click();
  });

  // Drag and drop
  elements.uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    elements.uploadArea.classList.add("dragover");
  });

  elements.uploadArea.addEventListener("dragleave", () => {
    elements.uploadArea.classList.remove("dragover");
  });

  elements.uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    elements.uploadArea.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  // Clear button
  elements.clearBtn.addEventListener("click", clearData);
}

async function handleFileUpload(file) {
  setStatus(`Uploading ${file.name}...`, true);

  try {
    const result = await api.uploadCSV(file);
    setStatus(`Loaded: ${result.filename} (${result.rows} rows)`, false);

    // Update UI
    updateDatasetInfo(result);
    initializeMap();  // Initialize map FIRST
    loadTableData();  // Then load data (which triggers updateMapMarkers)

    elements.clearBtn.disabled = false;
    elements.exportBtn.disabled = false;
  } catch (error) {
    setStatus(`Error: ${error.message}`, false);
    alert(`Upload failed: ${error.message}`);
  }
}

function clearData() {
  if (!confirm("Are you sure you want to clear all data?")) return;
  
  state.currentData = null;
  state.allRecords = [];
  state.displayRecords = [];
  state.currentPage = 1;
  
  elements.datasetInfo.innerHTML = "<p>No data loaded</p>";
  elements.tableBody.innerHTML =
    '<tr><td colspan="8" class="center-text">No data loaded. Upload a CSV file to begin.</td></tr>';
  elements.recordCount.textContent = "0 records";
  elements.pageInfo.textContent = "Page 0 of 0";
  elements.clearBtn.disabled = true;
  elements.exportBtn.disabled = true;
  elements.prevPageBtn.disabled = true;
  elements.nextPageBtn.disabled = true;
  elements.fileInput.value = "";
  elements.filterPreviewCount.textContent = "—";

  if (state.map) {
    state.map.remove();
    state.map = null;
    elements.mapContainer.innerHTML = "";
  }

  setStatus("Ready", false);
}

// ============================================
// DATA LOADING
// ============================================

async function loadTableData() {
  setStatus("Loading data...", true);

  try {
    // Increase limit to 100,000 to fetch everything in one go (backend updated)
    const response = await api.getData(100000, 0);
    state.allRecords = response.rows;
    state.displayRecords = response.rows;
    state.currentPage = 1;

    applyFilters();
    renderTablePage();
    updateFilterPreview();
    setStatus("Data loaded", false);
  } catch (error) {
    setStatus(`Error loading data: ${error.message}`, false);
    alert(`Failed to load data: ${error.message}`);
  }
}

function updateDatasetInfo(info) {
  const html = `
    <p><strong>File:</strong> ${info.filename}</p>
    <p><strong>Rows:</strong> ${info.rows.toLocaleString()}</p>
    <p><strong>Columns:</strong> ${info.columns}</p>
  `;
  elements.datasetInfo.innerHTML = html;
  state.currentData = info;
}

// ============================================
// FILTERING
// ============================================

function readFilterInputs() {
  return {
    callsign: elements.callsignFilter.value.toUpperCase(),
    minAlt: elements.minAlt.value ? Number(elements.minAlt.value) : null,
    maxAlt: elements.maxAlt.value ? Number(elements.maxAlt.value) : null,
    minSpeed: elements.minSpeed.value ? Number(elements.minSpeed.value) : null,
    maxSpeed: elements.maxSpeed.value ? Number(elements.maxSpeed.value) : null,
    timeFrom: elements.timeFrom.value,
    timeTo: elements.timeTo.value,
  };
}

function setupFilterHandlers() {
  elements.filterBtn.addEventListener("click", () => {
    state.currentPage = 1;
    applyFilters();
    renderTablePage();
  });

  elements.clearFiltersBtn.addEventListener("click", () => {
    clearFilters();
  });

  const inputs = [
    elements.minAlt, elements.maxAlt,
    elements.minSpeed, elements.maxSpeed,
    elements.timeFrom, elements.timeTo,
    elements.callsignFilter,
  ];
  inputs.forEach((input) => {
    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        state.currentPage = 1;
        applyFilters();
        renderTablePage();
      }
    });
    input.addEventListener("input", updateFilterPreview);
    input.addEventListener("change", updateFilterPreview);
  });
}

function clearFilters() {
  elements.callsignFilter.value = "";
  elements.minAlt.value = "";
  elements.maxAlt.value = "";
  elements.minSpeed.value = "";
  elements.maxSpeed.value = "";
  elements.timeFrom.value = "";
  elements.timeTo.value = "";
    
  state.currentPage = 1;
  applyFilters();
  renderTablePage();
}

function applyFilters() {
  const f = readFilterInputs();
  state.displayRecords = state.allRecords.filter((r) => matchesFilters(r, f));
  updateMapMarkers();
  updateFilterPreview();
  elements.exportBtn.disabled = state.displayRecords.length === 0;
}

function timeToMinutes(hhmm) {
  if (!hhmm) return null;
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function recordTimeMinutes(record) {
  const t = record.time;
  if (!t) return null;
  const d = new Date(t);
  if (isNaN(d.getTime())) return null;
  return d.getHours() * 60 + d.getMinutes();
}

function matchesFilters(record, f) {
  if (f.minAlt !== null && record.altitude < f.minAlt) return false;
  if (f.maxAlt !== null && record.altitude > f.maxAlt) return false;
  if (f.minSpeed !== null && (record.speed == null || record.speed < f.minSpeed)) return false;
  if (f.maxSpeed !== null && (record.speed == null || record.speed > f.maxSpeed)) return false;

  const fromMin = timeToMinutes(f.timeFrom);
  const toMin = timeToMinutes(f.timeTo);
  if (fromMin !== null || toMin !== null) {
    const recMin = recordTimeMinutes(record);
    if (recMin === null) return false;
    if (fromMin !== null && toMin !== null) {
      if (fromMin <= toMin) {
        if (recMin < fromMin || recMin > toMin) return false;
      } else {
        // Wrap past midnight
        if (recMin < fromMin && recMin > toMin) return false;
      }
    } else if (fromMin !== null && recMin < fromMin) return false;
    else if (toMin !== null && recMin > toMin) return false;
  }

  if (f.callsign && !(record.callsign || "").toUpperCase().includes(f.callsign)) return false;
  return true;
}

function updateFilterPreview() {
  if (!state.allRecords.length) {
    elements.filterPreviewCount.textContent = "—";
    return;
  }
  const f = readFilterInputs();
  let count = 0;
  for (const r of state.allRecords) if (matchesFilters(r, f)) count++;
  elements.filterPreviewCount.textContent = `${count.toLocaleString()} / ${state.allRecords.length.toLocaleString()}`;
}

// ============================================
// TABLE RENDERING
// ============================================

function renderTablePage() {
  const total = state.displayRecords.length;
  const totalPages = Math.ceil(total / state.pageSize) || 0;

  // Clamp current page
  if (state.currentPage > totalPages) state.currentPage = totalPages;
  if (state.currentPage < 1 && totalPages > 0) state.currentPage = 1;

  const start = (state.currentPage - 1) * state.pageSize;
  const end = Math.min(start + state.pageSize, total);
  const pageSlice = state.displayRecords.slice(start, end);

  elements.tableBody.innerHTML = "";
  if (pageSlice.length === 0) {
    const message = state.allRecords.length
      ? "No records match the filters"
      : "No data loaded. Upload a CSV file to begin.";
    elements.tableBody.innerHTML = `<tr><td colspan="8" class="center-text">${message}</td></tr>`;
  } else {
    pageSlice.forEach((record) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${formatTime(record.time)}</td>
        <td>${record.callsign || "-"}</td>
        <td>${record.track_number || "-"}</td>
        <td>${formatCoordinate(record.latitude)}</td>
        <td>${formatCoordinate(record.longitude)}</td>
        <td>${formatAltitude(record.altitude)}</td>
        <td>${formatSpeed(record.speed)}</td>
        <td>${record.runway || "-"}</td>
      `;
      elements.tableBody.appendChild(row);
    });
  }

  const rangeStart = total > 0 ? start + 1 : 0;
  const rangeEnd = Math.min(end, total);
  elements.recordCount.textContent = total > 0
    ? `Viewing ${rangeStart}-${rangeEnd} of ${total.toLocaleString()} records`
    : "0 records";
  elements.pageInfo.textContent = `Page ${totalPages > 0 ? state.currentPage : 0} of ${totalPages}`;
  elements.prevPageBtn.disabled = state.currentPage <= 1;
  elements.nextPageBtn.disabled = state.currentPage >= totalPages;
}

function setupPaginationHandlers() {
  elements.prevPageBtn.addEventListener("click", () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      renderTablePage();
    }
  });

  elements.nextPageBtn.addEventListener("click", () => {
    const totalPages = Math.ceil(state.displayRecords.length / state.pageSize);
    if (state.currentPage < totalPages) {
      state.currentPage++;
      renderTablePage();
    }
  });
}

// ============================================
// MAP FUNCTIONS
// ============================================

function initializeMap() {
  if (state.map) return;

  // Use Canvas renderer for better performance with many points
  state.map = L.map(elements.mapContainer, {
    preferCanvas: true
  }).setView([41.2974, 2.0833], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
  }).addTo(state.map);

  updateMapMarkers();
}

function updateMapMarkers() {
  if (!state.map) return;  // Exit if map not initialized
  
  // Clear existing markers
  Object.values(state.markers).forEach((marker) => state.map.removeLayer(marker));
  state.markers = {};

  // Render all filtered records on map (Canvas handles this well)
  state.displayRecords.forEach((record, idx) => {
    const marker = L.circleMarker(
      { lat: record.latitude, lng: record.longitude },
      {
        radius: 3, // Smaller radius for high density
        color: "#0077B6",
        weight: 0.5,
        fillOpacity: 0.5,
        fillColor: "#0077B6",
      }
    );

    const popupContent = `
      <strong>${record.callsign || "Unknown"}</strong><br>
      Alt: ${formatAltitude(record.altitude)} ft<br>
      Speed: ${formatSpeed(record.speed)} kt<br>
      Time: ${formatTime(record.time)}
    `;
    marker.bindPopup(popupContent);
    marker.addTo(state.map);
    state.markers[idx] = marker;
  });
}

// ============================================
// TAB SWITCHING
// ============================================

function setupTabHandlers() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      const tabPanel = document.getElementById(`${tab}Tab`);
      if (!tabPanel) return;

      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-content").forEach((panel) => panel.classList.remove("active"));
      tabPanel.classList.add("active");

      if (tab === "map") {
        setTimeout(() => {
          if (!state.map) initializeMap();
          state.map.invalidateSize();
        }, 100);
      }
    });
  });
}

// ============================================
// EXPORT FUNCTIONS
// ============================================

function setupExportHandlers() {
  elements.exportBtn.addEventListener("click", exportToCSV);
}

function escapeCSV(value) {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\n\r]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

function hasDesktopCsvSaver() {
  return !!(window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_csv === "function");
}

async function exportToCSV() {
  if (state.displayRecords.length === 0) {
    alert("No data to export");
    return;
  }

  const headers = Object.keys(state.displayRecords[0]);
  const rows = state.displayRecords.map((record) => headers.map((header) => escapeCSV(record[header])));
  const csv = [
    headers.map(escapeCSV).join(","),
    ...rows.map((row) => row.join(",")),
  ].join("\n");

  const filename = `atm_filtered_${state.displayRecords.length}rows_${Date.now()}.csv`;

  if (hasDesktopCsvSaver()) {
    try {
      const result = await window.pywebview.api.save_csv(filename, csv);
      if (result && result.status === "cancelled") {
        setStatus("Guardado cancelado.", false);
        return;
      }
      if (result && result.status === "error") {
        throw new Error(result.message || "No se pudo guardar el CSV");
      }
      setStatus(`Exported ${state.displayRecords.length} filtered records`, false);
      return;
    } catch (err) {
      alert(`Export failed: ${err.message}`);
      setStatus(`Error: ${err.message}`, false);
      return;
    }
  }

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);

  setStatus(`Exported ${state.displayRecords.length} filtered records`, false);
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener("DOMContentLoaded", () => {
  setupUploadHandlers();
  setupFilterHandlers();
  setupPaginationHandlers();
  setupTabHandlers();
  setupExportHandlers();

  // Try to load initial info
  api.getInfo().then((info) => {
    if (info.status === "loaded") {
      updateDatasetInfo(info);
      initializeMap();
      loadTableData();
      elements.clearBtn.disabled = false;
      elements.exportBtn.disabled = false;
    }
  }).catch(() => {
    // No data loaded yet, normal state
  });
});
