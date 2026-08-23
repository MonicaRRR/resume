import { useState } from "react";

import type { ResumePatch } from "../types";


function displayValue(value: unknown): string {
  if (value && typeof value === "object" && "value" in value) {
    return String((value as { value: unknown }).value ?? "");
  }
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}


export function PatchReview({ patch, onApply, busy = false }: {
  patch: ResumePatch;
  onApply: (acceptedIds: string[]) => void;
  busy?: boolean;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toggle = (id: string) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <section className="patch-review" aria-labelledby="patch-title">
      <div className="panel-heading">
        <div><span className="panel-index">04</span><h2 id="patch-title">逐项审阅 AI 修改</h2></div>
        <span>{selected.size}/{patch.operations.length} 已选择</span>
      </div>
      <p className="panel-note">AI 的建议默认不生效。勾选后才会生成新的简历版本。</p>
      <div className="patch-list">
        {patch.operations.map((operation) => {
          const before = displayValue(operation.before);
          const after = displayValue(operation.after);
          return (
            <label className={`patch-card ${selected.has(operation.id) ? "selected" : ""}`} key={operation.id}>
              <input type="checkbox" checked={selected.has(operation.id)} onChange={() => toggle(operation.id)} aria-label={`接受修改：${after}`} />
              <div className="patch-content">
                <div className="patch-meta"><span>{operation.reason}</span><span className={`risk-${operation.risk}`}>{operation.risk === "low" ? "低风险" : operation.risk === "medium" ? "需确认" : "高风险"}</span></div>
                <p className="diff-before">− {before || "（空）"}</p>
                <p className="diff-after">＋ {after || "（空）"}</p>
                <small>岗位依据 {operation.jd_requirement_ids.length} 条 · 事实依据 {operation.source_fact_ids.length} 条</small>
              </div>
            </label>
          );
        })}
      </div>
      <button className="primary-button" type="button" disabled={selected.size === 0 || busy} onClick={() => onApply([...selected])}>应用已选修改</button>
    </section>
  );
}
