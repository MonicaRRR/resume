import type { ReactNode } from "react";


function normalizeBulletLine(line: string): string {
  return line.replace(/^\s*(?:[-*•+]|\d+[.)、])\s+/, "").trim();
}


/** Render resume before/after text as readable markdown-ish blocks (lists + paragraphs). */
export function DiffMarkdown({ text, empty = "（空）" }: { text: string; empty?: string }): ReactNode {
  const raw = text.replace(/\r\n/g, "\n").trim();
  if (!raw) return <p className="diff-md-empty">{empty}</p>;

  const lines = raw.split("\n").map((line) => line.trimEnd());
  const nonEmpty = lines.map((line) => line.trim()).filter(Boolean);
  const bulletLike = nonEmpty.filter((line) => /^(?:[-*•+]|\d+[.)、])\s+/.test(line));
  const preferList = nonEmpty.length > 1 && (bulletLike.length >= Math.ceil(nonEmpty.length * 0.5) || nonEmpty.length >= 2);

  if (preferList) {
    return (
      <ul className="diff-md-list">
        {nonEmpty.map((line, index) => (
          <li key={`${index}-${line.slice(0, 12)}`}>{normalizeBulletLine(line)}</li>
        ))}
      </ul>
    );
  }

  return (
    <div className="diff-md-prose">
      {nonEmpty.map((line, index) => (
        <p key={`${index}-${line.slice(0, 12)}`}>{line}</p>
      ))}
    </div>
  );
}
