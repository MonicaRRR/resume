import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";


export type ChatMessage = { role: "user" | "assistant"; content: string };


type Props = {
  disabled?: boolean;
  busy?: boolean;
  title?: string;
  contextLabel?: string;
  messages: ChatMessage[];
  error?: string;
  onSend: (message: string) => Promise<void> | void;
  emptyHint?: ReactNode;
  busyLabel?: string;
  footer?: ReactNode;
  openLabel?: string;
};


export function AiAssistChat({
  disabled = false,
  busy = false,
  title = "与 AI 讨论",
  contextLabel,
  messages,
  error = "",
  onSend,
  emptyHint = "告诉 AI 你的想法；它可以反驳或追问，确认后才改写。",
  busyLabel = "AI 正在思考…",
  footer,
  openLabel = "与 AI 讨论",
}: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const titleId = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [open, messages, busy, footer]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!draft.trim() || disabled || busy) return;
    const message = draft.trim();
    setDraft("");
    await onSend(message);
  }

  return (
    <>
      <button
        type="button"
        className={`ai-assist-fab ${open ? "open" : ""}`}
        aria-label={openLabel}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <span aria-hidden="true">✦</span>
        <strong>AI</strong>
      </button>

      {open ? (
        <div className="ai-assist-root" role="presentation">
          <button type="button" className="ai-assist-backdrop" aria-label="关闭对话" onClick={() => setOpen(false)} />
          <section className="ai-assist-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
            <header className="ai-assist-header">
              <div>
                <h2 id={titleId}>{title}</h2>
                {contextLabel ? <p>{contextLabel}</p> : null}
              </div>
              <button type="button" className="text-button" onClick={() => setOpen(false)}>完成</button>
            </header>

            <div className="ai-assist-thread" ref={listRef} aria-live="polite">
              {messages.length === 0 && !busy ? (
                <div className="ai-assist-empty">{emptyHint}</div>
              ) : null}
              {messages.map((item, index) => (
                <div key={`${item.role}-${index}`} className={`ai-assist-bubble ${item.role}`}>
                  <span>{item.role === "user" ? "你" : "AI"}</span>
                  <p>{item.content}</p>
                </div>
              ))}
              {busy ? <div className="ai-assist-typing">{busyLabel}</div> : null}
              {footer}
            </div>

            <form className="ai-assist-composer" onSubmit={(event) => void submit(event)}>
              <textarea
                ref={inputRef}
                rows={2}
                value={draft}
                disabled={disabled || busy}
                placeholder="输入你的想法…"
                aria-label="对 AI 的讨论内容"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
              />
              <button type="submit" className="primary-button" disabled={disabled || busy || !draft.trim()}>
                {busy ? "发送中" : "发送"}
              </button>
            </form>
            {error ? <p className="form-error ai-assist-error" role="alert">{error}</p> : null}
          </section>
        </div>
      ) : null}
    </>
  );
}
