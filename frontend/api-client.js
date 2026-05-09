/**
 * API Client for ATM Analyzer Backend
 */

class APIClient {
  constructor(baseURL = "/api") {
    this.baseURL = baseURL;
  }

  async uploadCSV(file) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${this.baseURL}/datasets/mvp/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Upload failed");
    }

    return await response.json();
  }

  async getData(limit = 1000, offset = 0) {
    const params = new URLSearchParams({ limit, offset });
    const response = await fetch(`${this.baseURL}/datasets/mvp/data?${params}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to fetch data");
    }

    return await response.json();
  }

  async getInfo() {
    const response = await fetch(`${this.baseURL}/datasets/mvp/info`);

    if (!response.ok) {
      throw new Error("Failed to fetch info");
    }

    return await response.json();
  }

  async _getJSON(path, params = {}) {
    const qs = new URLSearchParams(params);
    const url = `${this.baseURL}${path}${qs.toString() ? `?${qs}` : ""}`;
    const response = await fetch(url);
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const err = await response.json();
        detail = err.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return await response.json();
  }

  getSeparations() { return this._getJSON("/datasets/mvp/separations"); }
  getTurns()       { return this._getJSON("/datasets/mvp/turns"); }
  getNadp(thresholdKt = 30) {
    return this._getJSON("/datasets/mvp/nadp", { threshold_kt: thresholdKt });
  }
  getThresholds() { return this._getJSON("/datasets/mvp/thresholds"); }
  getStats(opts = {}) {
    const params = {};
    if (opts.dataset) params.dataset = opts.dataset;
    if (opts.metric) params.metric = opts.metric;
    if (opts.groupby) params.groupby = opts.groupby;
    if (opts.violation_col) params.violation_col = opts.violation_col;
    return this._getJSON("/datasets/mvp/stats", params);
  }

  csvURL(name, params = {}) {
    const qs = new URLSearchParams({ format: "csv", ...params });
    return `${this.baseURL}/datasets/mvp/${name}?${qs}`;
  }
}

// Export for use
const api = new APIClient();
