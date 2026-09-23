/**
 * CapitalX Backend API Client
 */

export function getApiBaseUrl() {
  const customUrl = localStorage.getItem('capitalx_api_url');
  if (customUrl) return customUrl.replace(/\/+$/, '');

  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : (window.CAPITALX_API_URL || 'https://capitalx-826z.onrender.com');
}

export class ApiClient {
  static async checkHealth() {
    try {
      const url = getApiBaseUrl();
      const res = await fetch(`${url}/api/v1/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(8000)
      });
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  static async optimizePortfolio(payload) {
    const url = getApiBaseUrl();
    const res = await fetch(`${url}/api/v1/optimize`, {
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
