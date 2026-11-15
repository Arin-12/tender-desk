import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Answer, { Confidence } from "./Answer.jsx";

const SUGGESTIONS = [
  "What is the EMD and how must it be paid?",
  "What are the liquidated damages for delay?",
  "What experience does a bidder need?",
];

function Highlight({ text, query }) {
  const words = query.split(/\s+/).filter((w) => w.length > 1).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return text;
  const parts = text.split(new RegExp(`(${words.join("|")})`, "gi"));
  return parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : p));
}

export default function Ask({ docId, onCite }) {
  const [mode, setMode] = useState("ask");
  const [k, setK] = useState(6);
  const [input, setInput] = useState("");
  const [items, setItems] = useState([]);
  const end = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items]);

  async function submit(event, preset) {
    event?.preventDefault();
    const q = (preset ?? input).trim();
    if (!q || !docId) return;
    setInput("");
    const id = Date.now();
    setItems((list) => [...list, { id, q, mode, loading: true }]);
    try {
      const res = mode === "ask" ? await api.chat(docId, q, k) : await api.search(docId, q);
      setItems((list) => list.map((it) => (it.id === id ? { ...it, loading: false, res } : it)));
    } catch (e) {
      setItems((list) => list.map((it) => (it.id === id ? { ...it, loading: false, error: e.message } : it)));
    }
  }

  return (
    <div className="ask">
      <div className="thread">
        {items.length === 0 && (
          <div className="starter">
            <p>Ask anything about this tender. Answers cite the page they came from.</p>
            <div className="chips">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => { setMode("ask"); submit(null, s); }}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {items.map((it) => (
          <article key={it.id} className="turn">
            <p className="q">{it.q}</p>
            {it.loading && <p className="muted pulse">{it.mode === "ask" ? "Reading the tender…" : "Searching…"}</p>}
            {it.error && <p className="error">{it.error}</p>}
            {it.res && it.mode === "ask" && (
              <div className="a">
                <Answer text={it.res.answer} sources={it.res.sources} onCite={onCite} />
                <div className="a-meta">
                  <Confidence value={it.res.confidence} />
                  {it.res.citations?.total > 0 && it.res.citations.valid < it.res.citations.total && (
                    <span className="warn-text">Some citations the AI gave were invalid and were removed.</span>
                  )}
                  {it.res.citations?.total === 0 && <span className="warn-text">No citations given. Treat this answer with care.</span>}
                </div>
              </div>
            )}
            {it.res && it.mode === "search" && (
              <div className="hits">
                {it.res.hits.length === 0 && <p className="muted">No passages contain those words.</p>}
                {it.res.hits.map((h, i) => (
                  <button key={i} className="hit" onClick={() => onCite({ ...h, chunk_type: h.chunk_type })}>
                    <span className="hit-page">p.{h.page}</span>
                    <span className="hit-text"><Highlight text={h.text.slice(0, 280)} query={it.q} /></span>
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}
        <div ref={end} />
      </div>

      <form className="composer" onSubmit={submit}>
        <div className="seg" role="group" aria-label="Mode">
          <button type="button" className={mode === "ask" ? "on" : ""} onClick={() => setMode("ask")}>Ask AI</button>
          <button type="button" className={mode === "search" ? "on" : ""} onClick={() => setMode("search")}>Find words</button>
        </div>
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder={mode === "ask" ? "Ask about eligibility, dates, penalties…" : "Find exact words or clause numbers"}
               aria-label="Your question" />
        {mode === "ask" && (
          <label className="k" title="How many passages the AI reads for each answer">
            Passages
            <select value={k} onChange={(e) => setK(Number(e.target.value))}>
              {[4, 6, 8, 12].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        )}
        <button className="btn primary" type="submit">{mode === "ask" ? "Ask" : "Search"}</button>
      </form>
    </div>
  );
}
