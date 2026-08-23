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
          return <article key={requirement.id}>
            <div><strong>{requirement.text}</strong>{item && <span className={`match-${item.status}`}>{item.status}</span>}</div>
            <blockquote>“{requirement.evidence_quote}”</blockquote>
            {item?.excerpts.map((excerpt, index) => <p key={index}>证据：{excerpt}</p>)}
          </article>;
        })}
      </div>
    </section>
  );
}
