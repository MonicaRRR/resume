import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  ExperienceAsk,
  LayoutIssue,
  OptimizationRun,
  PatchDiscussionResult,
  ResumePatch,
  ResumePatchOperation,
} from "../types";
import { AiAssistChat, type ChatMessage } from "./ui/AiAssistChat";
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


function displayValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return scrubDisplayText(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const lines = value.map((item) => displayValue(item).trim()).filter(Boolean);
    return lines.join("\n");
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
        const text = displayValue(record[key]).trim();
        if (text) chunks.push(text);
      }
    }
    if (chunks.length) return chunks.join("\n");
  }
  return "";
}


function operationIdsKey(operations: ResumePatchOperation[]): string {
  return operations.map((item) => item.id).join("\0");
}


function issuesById(run?: OptimizationRun | null): Map<string, LayoutIssue> {
  const map = new Map<string, LayoutIssue>();
  for (const issue of run?.baseline_layout_report?.issues ?? []) map.set(issue.id, issue);
  for (const issue of run?.layout_report?.issues ?? []) map.set(issue.id, issue);
  return map;
}


function averageDensity(report: { density_by_page: number[] } | null | undefined): string | null {
  const values = report?.density_by_page ?? [];
  if (!values.length) return null;
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return `${Math.round(average * 100)}%`;
}


export type DiscussMessage = ChatMessage;


export function PatchReview({
  patch,
  onApply,
  onChange,
  onDiscuss,
  onAnswerAsk,
  askBusy = false,
  busy = false,
  optimization,
}: {
  patch: ResumePatch;
  onApply: (acceptedIds: string[]) => void;
  onChange?: (patch: ResumePatch) => void;
  onDiscuss?: (operationId: string, message: string, history: DiscussMessage[]) => Promise<PatchDiscussionResult>;
  onAnswerAsk?: (ask: ExperienceAsk, answer: string) => Promise<void>;
  askBusy?: boolean;
  busy?: boolean;
  optimization?: OptimizationRun | null;
}) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [agreed, setAgreed] = useState(false);
  const [discussBusy, setDiscussBusy] = useState(false);
  const [discussError, setDiscussError] = useState("");
  const [histories, setHistories] = useState<Record<string, DiscussMessage[]>>({});
  const [operations, setOperations] = useState(patch.operations);
  const [pendingDraft, setPendingDraft] = useState<ResumePatchOperation | null>(null);

  const idsKey = useMemo(() => operationIdsKey(patch.operations), [patch.operations]);

  useEffect(() => {
    setOperations(patch.operations);
    setIndex(0);
    setSelected(new Set());
    setAgreed(false);
    setDiscussError("");
    setHistories({});
    setPendingDraft(null);
  }, [idsKey]);

  useEffect(() => {
    setOperations(patch.operations);
  }, [patch]);

  const total = operations.length;
  const safeIndex = total === 0 ? 0 : Math.min(index, total - 1);
  const current = operations[safeIndex];
  const history = current ? (histories[current.id] ?? []) : [];

  useEffect(() => {
    setPendingDraft(null);
    setDiscussError("");
  }, [current?.id]);

  const progressLabel = useMemo(
    () => (total ? `${safeIndex + 1} / ${total}` : "0 / 0"),
    [safeIndex, total],
  );
  const layoutCatalog = useMemo(() => issuesById(optimization), [optimization]);

  function acceptCurrent() {
    if (!current) return;
    setSelected((prev) => new Set(prev).add(current.id));
    if (safeIndex < total - 1) setIndex(safeIndex + 1);
  }

  function rejectCurrent() {
    if (!current) return;
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(current.id);
      return next;
    });
  }

  async function sendDiscuss(message: string) {
    if (!current || !onDiscuss || discussBusy) return;
    setDiscussBusy(true);
    setDiscussError("");
    try {
      const prior = histories[current.id] ?? [];
      const result = await onDiscuss(current.id, message, prior);
      setHistories((prev) => ({
        ...prev,
        [current.id]: [
          ...prior,
          { role: "user", content: message },
          { role: "assistant", content: result.reply || "已收到。" },
        ],
      }));
      setPendingDraft(result.proposes_change && result.draft_operation ? result.draft_operation : null);
    } catch (error) {
      setDiscussError(error instanceof Error ? error.message : "讨论未完成，请稍后重试");
    } finally {
      setDiscussBusy(false);
    }
  }

  function applyDraft() {
    if (!current || !pendingDraft) return;
    const nextOperations = operations.map((item) => (item.id === current.id ? pendingDraft : item));
    setOperations(nextOperations);
    onChange?.({ ...patch, operations: nextOperations });
    setPendingDraft(null);
    setHistories((prev) => ({
      ...prev,
      [current.id]: [
        ...(prev[current.id] ?? []),
        { role: "assistant", content: "已采用本轮改写，建议卡片已更新。若还要调整可继续讨论。" },
      ],
    }));
  }

  const experienceAsks = patch.experience_asks ?? [];

  if (!current && experienceAsks.length === 0) {
    return (
      <section className="patch-review">
        <div className="panel-heading">
          <div><span className="panel-index">04</span><h2>逐项同意建议</h2></div>
        </div>
        <p className="panel-note">当前没有可审阅的建议。</p>
      </section>
    );
  }

  const asksBlock = experienceAsks.length > 0 && onAnswerAsk ? (
    <ExperienceAskPanel asks={experienceAsks} busy={askBusy || busy} onAnswer={onAnswerAsk} />
  ) : experienceAsks.length > 0 ? (
    <ExperienceAskPanel asks={experienceAsks} busy={false} />
  ) : null;

  if (!current) {
    return (
      <section className="patch-review">
        <div className="panel-heading">
          <div><span className="panel-index">04</span><h2>补充项目线索</h2></div>
        </div>
        <p className="panel-note">AI 判断当前项目经历相对岗位偏少，先确认你是否还有可补充的相关经历；回答会记入事实库。</p>
        {asksBlock}
      </section>
    );
  }

  const before = displayValue(current.before);
  const after = displayValue(current.after);
  const accepted = selected.has(current.id);
  const draftAfter = pendingDraft ? displayValue(pendingDraft.after) : "";
  const layoutIssues = (current.layout_issue_ids ?? [])
    .map((issueId) => layoutCatalog.get(issueId))
    .filter((issue): issue is LayoutIssue => Boolean(issue));
  const baseline = optimization?.baseline_layout_report ?? null;
  const finalLayout = optimization?.layout_report ?? null;
  const quality = optimization?.quality ?? null;
  const showStoppedAlert = Boolean(
    optimization
    && optimization.status === "ready_for_user"
    && quality
    && !quality.passed,
  );

  const draftActions: ReactNode = pendingDraft ? (
    <div className="ai-assist-draft">
      <p className="ai-assist-draft-label">AI 提出的改写（未写入，需你确认）</p>
      <div className="diff-after">
        <DiffMarkdown text={draftAfter} empty="（空）" />
      </div>
      {pendingDraft.reason ? <small>{pendingDraft.reason}</small> : null}
      <div className="ai-assist-draft-actions">
        <button type="button" className="primary-button" onClick={applyDraft} disabled={busy || discussBusy}>
          采用此改写
        </button>
        <button type="button" className="secondary-button" onClick={() => setPendingDraft(null)} disabled={discussBusy}>
          不用这个改写
        </button>
      </div>
    </div>
  ) : null;

  return (
    <section className="patch-review" aria-labelledby="patch-title">
      <div className="panel-heading">
        <div><span className="panel-index">04</span><h2 id="patch-title">逐项同意建议</h2></div>
        <span>
          <span>{selected.size}/{total} 已同意</span>
          <span aria-hidden="true"> · </span>
          <span>{progressLabel}</span>
        </span>
      </div>
      <p className="panel-note">
        一次只看一条。右下角可与 AI 讨论；AI 可以反驳，只有你点「采用此改写」才会更新本条建议。
        <strong>默认全部不生效</strong>，只有你同意的条目才会写入新版本。
      </p>

      {optimization && (
        <div className="optimization-evidence-summary">
          {showStoppedAlert && (
            <p className="optimization-stopped-alert" role="alert">
              已达到自动返工上限
              {quality?.reasons?.length ? `：${quality.reasons.join("；")}` : "，仍可逐条审阅当前建议。"}
            </p>
          )}
          <ul>
            {quality && (
              <li>JD 覆盖 {Math.round(quality.jd_coverage * 100)}%</li>
            )}
            {finalLayout && <li>实际 {finalLayout.page_count} 页</li>}
            {baseline && finalLayout && baseline.page_count !== finalLayout.page_count && (
              <li>页数 {baseline.page_count} → {finalLayout.page_count}</li>
            )}
            {averageDensity(baseline) && averageDensity(finalLayout) && (
              <li>版面密度 {averageDensity(baseline)} → {averageDensity(finalLayout)}</li>
            )}
            {quality && <li>表达 {quality.expression_score} 分</li>}
          </ul>
          <small>本次简历与该 JD 的内部优化指标，不代表录取概率</small>
        </div>
      )}

      {asksBlock}

      <article className={`patch-card single ${accepted ? "selected" : ""}`}>
        <div className="patch-stepper">
          <button type="button" className="text-button" disabled={safeIndex === 0} onClick={() => setIndex((value) => Math.max(0, value - 1))}>上一项</button>
          <strong>建议 {progressLabel}</strong>
          <button type="button" className="text-button" disabled={safeIndex >= total - 1} onClick={() => setIndex((value) => Math.min(total - 1, value + 1))}>下一项</button>
        </div>
        <div className="patch-content">
          <div className="patch-meta">
            <span>{current.reason}</span>
            <span className={`risk-${current.risk}`}>{current.risk === "low" ? "低风险" : current.risk === "medium" ? "需确认" : "高风险"}</span>
          </div>
          {current.expected_layout_benefit ? (
            <p className="layout-benefit">{current.expected_layout_benefit}</p>
          ) : null}
          {layoutIssues.length > 0 && (
            <ul className="layout-issue-list">
              {layoutIssues.map((issue) => (
                <li key={issue.id}>{issue.message}</li>
              ))}
            </ul>
          )}
          <p className="diff-path"><code>{current.path}</code></p>
          <div className="diff-before" aria-label="修改前">
            <span className="diff-label">修改前</span>
            <DiffMarkdown text={before} empty="（空 / 建议移出投递版）" />
          </div>
          <div className="diff-after" aria-label="修改后">
            <span className="diff-label">修改后</span>
            <DiffMarkdown text={after} empty="（空）" />
          </div>
          <small>岗位依据 {current.jd_requirement_ids.length} 条 · 事实依据 {current.source_fact_ids.length} 条</small>
        </div>
        <div className="patch-actions">
          <button type="button" className={accepted ? "primary-button" : "secondary-button"} onClick={acceptCurrent}>同意这项</button>
          <button type="button" className="secondary-button" onClick={rejectCurrent} disabled={!accepted}>取消同意</button>
        </div>
      </article>

      <label className="privacy-confirm">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(event) => setAgreed(event.target.checked)}
          aria-label="我同意仅应用已勾选的建议"
        />
        <span><strong>我已阅读并同意</strong>仅将已点「同意这项」的建议应用到新版本；未同意内容保持不变。</span>
      </label>
      <button
        className="primary-button"
        type="button"
        disabled={selected.size === 0 || !agreed || busy || discussBusy}
        onClick={() => onApply([...selected])}
      >
        应用已同意的修改（{selected.size}）
      </button>

      {onDiscuss ? (
        <AiAssistChat
          disabled={busy}
          busy={discussBusy}
          title="与 AI 讨论"
          contextLabel={`正在讨论建议 ${progressLabel} · ${current.path}`}
          messages={history}
          error={discussError}
          onSend={sendDiscuss}
          emptyHint="可以说你想怎么改；AI 可以同意、反驳或追问。只有你确认「采用此改写」后才会更新本条建议。"
          busyLabel="AI 正在思考…"
          footer={draftActions}
        />
      ) : null}
    </section>
  );
}


function ExperienceAskPanel({
  asks,
  busy,
  onAnswer,
}: {
  asks: ExperienceAsk[];
  busy: boolean;
  onAnswer?: (ask: ExperienceAsk, answer: string) => Promise<void>;
}) {
  const [activeId, setActiveId] = useState(asks[0]?.id ?? "");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const active = asks.find((item) => item.id === activeId) ?? asks[0];

  useEffect(() => {
    if (!asks.some((item) => item.id === activeId)) {
      setActiveId(asks[0]?.id ?? "");
    }
  }, [asks, activeId]);

  if (!active) return null;

  const guidanceLines = active.guidance
    .split(/\n|·/)
    .map((line) => line.replace(/^[\s•\-]+/, "").trim())
    .filter(Boolean);

  async function submit() {
    if (!onAnswer) return;
    const text = (drafts[active.id] ?? "").trim();
    if (!text) {
      setError("请先写一两句相关经历，或点跳过");
      return;
    }
    setError("");
    await onAnswer(active, text);
    setDrafts((prev) => ({ ...prev, [active.id]: "" }));
  }

  return (
    <section className="experience-ask-panel" aria-label="项目补充追问">
      <div className="panel-heading">
        <div><strong>项目可能偏少</strong></div>
        <span>{asks.length} 条追问</span>
      </div>
      <p className="panel-note">AI 不会替你编项目；若你确实还有相关经历，按提示回忆后写下来，会记入事实库，便于下一轮适配。</p>
      {asks.length > 1 && (
        <div className="patch-stepper">
          {asks.map((ask, index) => (
            <button
              key={ask.id}
              type="button"
              className={ask.id === active.id ? "text-button active" : "text-button"}
              onClick={() => setActiveId(ask.id)}
            >
              追问 {index + 1}
            </button>
          ))}
        </div>
      )}
      <article className="question-card experience-ask-card">
        <span>{active.topic}</span>
        <h3>{active.question}</h3>
        {guidanceLines.length > 0 && (
          <ul className="ask-guidance">
            {guidanceLines.map((line) => <li key={line}>{line}</li>)}
          </ul>
        )}
        {active.jd_keywords.length > 0 && (
          <p className="ask-keywords">可对齐关键词：{active.jd_keywords.join("、")}</p>
        )}
        {onAnswer ? (
          <>
            <textarea
              aria-label="补充相关项目"
              rows={4}
              value={drafts[active.id] ?? ""}
              onChange={(event) => setDrafts((prev) => ({ ...prev, [active.id]: event.target.value }))}
              placeholder="例：大三课程《XX》做过一个…；或参加过黑客松做了…；没有可直接跳过"
            />
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="button-row">
              <button type="button" className="primary-button" disabled={busy} onClick={() => void submit()}>
                保存为事实
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => void onAnswer(active, "")}
              >
                暂时没有 / 跳过
              </button>
            </div>
          </>
        ) : null}
      </article>
    </section>
  );
}
