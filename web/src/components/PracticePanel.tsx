import { type FormEvent, useEffect, useState } from "react";

import type { PracticeSession } from "../types";


export function PracticePanel({ session, onAnswer, busy = false, error = "" }: {
  session: PracticeSession;
  onAnswer: (answer: string) => Promise<void>;
  busy?: boolean;
  error?: string;
}) {
  const [answer, setAnswer] = useState("");
  const [showHint, setShowHint] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const question = session.current_question;
  const lastTurn = session.turns.at(-1);

  useEffect(() => {
    setShowHint(false);
    setShowEvidence(false);
  }, [question?.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!answer.trim()) return;
    try {
      await onAnswer(answer.trim());
      setAnswer("");
    } catch {
      // The parent displays the provider error; keep the answer for a safe retry.
    }
  }

  return (
    <section className="practice-panel">
      <div className="practice-progress">
        <span>{session.kind === "interview" ? "模拟面试" : "笔试练习"}</span>
        <div><i /><i /><i /><i /><i /></div>
        <small>第 {session.turns.length + (question ? 1 : 0)} 题</small>
      </div>

      {lastTurn && <article className="practice-feedback">
        <div className="panel-heading"><div><span className="panel-index">评</span><h2>上一题反馈</h2></div></div>
        <p className="feedback-summary">{lastTurn.feedback.summary}</p>
        {lastTurn.feedback.percentage_score !== null && <p className="feedback-score">本题表现：{lastTurn.feedback.percentage_score} 分</p>}
        <dl>{Object.entries(lastTurn.feedback.dimensions).map(([name, detail]) => <div key={name}><dt>{name}</dt><dd>{detail}</dd></div>)}</dl>
        {lastTurn.feedback.improved_answer && <details><summary>查看更好的回答示例</summary><p>{lastTurn.feedback.improved_answer}</p></details>}
        {lastTurn.explanation && <div className="answer-explanation"><strong>参考解析</strong><p>{lastTurn.explanation}</p></div>}
        {lastTurn.follow_up && <p className="followup-note">追问方向：{lastTurn.follow_up}</p>}
      </article>}

      {question ? <form className="practice-question" onSubmit={submit}>
        <header><span>{question.category}</span><h2>{question.prompt}</h2></header>
        <div className="practice-tools">
          <button type="button" onClick={() => setShowHint((value) => !value)}>{showHint ? "收起提示" : "查看提示"}</button>
          <button type="button" onClick={() => setShowEvidence((value) => !value)}>查看题目依据</button>
        </div>
        {showHint && <div className="hint-box"><strong>提示</strong><p>{question.hint || "先用自己的经历拆解问题，再组织答案。"}</p></div>}
        {showEvidence && <div className="evidence-drawer"><strong>题目依据</strong><p>岗位要求 {question.requirement_ids.length} 条 · 简历事实 {question.fact_ids.length} 条</p></div>}
        <label htmlFor="practice-answer">你的回答</label>
        <textarea id="practice-answer" rows={8} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={session.kind === "interview" ? "建议用情境—任务—行动—结果组织回答" : "写下分析过程和最终答案"} />
        {error && <p className="form-error">{error}</p>}
        <div className="button-row"><button className="primary-button" disabled={busy || !answer.trim()}>{busy ? "正在分析…" : "提交答案"}</button><span>提交后才会显示反馈{session.kind === "written" ? "与参考解析" : ""}</span></div>
      </form> : <div className="practice-complete">
        <span>SESSION COMPLETE</span><h2>本轮训练完成</h2><p>已完成 {session.turns.length} 道题。薄弱点会保存在本次训练记录中。</p>
        {session.weaknesses.length > 0 && <ul>{session.weaknesses.map((item) => <li key={item}>{item}</li>)}</ul>}
      </div>}
    </section>
  );
}
