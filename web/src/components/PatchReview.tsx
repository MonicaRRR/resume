import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import type {
  ApplicationType,
  ExperienceAsk,
  OptimizationRun,
  PatchDiscussionResult,
  ResumeDocument,
  ResumePatch,
  ResumePatchOperation,
} from "../types";
import { AnnotatedResumePreview, displayPatchValue } from "./AnnotatedResumePreview";
import { AiAssistChat, type ChatMessage } from "./ui/AiAssistChat";
import { DiffMarkdown } from "./ui/DiffMarkdown";


function operationIdsKey(operations: ResumePatchOperation[]): string {
  return operations.map((item) => item.id).join("\0");
}


export type DiscussMessage = ChatMessage;


export function PatchReview({
  patch,
  resume,
  templateId,
  projectId,
  applicationType,
  onApply,
  onChange,
  onDiscuss,
  onAnswerAsk,
  askBusy = false,
  busy = false,
  optimization,
  previewHost = null,
}: {
  patch: ResumePatch;
  resume: ResumeDocument;
  templateId: string;
  projectId: string;
  applicationType: ApplicationType;
  onApply: (acceptedIds: string[]) => void;
  onChange?: (patch: ResumePatch) => void;
  onDiscuss?: (operationId: string, message: string, history: DiscussMessage[]) => Promise<PatchDiscussionResult>;
  onAnswerAsk?: (ask: ExperienceAsk, answer: string) => Promise<void>;
  askBusy?: boolean;
  busy?: boolean;
  optimization?: OptimizationRun | null;
  previewHost?: HTMLElement | null;
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
  const current = operations[safeIndex] ?? null;
  const history = current ? (histories[current.id] ?? []) : [];

  useEffect(() => {
    setPendingDraft(null);
    setDiscussError("");
  }, [current?.id]);

  const quality = optimization?.quality ?? null;
  const qualityFailed = Boolean(quality && !quality.passed);

  function acceptOperation(operationId: string) {
    setSelected((prev) => new Set(prev).add(operationId));
    const nextIndex = operations.findIndex((item) => item.id === operationId);
    if (nextIndex >= 0 && nextIndex < total - 1) setIndex(nextIndex + 1);
  }

  function rejectOperation(operationId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(operationId);
      return next;
    });
  }

  function selectOperation(operationId: string) {
    const nextIndex = operations.findIndex((item) => item.id === operationId);
    if (nextIndex >= 0) setIndex(nextIndex);
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
        { role: "assistant", content: "已采用本轮改写，批注已更新。若还要调整可继续讨论。" },
      ],
    }));
  }

  const experienceAsks = patch.experience_asks ?? [];

  const asksBlock = experienceAsks.length > 0 ? (
    <ExperienceAskPanel asks={experienceAsks} busy={askBusy || busy} onAnswer={onAnswerAsk} />
  ) : null;

  if (!current && experienceAsks.length === 0) {
    return (
      <section className="patch-review">
        <div className="panel-heading">
          <div><span className="panel-index">04</span><h2>建议确认</h2></div>
        </div>
        <p className="panel-note">当前没有可审阅的建议。</p>
      </section>
    );
  }

  if (!current) {
    return (
      <section className="patch-review">
        <div className="panel-heading">
          <div><span className="panel-index">04</span><h2>补充项目线索</h2></div>
        </div>
        <p className="panel-note">AI 判断当前项目经历相对岗位偏少，先确认你是否还有可补充的相关经历。</p>
        {asksBlock}
      </section>
    );
  }

  const draftAfter = pendingDraft ? displayPatchValue(pendingDraft.after) : "";
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

  const board = (
    <AnnotatedResumePreview
      projectId={projectId}
      applicationType={applicationType}
      resume={resume}
      templateId={templateId}
      operations={operations}
      selected={selected}
      activeOperation={current}
      onSelectOperation={selectOperation}
      onAccept={acceptOperation}
      onReject={rejectOperation}
    />
  );

  return (
    <section className="patch-review patch-review-annotations" aria-labelledby="patch-title">
      <div className="panel-heading">
        <div><span className="panel-index">04</span><h2 id="patch-title">建议确认</h2></div>
        <span>{selected.size}/{total} 已同意</span>
      </div>
      <p className="panel-note">
        右侧是与导出同源的 Word/PDF 预览；批注栏标明修改位置。点「同意」后才会生效。
      </p>

      {qualityFailed && quality?.reasons?.length ? (
        <p className="optimization-quality-inline" role="status">
          质量提醒：{quality.reasons.slice(0, 3).join("；")}
          {quality.reasons.length > 3 ? "…" : ""}
        </p>
      ) : null}

      {asksBlock}

      {previewHost ? createPortal(board, previewHost) : board}

      <div className="patch-review-footer">
        <label className="privacy-confirm">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(event) => setAgreed(event.target.checked)}
            aria-label="我同意仅应用已勾选的建议"
          />
          <span><strong>我已阅读并同意</strong>仅将已点「同意」的批注应用到新版本。</span>
        </label>
        <button
          className="primary-button"
          type="button"
          disabled={selected.size === 0 || !agreed || busy || discussBusy}
          onClick={() => onApply([...selected])}
        >
          应用已同意的修改（{selected.size}）
        </button>
      </div>

      {onDiscuss ? (
        <AiAssistChat
          disabled={busy}
          busy={discussBusy}
          title="与 AI 讨论"
          contextLabel={`正在讨论批注 ${safeIndex + 1} · ${current.path}`}
          messages={history}
          error={discussError}
          onSend={sendDiscuss}
          emptyHint="可以说你想怎么改；只有你确认「采用此改写」后才会更新本条批注。"
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
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const current = asks[Math.min(index, Math.max(asks.length - 1, 0))];
  if (!current) return null;

  const guidanceLines = (current.guidance || "")
    .split(/\n|·/)
    .map((line) => line.replace(/^[\s•\-]+/, "").trim())
    .filter(Boolean);
  const keywords = current.jd_keywords ?? [];
  const step = Math.min(index + 1, asks.length);

  return (
    <section className="experience-ask-sheet" aria-labelledby="experience-ask-title">
      <header className="experience-ask-sheet-head">
        <div>
          <span className="experience-ask-eyebrow">可选补充</span>
          <h3 id="experience-ask-title">项目线索</h3>
        </div>
        <span className="experience-ask-step" aria-label={`第 ${step} 条，共 ${asks.length} 条`}>
          {step}/{asks.length}
        </span>
      </header>

      <div className="experience-ask-body">
        {current.topic ? <span className="experience-ask-topic">{current.topic}</span> : null}
        <p className="experience-ask-question">{current.question}</p>

        {guidanceLines.length > 0 ? (
          <ul className="experience-ask-hints">
            {guidanceLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}

        {keywords.length > 0 ? (
          <div className="experience-ask-keywords" aria-label="相关关键词">
            {keywords.map((keyword) => (
              <span key={keyword}>{keyword}</span>
            ))}
          </div>
        ) : null}

        {onAnswer ? (
          <>
            <label className="experience-ask-field">
              <span>你的补充</span>
              <textarea
                aria-label="补充项目回答"
                rows={4}
                value={answer}
                disabled={busy}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="有相关经历就写清行动与结果；没有可直接跳过"
              />
            </label>
            <div className="experience-ask-actions">
              <button
                type="button"
                className="primary-button"
                disabled={busy || !answer.trim()}
                onClick={async () => {
                  await onAnswer(current, answer.trim());
                  setAnswer("");
                  setIndex((value) => value + 1);
                }}
              >
                保存到事实库
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={busy}
                onClick={() => {
                  setAnswer("");
                  setIndex((value) => value + 1);
                }}
              >
                跳过
              </button>
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}
