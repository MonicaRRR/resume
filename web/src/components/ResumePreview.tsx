import { useEffect } from "react";

import { estimateResumeUnits, isOnePageApplication } from "../resume";
import { TemplateResume } from "../templates/registry";
import type { ApplicationType, ResumeDocument } from "../types";


export function ResumePreview({ resume, templateId, applicationType, onOverflowChange }: {
  resume: ResumeDocument;
  templateId: string;
  applicationType: ApplicationType;
  onOverflowChange?: (overflow: boolean) => void;
}) {
  const units = estimateResumeUnits(resume);
  const onePage = isOnePageApplication(applicationType);
  const overflow = onePage && units > 1700;
  useEffect(() => onOverflowChange?.(overflow), [onOverflowChange, overflow]);

  return (
    <section className={`preview-panel ${onePage ? "compact-preview" : ""}`} aria-label="简历预览">
      <div className="preview-toolbar">
        <div>
          <strong>{onePage ? "一页紧凑预览" : "自然分页预览"}</strong>
          <span>{onePage ? `容量估算 ${Math.min(Math.round(units / 17), 999)}%` : "社招不限制页数"}</span>
        </div>
        <button type="button" disabled={overflow} onClick={() => window.print()}>打印或保存 PDF</button>
      </div>
      {overflow && (
        <div className="overflow-warning" role="alert">
          <strong>当前内容超过一页</strong>
          <span>内容已完整保留。请精简重复表述或降低次要信息优先级后再导出。</span>
        </div>
      )}
      <div className="paper-stage">
        <TemplateResume resume={resume} templateId={templateId} />
      </div>
    </section>
  );
}
