import { useRef, useState } from "react";
import { api } from "../api.js";

export default function Sidebar({ docs, active, onSelect, onUploaded, onDelete }) {
  const input = useRef(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  async function handleFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const res = await api.upload(file);
      onUploaded(res.doc_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <aside className="rail">
      <div className="brand">Tender Desk</div>

      <input ref={input} type="file" accept=".pdf,application/pdf" hidden onChange={handleFile} />
      <button className="btn primary wide" onClick={() => input.current.click()} disabled={uploading}>
        {uploading ? "Uploading…" : "Add tender PDF"}
      </button>
      {error && <p className="error small">{error}</p>}

      <h2 className="rail-title">Tenders</h2>
      {docs.length === 0 && <p className="muted small">Nothing here yet. Add a tender PDF to start.</p>}

      <ul className="doc-list">
        {docs.map((d) => {
          const working = d.state === "queued" || d.state === "processing";
          const ready = d.state === "done";
          return (
            <li key={d.doc_id}>
              <button className={`doc ${d.doc_id === active ? "on" : ""}`} disabled={!ready}
                      onClick={() => onSelect(d.doc_id)} title={d.name}>
                <span className="doc-name">{d.name}</span>
                {ready && <span className="muted small">{d.pages} pages · {d.chunks} passages</span>}
                {working && (
                  <>
                    <span className="muted small">{d.message} · {d.percent}%</span>
                    <span className="bar"><span style={{ width: `${d.percent}%` }} /></span>
                  </>
                )}
                {d.state === "error" && <span className="error small">{d.message}</span>}
              </button>
              {!working && (
                <button className="icon-btn" aria-label={`Delete ${d.name}`} onClick={() => onDelete(d.doc_id)}>×</button>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
