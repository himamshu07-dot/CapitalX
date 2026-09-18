/**
 * CapitalX Backend API Client
 */

// Default to local backend or production Render URL
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://capitalx-backend.onrender.com'; // Render deployment target

export class ApiClient {
  static async checkHealth() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  static async optimizePortfolio(payload) {
    const res = await fetch(`${API_BASE_URL}/api/v1/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      let errorMsg = 'Optimization request failed';
      try {
        const errJson = await res.json();
        errorMsg = errJson.detail || errJson.message || errorMsg;
      } catch (e) {
        errorMsg = `Server error HTTP ${res.status}`;
      }
      throw new Error(errorMsg);
    }

    return await res.json();
  }
}
