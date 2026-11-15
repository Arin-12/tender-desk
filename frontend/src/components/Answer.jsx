import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Markdown with numbered citations [n] turned into clickable page chips. */
export default function Answer({ text, sources = [], onCite }) {
  const md = useMemo(() => (text || "").replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)"), [text]);
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href && href.startsWith("#cite-")) {
              const n = Number(href.slice(6));
              const src = sources.find((s) => s.ref_id === n);
              if (!src) return null;
              return (
                <button className="cite" onClick={() => onCite(src)} title={`Show page ${src.page}`}>
                  p.{src.page}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
          },
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}

export function Confidence({ value }) {
  if (!value) return null;
  const word = { high: "High", medium: "Medium", low: "Low" }[value.label];
  return (
    <span className={`conf ${value.label}`}
          title="Combines how closely the cited passages match the question with the share of valid citations. A guide, not a guarantee.">
      {word} confidence · {Math.round(value.score * 100)}%
    </span>
  );
}
