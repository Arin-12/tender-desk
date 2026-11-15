import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import Ask from "./components/Ask.jsx";
import Analysis from "./components/Analysis.jsx";
import BidCheck from "./components/BidCheck.jsx";
import Compare from "./components/Compare.jsx";
import Evidence from "./components/Evidence.jsx";

const TABS = [
  { id: "ask", label: "Ask" },
  { id: "analysis", label: "Analysis" },
  { id: "bid", label: "Bid check" },
  { id: "compare", label: "Compare" },
];

export default function App() {
  const [docs, setDocs] = useState([]);
  const [active, setActive] = useState(null);
  const [tab, setTab] = useState("ask");
  const [evidence, setEvidence] = useState(null);
  const [backendDown, setBackendDown] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.documents();
      setDocs(data.documents);
      setBackendDown(false);
    } catch {
      setBackendDown(true);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const busy = docs.some((d) => d.state === "queued" || d.state === "processing");
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, [busy, refresh]);

  // Select the first ready tender automatically
  useEffect(() => {
    const current = docs.find((d) => d.doc_id === active);
    if (!current || current.state !== "done") {
      const ready = docs.find((d) => d.state === "done");
      if (ready && ready.doc_id !== active) setActive(ready.doc_id);
    }
  }, [docs, active]);

  useEffect(() => { setEvidence(null); }, [active]);

  const ready = docs.filter((d) => d.state === "done");
  const current = ready.find((d) => d.doc_id === active);

  async function handleDelete(id) {
    if (!window.confirm("Delete this tender and its analyses?")) return;
    try { await api.remove(id); if (id === active) setActive(null); refresh(); }
    catch (e) { window.alert(e.message); }
  }

  return (
    <div className="app">
      <Sidebar docs={docs} active={active} onSelect={setActive}
               onUploaded={(id) => { setActive(id); refresh(); }} onDelete={handleDelete} />

      <main className="work">
        {backendDown && (
          <div className="banner">
            Can't reach the server. Start the backend with <code>python app.py</code>.
          </div>
        )}

        <header className="work-head">
          <div>
            <h1>{current ? current.name : "No tender selected"}</h1>
            {current && <p className="muted">{current.pages} pages · {current.tables ?? 0} tables detected{current.ocr_pages ? ` · ${current.ocr_pages} scanned pages read with OCR` : ""}</p>}
          </div>
          <nav className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id}
                      className={tab === t.id ? "tab on" : "tab"} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
        </header>

        {!current && tab !== "compare" ? (
          <div className="empty">
            <h2>Upload a tender to begin</h2>
            <p>Add a tender PDF in the left panel. It is read, split into passages and indexed, which takes a minute or two for a long document.</p>
          </div>
        ) : (
          <>
            {/* Panels stay mounted so chat history and results survive tab changes */}
            <section hidden={tab !== "ask"}><Ask key={`ask-${active}`} docId={active} onCite={setEvidence} /></section>
            <section hidden={tab !== "analysis"}><Analysis key={`an-${active}`} docId={active} visible={tab === "analysis"} onCite={setEvidence} /></section>
            <section hidden={tab !== "bid"}><BidCheck key={`bid-${active}`} docId={active} onCite={setEvidence} /></section>
          </>
        )}
        <section hidden={tab !== "compare"}><Compare docs={ready} /></section>

        <footer className="disclaimer">
          AI-assisted reading aid, not legal advice. Check every figure against the original tender before you bid.
        </footer>
      </main>

      <Evidence source={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}
