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
}

// Export for use
const api = new APIClient();
