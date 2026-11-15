import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api.js";

const pages = (p) => (p && p.length ? `p.${p.join(", ")}` : "");

export default function Compare({ docs }) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [onlyDiff, setOnlyDiff] = useState(true);
  const [state, setState] = useState({});

  async function run() {
    setState({ loading: true });
    try { setState({ data: await api.compare(a, b) }); }
    catch (e) { setState({ error: e.message }); }
  }

  if (docs.length < 2) {
    return (
      <div className="empty">
        <h2>Add a second tender to compare</h2>
        <p>Comparison needs two indexed tenders. They can be two different tenders or two revisions of the same one.</p>
      </div>
    );
  }

  const name = (id) => docs.find((d) => d.doc_id === id)?.name || "";
  const data = state.data;
  const rows = data ? data.rows.filter((r) => !onlyDiff || !r.same) : [];
  let lastGroup = "";

  return (
    <div className="compare">
      <div className="pick panel">
        <label className="field"><span>Tender A</span>
          <select value={a} onChange={(e) => setA(e.target.value)}>
            <option value="">Choose…</option>
            {docs.map((d) => <option key={d.doc_id} value={d.doc_id}>{d.name}</option>)}
          </select>
        </label>
        <label className="field"><span>Tender B</span>
          <select value={b} onChange={(e) => setB(e.target.value)}>
            <option value="">Choose…</option>
            {docs.map((d) => <option key={d.doc_id} value={d.doc_id}>{d.name}</option>)}
          </select>
        </label>
        <button className="btn primary" onClick={run} disabled={!a || !b || a === b || state.loading}>
          {state.loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {state.loading && <p className="muted pulse">Extracting both tenders. The first comparison can take a few minutes.</p>}
      {state.error && <p className="error">{state.error}</p>}

      {data && (
        <div className="panel">
          {data.summary && (
            <>
              <h2>What differs</h2>
              <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]}>{data.summary}</ReactMarkdown></div>
            </>
          )}
          <label className="check">
            <input type="checkbox" checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} />
            Show only differing items
          </label>
          <table className="fields compare-table">
            <thead>
              <tr><th></th><th>{name(a)}</th><th>{name(b)}</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const header = r.group !== lastGroup ? <tr key={`g${i}`} className="group"><td colSpan={3}>{r.group}</td></tr> : null;
                lastGroup = r.group;
                return [header,
                  <tr key={i} className={r.same ? "" : "diff"}>
                    <th scope="row">{r.label}</th>
                    <td>{r.a} <span className="muted small">{pages(r.pages_a)}</span></td>
                    <td>{r.b} <span className="muted small">{pages(r.pages_b)}</span></td>
                  </tr>];
              })}
            </tbody>
          </table>
          <p className="muted small">{data.note}</p>
        </div>
      )}
    </div>
  );
}
