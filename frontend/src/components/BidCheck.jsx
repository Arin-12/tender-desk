import { useState } from "react";
import { api } from "../api.js";

const FIELDS = [
  { key: "company", label: "Company name and type", rows: 1, ph: "Rai Constructions, proprietorship" },
  { key: "turnover", label: "Annual turnover", rows: 3, ph: "FY 2022-23: 4.2 Cr\nFY 2023-24: 5.1 Cr\nFY 2024-25: 4.8 Cr" },
  { key: "net_worth", label: "Net worth and solvency", rows: 2, ph: "Net worth 2.1 Cr (CA certificate). Solvency certificate from SBI for 1.5 Cr." },
  { key: "similar_works", label: "Completed similar works", rows: 5, ph: "Name, value, completion year, client. One work per line." },
  { key: "registrations", label: "Registrations and licences", rows: 2, ph: "Class II contractor, GST, PAN, EPF, ESI, labour licence" },
  { key: "equipment", label: "Equipment owned or leased", rows: 3, ph: "1 concrete mixer, 2 vibrators, 1 JCB" },
  { key: "personnel", label: "Key personnel", rows: 2, ph: "1 civil engineer (B.E., 8 years experience)" },
  { key: "other", label: "Other certificates or notes", rows: 2, ph: "" },
];

const STATUS = { met: "Met", not_met: "Not met", unclear: "Unclear", to_prepare: "To prepare", not_applicable: "Not applicable" };
const VERDICT = {
  likely_eligible: "Every criterion looks met. Verify the documents before bidding.",
  needs_verification: "Some criteria cannot be decided from your profile. Add the missing information.",
  not_eligible_as_stated: "At least one criterion is not met by the profile as written.",
};

function loadProfile() {
  try { return JSON.parse(localStorage.getItem("tender-desk-profile") || "{}"); } catch { return {}; }
}

export default function BidCheck({ docId, onCite }) {
  const [profile, setProfile] = useState(loadProfile);
  const [state, setState] = useState({});

  function update(key, value) {
    const next = { ...profile, [key]: value };
    setProfile(next);
    try { localStorage.setItem("tender-desk-profile", JSON.stringify(next)); } catch { /* storage unavailable */ }
  }

  async function run() {
    setState({ loading: true });
    try { setState({ data: await api.checkBid(docId, profile) }); }
    catch (e) { setState({ error: e.message }); }
  }

  const data = state.data;
  return (
    <div className="bid">
      <div className="bid-form panel">
        <h2>Contractor profile</h2>
        <p className="muted small">Describe your firm. Each tender criterion is checked against this text. It is saved in this browser only.</p>
        {FIELDS.map((f) => (
          <label key={f.key} className="field">
            <span>{f.label}</span>
            <textarea rows={f.rows} value={profile[f.key] || ""} placeholder={f.ph} onChange={(e) => update(f.key, e.target.value)} />
          </label>
        ))}
        <button className="btn primary" onClick={run} disabled={state.loading}>
          {state.loading ? "Checking…" : "Check eligibility"}
        </button>
        {state.error && <p className="error">{state.error}</p>}
      </div>

      <div className="bid-result">
        {!data && !state.loading && (
          <div className="empty small-empty">
            <h2>See where you stand</h2>
            <p>Fill in your profile and check it against this tender's eligibility criteria. You get a Met, Not met or Unclear result for each one, with the evidence and what to prepare.</p>
          </div>
        )}
        {state.loading && <p className="muted pulse">Reading the criteria and comparing them with your profile…</p>}

        {data && (
          <>
            <div className={`verdict ${data.summary.verdict}`}>
              <div className="counts">
                <span><b>{data.summary.met}</b> met</span>
                <span><b>{data.summary.unclear}</b> unclear</span>
                <span><b>{data.summary.not_met}</b> not met</span>
                <span className="muted">of {data.summary.judged ?? data.summary.total} judged</span>
                {data.summary.to_prepare > 0 && <span className="muted"><b>{data.summary.to_prepare}</b> to prepare with the bid</span>}
                {data.summary.not_applicable > 0 && <span className="muted"><b>{data.summary.not_applicable}</b> not applicable</span>}
              </div>
              <p>{VERDICT[data.summary.verdict]}</p>
            </div>

            <ul className="criteria">
              {data.criteria.map((c) => (
                <li key={c.id} className={`crit ${c.status}`}>
                  <div className="crit-head">
                    <span className={`status ${c.status}`}>{STATUS[c.status]}</span>
                    <strong>{c.criterion}</strong>
                    {c.refs.map((r) => {
                      const src = data.sources.find((s) => s.ref_id === r);
                      return src ? <button key={r} className="cite" onClick={() => onCite(src)}>p.{src.page}</button> : null;
                    })}
                  </div>
                  <p className="req">{c.requirement}</p>
                  {c.applies_to && c.applies_to !== "all bidders" && <p className="muted small">Applies to: {c.applies_to}</p>}
                  <p className="evid"><span className="muted">Your profile: </span>{c.evidence}</p>
                  {c.action && <p className="action"><span className="muted">To do: </span>{c.action}</p>}
                </li>
              ))}
            </ul>
            <p className="muted small">{data.disclaimer}</p>
          </>
        )}
      </div>
    </div>
  );
}
