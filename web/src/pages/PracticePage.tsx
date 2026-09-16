import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { PracticePanel } from "../components/PracticePanel";
import type { PracticeReport, PracticeSession, Project, ProviderSettings } from "../types";


export function PracticePage() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [provider, setProvider] = useState<ProviderSettings | null>(null);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [interviewMode, setInterviewMode] = useState<"technical" | "hr" | "manager">("technical");
  const [report, setReport] = useState<PracticeReport | null>(null);

  useEffect(() => {
    Promise.all([api.getProject(id), api.getProviderSettings()])
      .then(([projectValue, providerValue]) => { setProject(projectValue); setProvider(providerValue); })
      .catch(() => setError("无法读取训练所需的项目数据"));
  }, [id]);

  async function start(kind: "interview" | "written") {
    setBusy(true);
    setError("");
    try {
      setReport(null);
      setSession(await api.createPractice(id, kind, provider?.kind || "openai-compatible", interviewMode));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "无法开始训练");
    } finally {
      setBusy(false);
    }
  }

  async function answer(value: string) {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      const next = await api.answerPractice(session.id, value, provider?.kind || "openai-compatible");
      setSession(next);
      if (next.status === "completed") setReport(await api.getPracticeReport(next.id));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "回答分析失败，输入内容已保留");
      throw reason;
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="practice-page">
      <header className="practice-header"><div><Link to={`/projects/${id}`}>← 返回简历工作台</Link><span className="eyebrow">JOB READINESS STUDIO</span><h1>{project?.title || "求职训练"}</h1><p>{project?.company_name || "基于当前 JD 与简历事实生成"}</p></div>{session && <button type="button" className="secondary-button" onClick={() => setSession(null)}>结束本轮</button>}</header>
      {!session ? <section className="practice-mode-select">
        <div className="mode-intro"><span>06 / PRACTICE</span><h2>把“会做”练成“能讲清楚”</h2><p>训练题目只使用当前岗位与简历里的事实，反馈会从结构、证据和岗位相关性等维度给出建议。笔试解析只会在作答后出现。</p>{!provider?.configured && <p className="form-error">AI 尚未连接，请先前往<Link to="/settings">模型设置</Link>。</p>}</div>
        <div className="practice-interview-modes" role="group" aria-label="面试模式">
          <strong>面试模式</strong>
          {(["technical", "hr", "manager"] as const).map((mode) => <button key={mode} type="button" className={interviewMode === mode ? "active" : ""} onClick={() => setInterviewMode(mode)}>{mode === "technical" ? "技术面" : mode === "hr" ? "HR 面" : "主管面"}</button>)}
        </div>
        <button type="button" disabled={busy || !provider?.configured} onClick={() => start("interview")}><span>INTERVIEW</span><strong>模拟面试</strong><p>岗位动机、经历深挖、行为题、专业题与连续追问</p><i>开始 →</i></button>
        <button type="button" disabled={busy || !provider?.configured} onClick={() => start("written")}><span>WRITTEN</span><strong>笔试练习</strong><p>选择、简答、案例与专业题；先作答，后看提示与解析</p><i>开始 →</i></button>
      </section> : <><PracticePanel session={session} onAnswer={answer} busy={busy} error={error} />{report && <section className="practice-report" aria-label="训练报告"><div className="panel-heading"><div><span className="panel-index">报</span><h2>本轮训练报告</h2></div><strong>{report.total_score} 分</strong></div><div className="report-dimensions">{Object.entries(report.dimensions).map(([name, score]) => <span key={name}>{name}<b>{score}</b></span>)}</div><div className="report-columns"><div><h3>做得好的地方</h3><ul>{report.strengths.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h3>下一步建议</h3><ul>{[...report.risks, ...report.recommendations].map((item) => <li key={item}>{item}</li>)}</ul></div></div></section>}</>}
      {!session && error && <p className="form-error practice-error">{error}</p>}
    </main>
  );
}
