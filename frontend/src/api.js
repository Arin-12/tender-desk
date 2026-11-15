const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.status === "error") {
    throw new Error(data.message || `Request failed (${res.status})`);
  }
  return data;
}

const post = (path, body) =>
  req(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  documents: () => req("/api/documents"),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return req("/api/upload", { method: "POST", body: form });
  },
  remove: (id) => req(`/api/documents/${id}`, { method: "DELETE" }),
  chat: (doc_id, query, k) => post("/api/chat", { doc_id, query, k }),
  search: (doc_id, query) => post("/api/search", { doc_id, query }),
  analyze: (doc_id, type, refresh = false) => post("/api/analyze", { doc_id, type, refresh }),
  checkBid: (doc_id, profile) => post("/api/eligibility/check", { doc_id, profile }),
  compare: (doc_a, doc_b) => post("/api/compare", { doc_a, doc_b }),
  exportUrl: (id) => `${BASE}/api/export/${id}`,
};
