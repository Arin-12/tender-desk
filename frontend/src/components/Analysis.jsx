import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api.js";
import Answer, { Confidence } from "./Answer.jsx";

const TYPES = [
  { id: "key_info", label: "Key details" },
  { id: "summary", label: "Summary" },
  { id: "eligibility", label: "Eligibility" },
  { id: "risks", label: "Risks" },
  { id: "boq", label: "BOQ and pricing" },
];

const RISK = { low: "Low risk", medium: "Medium risk", high: "High risk" };

export default function Analysis({ docId, visible, onCite }) {
  const [type, setType] = useState("key_info");
  const [state, setState] = useState({}); // type -> {loading, data, error}

  const load = useCallback(async (t, refresh = false) => {
    setState((s) => ({ ...s, [t]: { loading: true } }));
    try {
      const data = await api.analyze(docId, t, refresh);
      setState((s) => ({ ...s, [t]: { data } }));
    } catch (e) {
      setState((s) => ({ ...s, [t]: { error: e.message } }));
    }
  }, [docId]);

  // Run on first view of each analysis (the server caches results on disk)
  useEffect(() => {
    if (visible && docId && !state[type]) load(type);
  }, [visible, type, docId, state, load]);

  const current = state[type] || {};
  const data = current.data;

  return (
    <div className="analysis">
      <div className="subbar">
        <div className="chips">
          {TYPES.map((t) => (
            <button key={t.id} className={type === t.id ? "chip on" : "chip"} onClick={() => setType(t.id)}>{t.label}</button>
          ))}
        </div>
        <div className="subbar-actions">
          <button className="btn" onClick={() => load(type, true)} disabled={current.loading}>Run again</button>
          <a className="btn" href={api.exportUrl(docId)}>Export PDF</a>
        </div>
      </div>

      {current.loading && <p className="muted pulse">Reading the tender and extracting this section. The first run takes up to a minute.</p>}
      {current.error && <p className="error">{current.error}</p>}

      {data && data.type === "text" && (
        <div className="panel">
          <Answer text={data.content} sources={data.sources} onCite={onCite} />
          <div className="a-meta"><Confidence value={data.confidence} /></div>
        </div>
      )}

      {data && data.type === "fields" && (
        <div className="panel">
          <p className="muted small">
            {data.coverage.found} of {data.coverage.total} items found. Select a page to read the source passage.
          </p>
          <table className="fields">
            <tbody>
              {data.fields.map((f) => (
                <tr key={f.key} className={f.found ? "" : "missing"}>
                  <th scope="row">
                    {f.label}
                    {f.risk && <span className={`risk ${f.risk}`}>{RISK[f.risk]}</span>}
                  </th>
                  <td>
                    {f.found ? (
                      <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{f.value}</ReactMarkdown></div>
                    ) : (
                      <span className="muted">Not found in the passages read. Check the tender manually.</span>
                    )}
                    {f.risk_reason && f.found && <p className="note">{f.risk_reason}</p>}
                  </td>
                  <td className="pages">
                    {f.refs.map((r) => {
                      const src = data.sources.find((s) => s.ref_id === r);
                      return src ? <button key={r} className="cite" onClick={() => onCite(src)}>p.{src.page}</button> : null;
                    })}
                    {f.confidence && <span className={`dot ${f.confidence.label}`} title={`${f.confidence.label} confidence (${Math.round(f.confidence.score * 100)}%)`} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
