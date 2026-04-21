const API = "/api/datasets";
const CENTER = { lat: 41.2974, lon: 2.0833 };
const ZOOM = 11;

const state = {
	datasets: [],
	inputFiles: [],
	selectedDatasetId: "",
	selectedInputFile: "P3_04h_08h.csv",
	records: [],
	summary: null,
	flightFilter: "",
	minAltitude: "",
	maxAltitude: "",
	status: "idle",
	lastMessage: "Waiting for action",
	loading: false,
	websocket: null,
	visibleRecords: [],
};

const app = document.getElementById("app");

async function readJsonSafe(response, fallback) {
	const text = await response.text();
	if (!text) return fallback;
	try {
		return JSON.parse(text);
	} catch {
		return fallback;
	}
}

function formatNumber(value) {
	if (value === null || value === undefined || Number.isNaN(Number(value))) {
		return "-";
	}
	return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function altitudeValue(record) {
	const raw = record?.payload?.["H(ft)"];
	const parsed = Number(raw);
	return Number.isNaN(parsed) ? null : parsed;
}

function flightTag(record) {
	return String(record?.payload?.TI || record?.label || "").toLowerCase();
}

function applyFilters() {
	state.visibleRecords = state.records.filter((record) => {
		if (record.latitude === null || record.longitude === null) {
			return false;
		}

		if (state.flightFilter && !flightTag(record).includes(state.flightFilter.toLowerCase())) {
			return false;
		}

		const altitude = altitudeValue(record);
		if (state.minAltitude && altitude !== null && altitude < Number(state.minAltitude)) {
			return false;
		}
		if (state.maxAltitude && altitude !== null && altitude > Number(state.maxAltitude)) {
			return false;
		}

		return true;
	});
}

function mapBounds(records) {
	const latSpan = 0.65 / Math.max(1, ZOOM / 10);
	const lonSpan = 0.95 / Math.max(1, ZOOM / 10);
	let minLat = CENTER.lat - latSpan;
	let maxLat = CENTER.lat + latSpan;
	let minLon = CENTER.lon - lonSpan;
	let maxLon = CENTER.lon + lonSpan;

	for (const record of records) {
		if (record.latitude === null || record.longitude === null) continue;
		minLat = Math.min(minLat, record.latitude);
		maxLat = Math.max(maxLat, record.latitude);
		minLon = Math.min(minLon, record.longitude);
		maxLon = Math.max(maxLon, record.longitude);
	}

	const latPadding = Math.max(0.02, (maxLat - minLat) * 0.12);
	const lonPadding = Math.max(0.02, (maxLon - minLon) * 0.12);
	return {
		minLat: minLat - latPadding,
		maxLat: maxLat + latPadding,
		minLon: minLon - lonPadding,
		maxLon: maxLon + lonPadding,
	};
}

function projectPoint(lat, lon, bounds, width, height) {
	const x = ((lon - bounds.minLon) / Math.max(bounds.maxLon - bounds.minLon, 0.0001)) * width;
	const y = height - ((lat - bounds.minLat) / Math.max(bounds.maxLat - bounds.minLat, 0.0001)) * height;
	return { x, y };
}

function drawGrid(context, width, height) {
	context.save();
	context.strokeStyle = "rgba(0, 123, 177, 0.15)";
	context.lineWidth = 1;
	for (let x = 0; x <= width; x += width / 8) {
		context.beginPath();
		context.moveTo(x, 0);
		context.lineTo(x, height);
		context.stroke();
	}
	for (let y = 0; y <= height; y += height / 6) {
		context.beginPath();
		context.moveTo(0, y);
		context.lineTo(width, y);
		context.stroke();
	}
	context.restore();
}

function renderMap() {
	const canvas = document.getElementById("mapCanvas");
	const context = canvas?.getContext("2d");
	if (!canvas || !context) return;

	const rect = canvas.getBoundingClientRect();
	const width = Math.max(1, Math.floor(rect.width));
	const height = Math.max(1, Math.floor(rect.height));
	const ratio = window.devicePixelRatio || 1;

	canvas.width = Math.floor(width * ratio);
	canvas.height = Math.floor(height * ratio);
	canvas.style.width = `${width}px`;
	canvas.style.height = `${height}px`;
	context.setTransform(ratio, 0, 0, ratio, 0, 0);

	context.clearRect(0, 0, width, height);
	context.fillStyle = "#ffffff";
	context.fillRect(0, 0, width, height);

	drawGrid(context, width, height);

	const bounds = mapBounds(state.visibleRecords);
	const center = projectPoint(CENTER.lat, CENTER.lon, bounds, width, height);

	context.fillStyle = "rgba(0, 123, 177, 0.15)";
	context.beginPath();
	context.arc(center.x, center.y, 8, 0, Math.PI * 2);
	context.fill();

	context.strokeStyle = "rgb(0, 123, 177)";
	context.lineWidth = 2;
	context.beginPath();
	context.arc(center.x, center.y, 4, 0, Math.PI * 2);
	context.stroke();

	for (const record of state.visibleRecords.slice(0, 4000)) {
		const point = projectPoint(record.latitude, record.longitude, bounds, width, height);
		context.fillStyle = "rgb(0, 123, 177)";
		context.beginPath();
		context.arc(point.x, point.y, 3.5, 0, Math.PI * 2);
		context.fill();
	}

	context.fillStyle = "#000000";
	context.font = "600 13px Roboto, Helvetica, Arial, sans-serif";
	context.fillText("Barcelona sector", 16, 24);
	context.font = "12px Roboto, Helvetica, Arial, sans-serif";
	context.fillText(`Visible points: ${formatNumber(state.visibleRecords.length)}`, 16, 42);
}

function renderRecordList() {
	const container = document.getElementById("recordList");
	if (!container) return;
	container.innerHTML = "";

	for (const record of state.visibleRecords.slice(0, 24)) {
		const row = document.createElement("div");
		row.className = "record-row";
		row.innerHTML = `
			<div>${record.payload?.TI || record.label || "Unknown"}</div>
			<div class="meta">${record.payload?.Time || "-"} · ${formatNumber(record.payload?.["H(ft)"])} ft · ${formatNumber(record.payload?.["GS(kt)"])} kt</div>
		`;
		container.appendChild(row);
	}

	if (state.visibleRecords.length === 0) {
		const empty = document.createElement("div");
		empty.className = "hint";
		empty.textContent = "No records match the current filters.";
		container.appendChild(empty);
	}
}

function renderApp() {
	app.innerHTML = `
		<header class="top-banner">
			<h1>BCN ATM ANALYZER</h1>
		</header>
		<div class="layout">
			<aside class="panel sidebar-panel">
				<section class="menu-group">
					<div class="subsection-title">Data</div>
					<div class="controls-grid">
						<div>
							<label for="datasetSelect">Dataset</label>
							<select id="datasetSelect">
								<option value="">Select dataset</option>
								${state.datasets.map((dataset) => `<option value="${dataset.id}">#${dataset.id} - ${dataset.filename}</option>`).join("")}
							</select>
						</div>
						<div>
							<label for="inputFileSelect">Import from data/inputs</label>
							<select id="inputFileSelect">
								<option value="">Select CSV</option>
								${state.inputFiles.map((file) => `<option value="${file.filename}">${file.filename} (${Math.round(file.size_bytes / 1024)} KB)</option>`).join("")}
							</select>
						</div>
					</div>
				</section>

				<section class="menu-group">
					<div class="subsection-title">Filters</div>
					<div class="controls-grid">
						<div>
							<label for="flightFilter">Flight tag filter</label>
							<input id="flightFilter" type="text" placeholder="RYR, VLG, BCS..." value="${state.flightFilter}" />
						</div>
						<div>
							<label for="minAltitude">Min altitude (ft)</label>
							<input id="minAltitude" type="number" value="${state.minAltitude}" />
						</div>
						<div>
							<label for="maxAltitude">Max altitude (ft)</label>
							<input id="maxAltitude" type="number" value="${state.maxAltitude}" />
						</div>
					</div>
				</section>

				<section class="menu-group">
					<div class="subsection-title">Actions</div>
					<div class="actions-row">
						<button class="ghost" id="refreshButton">Refresh snapshot</button>
						<button class="action" id="importButton" ${state.loading ? "disabled" : ""}>${state.loading ? "Processing..." : "Import selected CSV"}</button>
						<label class="upload-label" for="uploadInput">Upload CSV</label>
						<input id="uploadInput" type="file" accept=".csv" />
					</div>
				</section>

				<section class="menu-group">
					<div class="subsection-title">Summary</div>
					<div class="stats">
						<div>Total: ${formatNumber(state.summary?.total_records)}</div>
						<div>Geo: ${formatNumber(state.summary?.geo_records)}</div>
						<div>Visible: ${formatNumber(state.visibleRecords.length)}</div>
					</div>
				</section>
			</aside>

			<section class="content-column">
				<main class="panel map-panel">
					<div class="subsection-title">Map</div>
					<div class="map-wrap">
						<canvas id="mapCanvas" class="map-canvas"></canvas>
					</div>
				</main>

				<section class="panel records-panel">
					<div class="subsection-title">Records</div>
					<div class="muted">Current dataset: ${state.selectedDatasetId || "none"}</div>
					<div class="muted">Current input: ${state.selectedInputFile || "none"}</div>
					<div class="records-list" id="recordList"></div>
				</section>
			</section>
		</div>
	`;

	const datasetSelect = document.getElementById("datasetSelect");
	const inputFileSelect = document.getElementById("inputFileSelect");
	const flightFilter = document.getElementById("flightFilter");
	const minAltitude = document.getElementById("minAltitude");
	const maxAltitude = document.getElementById("maxAltitude");
	const refreshButton = document.getElementById("refreshButton");
	const importButton = document.getElementById("importButton");
	const uploadInput = document.getElementById("uploadInput");

	datasetSelect.value = state.selectedDatasetId;
	inputFileSelect.value = state.selectedInputFile;

	datasetSelect.addEventListener("change", async (event) => {
		state.selectedDatasetId = event.target.value;
		if (state.selectedDatasetId) {
			await loadDatasetData(state.selectedDatasetId);
			connectWebSocket(state.selectedDatasetId);
			render();
		}
	});

	inputFileSelect.addEventListener("change", (event) => {
		state.selectedInputFile = event.target.value;
		render();
	});

	flightFilter.addEventListener("input", (event) => {
		state.flightFilter = event.target.value;
		render();
	});

	minAltitude.addEventListener("input", (event) => {
		state.minAltitude = event.target.value;
		render();
	});

	maxAltitude.addEventListener("input", (event) => {
		state.maxAltitude = event.target.value;
		render();
	});

	refreshButton.addEventListener("click", () => {
		if (state.selectedDatasetId) loadDatasetData(state.selectedDatasetId);
	});

	importButton.addEventListener("click", importExistingInput);
	uploadInput.addEventListener("change", (event) => uploadCsv(event.target.files?.[0]));

	renderRecordList();
	renderMap();
}

async function loadDatasets() {
	const response = await fetch(API);
	const payload = await readJsonSafe(response, []);
	state.datasets = Array.isArray(payload) ? payload : [];
	if (!state.selectedDatasetId && state.datasets.length > 0) {
		state.selectedDatasetId = String(state.datasets[0].id);
	}
}

async function loadInputFiles() {
	const response = await fetch(`${API}/input-files`);
	const payload = await readJsonSafe(response, []);
	state.inputFiles = Array.isArray(payload) ? payload : [];
	if (state.inputFiles.length > 0 && !state.selectedInputFile) {
		state.selectedInputFile = state.inputFiles[0].filename;
	}
}

async function loadDatasetData(datasetId) {
	if (!datasetId) return;
	const [summaryResponse, recordsResponse] = await Promise.all([
		fetch(`${API}/${datasetId}/summary`),
		fetch(`${API}/${datasetId}/records?limit=5000&offset=0`),
	]);

	if (!summaryResponse.ok || !recordsResponse.ok) {
		state.summary = null;
		state.records = [];
		applyFilters();
		render();
		return;
	}

	state.summary = await readJsonSafe(summaryResponse, null);
	const recordsPayload = await readJsonSafe(recordsResponse, []);
	state.records = Array.isArray(recordsPayload) ? recordsPayload : [];
	applyFilters();
	render();
}

async function importExistingInput() {
	if (!state.selectedInputFile) return;
	state.loading = true;
	render();

	const response = await fetch(`${API}/import-existing/${encodeURIComponent(state.selectedInputFile)}`, { method: "POST" });
	const payload = await readJsonSafe(response, {});
	state.loading = false;

	if (!response.ok) {
		state.status = "error";
		state.lastMessage = payload.detail || "Import failed";
		render();
		return;
	}

	state.status = "connected";
	state.lastMessage = `Dataset imported with id ${payload.id}`;
	await loadDatasets();
	state.selectedDatasetId = String(payload.id);
	await loadDatasetData(String(payload.id));
	connectWebSocket(String(payload.id));
	render();
}

async function uploadCsv(file) {
	if (!file) return;
	state.loading = true;
	render();

	const formData = new FormData();
	formData.append("upload_file", file);
	const response = await fetch(`${API}/upload`, { method: "POST", body: formData });
	const payload = await readJsonSafe(response, {});
	state.loading = false;

	if (!response.ok) {
		state.status = "error";
		state.lastMessage = payload.detail || "Upload failed";
		render();
		return;
	}

	state.status = "connected";
	state.lastMessage = `Upload completed with id ${payload.id}`;
	await loadDatasets();
	state.selectedDatasetId = String(payload.id);
	await loadDatasetData(String(payload.id));
	connectWebSocket(String(payload.id));
	render();
}

function disconnectSocket() {
	if (state.websocket) {
		state.websocket.close();
		state.websocket = null;
	}
}

function connectWebSocket(datasetId) {
	if (!datasetId) return;
	disconnectSocket();
	const protocol = window.location.protocol === "https:" ? "wss" : "ws";
	const socket = new WebSocket(`${protocol}://${window.location.host}/ws/datasets/${datasetId}`);
	state.websocket = socket;

	socket.onopen = () => {
		state.status = "connected";
	};

	socket.onmessage = async (event) => {
		let data;
		try {
			data = JSON.parse(event.data);
		} catch {
			return;
		}
		if (data.type === "snapshot") {
			await loadDatasetData(datasetId);
		} else if (data.type === "error") {
			state.status = "error";
			render();
		}
	};

	socket.onerror = () => {
		state.status = "error";
		render();
	};

	socket.onclose = () => {
		state.status = "idle";
		render();
	};
}

async function bootstrap() {
	await loadDatasets();
	await loadInputFiles();
	applyFilters();
	render();

	if (state.selectedDatasetId) {
		await loadDatasetData(state.selectedDatasetId);
		connectWebSocket(state.selectedDatasetId);
	}
	render();

	window.addEventListener("resize", renderMap);
	window.addEventListener("beforeunload", disconnectSocket);
}

function render() {
	applyFilters();
	renderApp();
}

bootstrap().catch((error) => {
	console.error(error);
	app.innerHTML = `<div class="panel" style="margin: 16px;">Failed to start application: ${error.message}</div>`;
});
