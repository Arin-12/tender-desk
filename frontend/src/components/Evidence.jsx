import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Right-hand panel that shows the source passage behind a citation. */
export default function Evidence({ source, onClose }) {
  if (!source) {
    return (
      <aside className="evidence">
        <p className="muted">Select a page reference such as <span className="cite static">p.12</span> to read the passage the answer came from.</p>
      </aside>
    );
  }
  const similarity = typeof source.similarity === "number" ? Math.round(source.similarity * 100) : null;
  return (
    <aside className="evidence open">
      <button className="icon-btn close" onClick={onClose} aria-label="Close source">×</button>
      <div className="titleblock">
        <div><span>Page</span><strong>{source.page}</strong></div>
        <div><span>Section</span><strong>{source.section || "Unknown"}</strong></div>
        <div><span>Type</span><strong>{source.chunk_type === "table" ? "Table" : "Text"}</strong></div>
        {similarity !== null && similarity > 0 && <div><span>Match</span><strong>{similarity}%</strong></div>}
      </div>
      {source.chunk_type === "table" ? (
        <div className="md src-table"><ReactMarkdown remarkPlugins={[remarkGfm]}>{source.text}</ReactMarkdown></div>
      ) : (
        <p className="src-text">{source.text}</p>
      )}
    </aside>
  );
}
