/**
 * ATM Analyzer - Main Application Logic
 */

// Constants
const BARCELONA_CENTER = { lat: 41.2974, lng: 2.0833 };
const DEFAULT_ZOOM = 12;
const RUNWAY_24L = { lat: 41.2865, lng: 2.0759, name: "RWY 24L" };
const RUNWAY_06R = { lat: 41.2870, lng: 2.0760, name: "RWY 06R" };

// State Management
const state = {
  currentData: null,
  allRecords: [],
  displayRecords: [],
  currentPage: 0,
  pageSize: 500,  // FIX 3: Increased from 100 to 500 records per page
  filters: {
    minAlt: null,
    maxAlt: null,
    callsign: "",
  },
  map: null,
  markers: {},
};

// ============================================
// DOM ELEMENTS
// ============================================

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
  callsignFilter: document.getElementById("callsignFilter"),
  filterBtn: document.getElementById("filterBtn"),
  recordCount: document.getElementById("recordCount"),
  tableBody: document.getElementById("tableBody"),
  pageInfo: document.getElementById("pageInfo"),
  prevPageBtn: document.getElementById("prevPageBtn"),
  nextPageBtn: document.getElementById("nextPageBtn"),
  exportBtn: document.getElementById("exportBtn"),
  mapContainer: document.getElementById("map"),
};

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
  state.currentData = null;
  state.allRecords = [];
  state.displayRecords = [];
  state.currentPage = 0;

  elements.datasetInfo.innerHTML = "<p>No data loaded</p>";
  elements.tableBody.innerHTML =
    '<tr><td colspan="6" class="center-text">No data loaded. Upload a CSV file to begin.</td></tr>';
  elements.recordCount.textContent = "0 records";
  elements.clearBtn.disabled = true;
  elements.exportBtn.disabled = true;

  // FIX 5: Reset file input so "Choose File" works again
  elements.fileInput.value = "";

  setStatus("Data cleared", false);

  // Clear map
  if (state.map) {
    Object.values(state.markers).forEach((marker) => state.map.removeLayer(marker));
    state.markers = {};
  }
}

// ============================================
// DATA LOADING
// ============================================

async function loadTableData() {
  setStatus("Loading data...", true);

  try {
    const response = await api.getData(10000, 0);
    state.allRecords = response.rows;
    state.displayRecords = response.rows;

    applyFilters();
    renderTablePage();
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

function setupFilterHandlers() {
  elements.filterBtn.addEventListener("click", applyFilters);

  [elements.minAlt, elements.maxAlt, elements.callsignFilter].forEach((input) => {
    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") applyFilters();
    });
  });
}

function applyFilters() {
  const minAlt = elements.minAlt.value ? parseFloat(elements.minAlt.value) : null;
  const maxAlt = elements.maxAlt.value ? parseFloat(elements.maxAlt.value) : null;
  const callsign = elements.callsignFilter.value.toUpperCase();

  // FIX 4: Debug logging for filters
  console.log("Filters applied:", { minAlt, maxAlt, callsign, totalRecords: state.allRecords.length });

  state.filters = { minAlt, maxAlt, callsign };

  state.displayRecords = state.allRecords.filter((record) => {
    if (minAlt !== null && record.altitude < minAlt) return false;
    if (maxAlt !== null && record.altitude > maxAlt) return false;
    if (callsign && !record.callsign?.toUpperCase().includes(callsign)) return false;
    return true;
  });

  console.log("After filter:", state.displayRecords.length, "records");

  state.currentPage = 0;
  renderTablePage();
  updateMapMarkers();

  setStatus(`Filtered: ${state.displayRecords.length} records`, false);
}

// ============================================
// TABLE RENDERING
// ============================================

function renderTablePage() {
  const start = state.currentPage * state.pageSize;
  const end = start + state.pageSize;
  const pageRecords = state.displayRecords.slice(start, end);

  const tbody = elements.tableBody;
  const thead = elements.tableBody.parentElement.querySelector("thead");
  
  // FIX 2: Generate columns dynamically from first record
  if (pageRecords.length > 0 && state.displayRecords.length > 0) {
    const firstRecord = state.displayRecords[0];
    const columns = Object.keys(firstRecord);
    
    // Update header
    const headerRow = thead.querySelector("tr");
    headerRow.innerHTML = columns.map(col => `<th>${col}</th>`).join("");
  }

  tbody.innerHTML = "";

  if (pageRecords.length === 0) {
    const colCount = state.displayRecords.length > 0 ? Object.keys(state.displayRecords[0]).length : 6;
    tbody.innerHTML =
      `<tr><td colspan="${colCount}" class="center-text">No records match the filters</td></tr>`;
  } else {
    pageRecords.forEach((record) => {
      const row = document.createElement("tr");
      const columns = Object.keys(record);
      const cells = columns.map(col => {
        const value = record[col];
        // Format special columns
        if (col === "time") return formatTime(value);
        if (col === "latitude" || col === "longitude") return formatCoordinate(value);
        if (col === "altitude") return formatAltitude(value);
        if (col === "speed") return formatSpeed(value);
        return value || "-";
      });
      row.innerHTML = cells.map(cell => `<td>${cell}</td>`).join("");
      tbody.appendChild(row);
    });
  }

  const totalPages = Math.ceil(state.displayRecords.length / state.pageSize);
  elements.pageInfo.textContent = `Page ${state.currentPage + 1} of ${Math.max(1, totalPages)}`;
  elements.prevPageBtn.disabled = state.currentPage === 0;
  elements.nextPageBtn.disabled = state.currentPage >= totalPages - 1;

  elements.recordCount.textContent = `${state.displayRecords.length} records`;
}

function setupPaginationHandlers() {
  elements.prevPageBtn.addEventListener("click", () => {
    if (state.currentPage > 0) {
      state.currentPage--;
      renderTablePage();
    }
  });

  elements.nextPageBtn.addEventListener("click", () => {
    const totalPages = Math.ceil(state.displayRecords.length / state.pageSize);
    if (state.currentPage < totalPages - 1) {
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

  state.map = L.map(elements.mapContainer).setView(BARCELONA_CENTER, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(state.map);

  L.circleMarker(RUNWAY_24L, {
    radius: 8,
    color: "red",
    weight: 2,
    fillOpacity: 0.5,
    fillColor: "red",
  })
    .bindPopup(`${RUNWAY_24L.name} - Threshold`)
    .addTo(state.map);

  L.circleMarker(RUNWAY_06R, {
    radius: 8,
    color: "red",
    weight: 2,
    fillOpacity: 0.5,
    fillColor: "red",
  })
    .bindPopup(`${RUNWAY_06R.name} - Threshold`)
    .addTo(state.map);

  updateMapMarkers();
}

function updateMapMarkers() {
  if (!state.map) return;  // Exit if map not initialized
  
  Object.values(state.markers).forEach((marker) => state.map.removeLayer(marker));
  state.markers = {};

  state.displayRecords.forEach((record, idx) => {
    const marker = L.circleMarker(
      { lat: record.latitude, lng: record.longitude },
      {
        radius: 5,
        color: "#0077B6",
        weight: 1,
        fillOpacity: 0.7,
        fillColor: "#0077B6",
      }
    );

    const popupContent = `
      <strong>${record.callsign || "Unknown"}</strong><br>
      Lat: ${formatCoordinate(record.latitude)}<br>
      Lon: ${formatCoordinate(record.longitude)}<br>
      Alt: ${formatAltitude(record.altitude)} ft<br>
      Time: ${formatTime(record.time)}<br>
      Speed: ${formatSpeed(record.speed)} kts
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

      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      document.getElementById(`${tab}Tab`).classList.add("active");

      // FIX 1: Ensure map renders properly when tab becomes visible
      if (tab === "map") {
        setTimeout(() => {
          if (state.map) {
            state.map.invalidateSize();
          } else {
            initializeMap();
          }
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

function exportToCSV() {
  if (state.displayRecords.length === 0) {
    alert("No data to export");
    return;
  }

  const headers = ["Callsign", "Latitude", "Longitude", "Altitude (ft)", "Time", "Speed (kts)"];
  const rows = state.displayRecords.map((r) => [
    r.callsign || "",
    r.latitude,
    r.longitude,
    r.altitude,
    r.time,
    r.speed || "",
  ]);

  const csv = [headers, ...rows].map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `atm_data_${new Date().getTime()}.csv`;
  link.click();

  setStatus("Data exported", false);
}

// ============================================
// INITIALIZATION
// ============================================

function initializeApp() {
  console.log("ATM Analyzer - Initializing...");

  setupUploadHandlers();
  setupFilterHandlers();
  setupPaginationHandlers();
  setupTabHandlers();
  setupExportHandlers();

  setStatus("Ready", false);

  console.log("✅ Application ready");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeApp);
} else {
  initializeApp();
}
