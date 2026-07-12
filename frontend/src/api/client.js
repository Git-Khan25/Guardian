const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  listDemos: () => request("/demo"),
  getDemo: (appName) => request(`/demo/${appName}`),
  startScan: (url) =>
    request("/scan", { method: "POST", body: JSON.stringify({ url }) }),
  getStatus: (scanId) => request(`/scan/${scanId}/status`),
  getReport: (scanId) => request(`/scan/${scanId}/report`),
};
