import { useEffect, useRef } from "react";

import { annotationLocationLabel, annotationTargetForPath } from "../lib/annotationTarget";
import type { ApplicationType, ResumeDocument, ResumePatchOperation } from "../types";
import { ResumePreview } from "./ResumePreview";
import { DiffMarkdown } from "./ui/DiffMarkdown";


const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;


function scrubDisplayText(text: string): string {
  return text
    .replace(UUID_RE, "")
    .replace(/[（\[]\s*[）\]]/g, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}


export function displayPatchValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return scrubDisplayText(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => displayPatchValue(item).trim()).filter(Boolean).join("\n");
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if ("value" in record) return scrubDisplayText(String(record.value ?? ""));
    const chunks: string[] = [];
    const titleBits = [record.company, record.name, record.institution, record.title, record.role, record.degree, record.field]
      .map((item) => (typeof item === "string" ? scrubDisplayText(item) : ""))
      .filter(Boolean);
    if (titleBits.length) chunks.push(titleBits.join(" · "));
    for (const key of ["bullets", "items", "highlights", "detail"] as const) {
      if (key in record) {
        const text = displayPatchValue(record[key]).trim();
        if (text) chunks.push(text);
      }
    }
    if (chunks.length) return chunks.join("\n");
  }
  return "";
}


function snippet(text: string, max = 72): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= max) return compact;
  return `${compact.slice(0, max)}…`;
}


export function AnnotatedResumePreview({
  projectId,
  applicationType,
  resume,
  templateId,
  operations,
  selected,
  activeOperation,
  onSelectOperation,
  onAccept,
  onReject,
}: {
  projectId: string;
  applicationType: ApplicationType;
  resume: ResumeDocument;
  templateId: string;
  operations: ResumePatchOperation[];
  selected: Set<string>;
  activeOperation: ResumePatchOperation | null;
  onSelectOperation: (operationId: string) => void;
  onAccept: (operationId: string) => void;
  onReject: (operationId: string) => void;
}) {
  const boardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!activeOperation || !boardRef.current) return;
    const card = Array.from(boardRef.current.querySelectorAll<HTMLElement>("[data-annotation-id]"))
      .find((node) => node.dataset.annotationId === activeOperation.id);
    if (typeof card?.scrollIntoView === "function") {
      card.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
  }, [activeOperation?.id]);

  return (
    <section ref={boardRef} className="annotation-board" aria-label="简历批注审阅">
      <div className="annotation-board-resume">
        <p className="annotation-board-hint">
          左侧预览与导出 Word/PDF 同源。右侧批注编号对应修改位置；点「同意」后才会生效。
        </p>
        <ResumePreview
          projectId={projectId}
          resume={resume}
          templateId={templateId}
          applicationType={applicationType}
          variant="annotation"
        />
      </div>
      <aside className="annotation-rail" aria-label="修改批注">
        <header className="annotation-rail-head">
          <strong>批注</strong>
          <span>{operations.length} 条</span>
        </header>
        {operations.map((operation, index) => {
          const isActive = activeOperation?.id === operation.id;
          const isAccepted = selected.has(operation.id);
          const afterText = displayPatchValue(operation.after);
          const beforeText = displayPatchValue(operation.before);
          const location = annotationLocationLabel(annotationTargetForPath(operation.path), resume);
          const tone = isActive ? "active" : isAccepted ? "accepted" : operation.source_fact_ids.length === 0 ? "gap" : "pending";
          return (
            <article
              key={operation.id}
              className={`annotation-card tone-${tone}${isActive ? " is-active" : ""}`}
              data-annotation-for={annotationTargetForPath(operation.path)}
              data-annotation-id={operation.id}
            >
              <button
                type="button"
                className="annotation-card-hit"
                onClick={() => onSelectOperation(operation.id)}
                aria-pressed={isActive}
              >
                <span className="annotation-card-index">
                  <span className="annotation-card-number">{index + 1}</span>
                  <span className="annotation-card-location">{location}</span>
                </span>
                <strong>{operation.reason || "修改建议"}</strong>
                <small>{snippet(afterText || beforeText || location)}</small>
              </button>
              {isActive && (
                <div className="annotation-card-body">
                  {operation.source_fact_ids.length === 0 && (
                    <p className="fact-gap-warning" role="status">未绑定事实依据，请重点核对。</p>
                  )}
                  <div className="diff-before" aria-label="修改前">
                    <span className="diff-label">修改前</span>
                    <DiffMarkdown text={beforeText} empty="（空 / 建议移出投递版）" />
                  </div>
                  <div className="diff-after" aria-label="修改后">
                    <span className="diff-label">修改后</span>
                    <DiffMarkdown text={afterText} empty="（空）" />
                  </div>
                  <div className="patch-actions">
                    <button
                      type="button"
                      className={isAccepted ? "primary-button" : "secondary-button"}
                      onClick={() => onAccept(operation.id)}
                    >
                      同意
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onReject(operation.id)}
                      disabled={!isAccepted}
                    >
                      取消同意
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </aside>
    </section>
  );
}
