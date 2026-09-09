import type { JobAnalysis, MatchReport } from "../types";


export function JobAnalysisPanel({ analysis, match }: { analysis: JobAnalysis; match?: MatchReport | null }) {
  const matchById = new Map(match?.items.map((item) => [item.requirement_id, item]));
  return (
    <section className="analysis-panel">
      <div className="panel-heading">
        <div><span className="panel-index">02</span><h2>岗位证据地图</h2></div>
        {match && <strong className="coverage-number">{Math.round(match.coverage * 100)}%</strong>}
      </div>
      <div className="analysis-meta"><span>{analysis.role_title || "目标岗位"}</span><span>{analysis.seniority || "级别待判断"}</span></div>
      <div className="keyword-row">{analysis.keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}</div>
      <div className="requirement-list">
        {analysis.requirements.map((requirement) => {
          const item = matchById.get(requirement.id);
          return <article key={requirement.id} className={requirement.inferred ? "requirement-inferred" : undefined}>
            <div>
              <strong>{requirement.text}</strong>
              {requirement.inferred && <span className="inferred-tag">推断 · 原文未精确定位</span>}
              {item && <span className={`match-${item.status}`}>{item.status}</span>}
            </div>
            <blockquote>“{requirement.evidence_quote}”</blockquote>
            {item?.reason && (
              <p className={`match-reason match-reason-${item.status}`}>
                {item.status === "证据较弱" ? "为何较弱：" : item.status === "没有证据" ? "缺口说明：" : item.status === "软性要求" ? "说明：" : "匹配说明："}
                {item.reason}
              </p>
            )}
            {item?.excerpts.map((excerpt, index) => (
              <p key={index}>{excerpt.startsWith("软性要求") ? excerpt : `证据：${excerpt}`}</p>
            ))}
          </article>;
        })}
      </div>
    </section>
  );
}
