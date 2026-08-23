import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { PracticePanel } from "../components/PracticePanel";
import type { PracticeSession, Project, ProviderSettings } from "../types";


export function PracticePage() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [provider, setProvider] = useState<ProviderSettings | null>(null);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getProject(id), api.getProviderSettings()])
      .then(([projectValue, providerValue]) => { setProject(projectValue); setProvider(providerValue); })
      .catch(() => setError("无法读取训练所需的项目数据"));
  }, [id]);

  async function start(kind: "interview" | "written") {
    setBusy(true);
    setError("");
    try {
      setSession(await api.createPractice(id, kind, provider?.kind || "openai-compatible"));
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
      setSession(await api.answerPractice(session.id, value, provider?.kind || "openai-compatible"));
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
        <div className="mode-intro"><span>06 / PRACTICE</span><h2>把“会做”练成“能讲清楚”</h2><p>训练题目只使用当前岗位与简历里的事实。面试不打虚假的百分分数，笔试解析只会在作答后出现。</p>{!provider?.configured && <p className="form-error">AI 尚未连接，请先前往<Link to="/settings">模型设置</Link>。</p>}</div>
        <button type="button" disabled={busy || !provider?.configured} onClick={() => start("interview")}><span>INTERVIEW</span><strong>模拟面试</strong><p>岗位动机、经历深挖、行为题、专业题与连续追问</p><i>开始 →</i></button>
        <button type="button" disabled={busy || !provider?.configured} onClick={() => start("written")}><span>WRITTEN</span><strong>笔试练习</strong><p>选择、简答、案例与专业题；先作答，后看提示与解析</p><i>开始 →</i></button>
      </section> : <PracticePanel session={session} onAnswer={answer} busy={busy} error={error} />}
      {!session && error && <p className="form-error practice-error">{error}</p>}
    </main>
  );
}
