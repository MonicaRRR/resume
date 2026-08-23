import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError, downloadFile } from "../api/client";
import { JobAnalysisPanel } from "../components/JobAnalysisPanel";
import { PatchReview } from "../components/PatchReview";
import { ResumeEditor } from "../components/ResumeEditor";
import { ResumeIntake } from "../components/ResumeIntake";
import { ResumePreview } from "../components/ResumePreview";
import { TemplatePicker } from "../components/TemplatePicker";
import { recommendTemplate } from "../templates/registry";
import type { Fact, ResumeDocument, ResumePatch } from "../types";


type Stage = "job" | "facts" | "match" | "optimize" | "export" | "practice";

const STAGES: { id: Stage; number: string; label: string }[] = [
  { id: "job", number: "01", label: "岗位信息" },
  { id: "facts", number: "02", label: "个人事实" },
  { id: "match", number: "03", label: "匹配分析" },
  { id: "optimize", number: "04", label: "简历优化" },
  { id: "export", number: "05", label: "导出" },
  { id: "practice", number: "06", label: "求职训练" },
];


export function WorkspacePage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("job");
  const [draft, setDraft] = useState<ResumeDocument | null>(null);
  const [jdDraft, setJdDraft] = useState("");
  const [patch, setPatch] = useState<ResumePatch | null>(null);
  const [questions, setQuestions] = useState<Array<{ id: string; question: string; topic: string }>>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [overflow, setOverflow] = useState(false);

  const projectQuery = useQuery({ queryKey: ["project", id], queryFn: () => api.getProject(id), enabled: Boolean(id) });
  const versionsQuery = useQuery({ queryKey: ["versions", id], queryFn: () => api.getVersions(id), enabled: Boolean(id) });
  const providerQuery = useQuery({ queryKey: ["provider-settings"], queryFn: api.getProviderSettings, retry: false });
  const project = projectQuery.data;
  const versions = versionsQuery.data ?? [];
  const activeVersion = versions.find((version) => version.id === project?.active_resume_version_id) ?? versions[0];
  const matchQuery = useQuery({
    queryKey: ["match", id, project?.active_resume_version_id],
    queryFn: () => api.getMatch(id),
    enabled: Boolean(project?.job_analysis && activeVersion),
    retry: false,
  });
  const provider = providerQuery.data?.kind || "openai-compatible";

  useEffect(() => {
    if (project) setJdDraft(project.job_description);
  }, [project?.id, project?.job_description]);
  useEffect(() => {
    if (activeVersion) setDraft(structuredClone(activeVersion.resume));
  }, [activeVersion?.id]);

  const recommendation = useMemo(
    () => draft ? recommendTemplate(draft, project?.job_analysis ?? null) : null,
    [draft, project?.job_analysis],
  );

  async function refreshResume() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project", id] }),
      queryClient.invalidateQueries({ queryKey: ["versions", id] }),
      queryClient.invalidateQueries({ queryKey: ["match", id] }),
    ]);
  }

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setMessage("");
    try {
      await action();
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "操作未完成，请检查本地服务后重试");
    } finally {
      setBusy("");
    }
  }

  async function upload(file: File) {
    await run("upload", async () => {
      await api.importResume(id, file);
      await refreshResume();
      setStage("facts");
      setMessage("简历已导入，原始版本已安全保存。");
    });
  }

  async function createResume(resume: ResumeDocument, facts: Fact[]) {
    await run("create", async () => {
      await api.saveResume(id, resume, facts, "从经历创建初稿");
      await refreshResume();
      setStage("facts");
      setMessage("事实底稿和初版简历已创建。");
    });
  }

  async function analyze() {
    await run("analyze", async () => {
      if (jdDraft !== project?.job_description) await api.updateProject(id, { job_description: jdDraft });
      await api.analyzeJob(id, provider);
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
      await queryClient.invalidateQueries({ queryKey: ["match", id] });
      setStage("match");
      setMessage("岗位分析完成，每条要求均保留了 JD 原文依据。");
    });
  }

  async function getFollowups() {
    await run("questions", async () => {
      const result = await api.getQuestions(id, provider);
      setQuestions(result);
      setQuestionIndex(0);
      setStage("facts");
    });
  }

  async function saveAnswer() {
    if (!answer.trim()) return;
    await run("answer", async () => {
      const current = questions[questionIndex];
      await api.addFact(id, answer.trim(), current?.topic || "补充回答");
      await refreshResume();
      setAnswer("");
      setQuestionIndex((index) => index + 1);
    });
  }

  async function suggest() {
    await run("suggest", async () => {
      setPatch(await api.suggestPatch(id, provider));
      setStage("optimize");
    });
  }

  async function applySelected(accepted: string[]) {
    if (!patch) return;
    await run("apply", async () => {
      await api.applyPatch(id, patch, accepted);
      setPatch(null);
      await refreshResume();
      setMessage("已生成新的简历版本，原版本仍可随时恢复。");
    });
  }

  async function saveDraft() {
    if (!draft || !activeVersion) return;
    await run("save", async () => {
      await api.saveResume(id, draft, activeVersion.facts, "手动编辑");
      await refreshResume();
      setMessage("手动修改已保存为新版本。");
    });
  }

  async function selectTemplate(templateId: string) {
    await run("template", async () => {
      await api.updateProject(id, { selected_template_id: templateId });
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
    });
  }

  async function activateVersion(versionId: string) {
    if (!window.confirm("切换到这个历史版本？当前版本不会被删除。")) return;
    await run("version", async () => {
      await api.activateVersion(id, versionId);
      await refreshResume();
    });
  }

  async function copyHandoff(download = false) {
    await run("handoff", async () => {
      const { markdown } = await api.getCodexHandoff(id);
      if (download) {
        const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = `${project?.title || "简历"}-Codex上下文.md`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        await navigator.clipboard.writeText(markdown);
        setMessage("Codex 上下文已复制，未包含未选择的敏感联系方式。");
      }
    });
  }

  if (projectQuery.isLoading || versionsQuery.isLoading) return <main className="page-placeholder"><h1>简历工作台</h1><p>正在读取本地项目……</p></main>;
  if (!project) return <main className="page-placeholder"><h1>项目不存在</h1><Link to="/">返回项目列表</Link></main>;

  const currentQuestion = questions[questionIndex];
  const applicationLabel = project.application_type === "campus" ? "校招 · 一页" : project.application_type === "internship" ? "实习 · 一页" : "社招 · 自然分页";

  return (
    <main className="workspace-page">
      <aside className="stage-rail">
        <Link className="back-link" to="/">← 项目列表</Link>
        <div className="project-identity"><span>{applicationLabel}</span><h1>{project.title}</h1><p>{project.company_name || "未填写公司"}</p></div>
        <nav aria-label="简历流程">
          {STAGES.map((item) => <button type="button" className={stage === item.id ? "active" : ""} onClick={() => setStage(item.id)} key={item.id}><span>{item.number}</span>{item.label}{item.id === "facts" && activeVersion && <i>{activeVersion.facts.length}</i>}</button>)}
        </nav>
        <div className="version-list">
          <strong>版本记录</strong>
          {versions.map((version, index) => <button type="button" className={version.id === activeVersion?.id ? "active" : ""} onClick={() => activateVersion(version.id)} key={version.id}><span>v{versions.length - index}</span><small>{version.reason}</small></button>)}
        </div>
      </aside>

      <section className="workbench-center">
        <header className="workbench-header">
          <div><span className="eyebrow">LOCAL EVIDENCE WORKSPACE</span><h2>{STAGES.find((item) => item.id === stage)?.label}</h2></div>
          <span className={`connection-chip ${providerQuery.data?.configured ? "ready" : ""}`}>{providerQuery.data?.configured ? `${provider === "codex" ? "Codex" : "API"} 已连接` : "AI 未配置"}</span>
        </header>
        {message && <div className="workspace-message" role="status">{message}</div>}
        {!activeVersion ? <ResumeIntake onUpload={upload} onCreate={createResume} busy={Boolean(busy)} /> : (
          <>
            {stage === "job" && <section className="job-panel">
              <div className="panel-heading"><div><span className="panel-index">01</span><h2>职位描述</h2></div><span>{project.company_name || "目标公司待定"}</span></div>
              <textarea aria-label="职位描述" rows={15} value={jdDraft} onChange={(event) => setJdDraft(event.target.value)} />
              {!providerQuery.data?.configured && <p className="panel-note">先在<Link to="/settings">模型设置</Link>中连接 OpenAI 兼容 API 或确认使用 Codex。</p>}
              <button className="primary-button" disabled={busy === "analyze" || !jdDraft.trim()} onClick={analyze}>分析职位描述</button>
            </section>}

            {stage === "facts" && <section className="facts-panel">
              <div className="panel-heading"><div><span className="panel-index">02</span><h2>已确认事实</h2></div><span>{activeVersion.facts.length} 条</span></div>
              <p className="panel-note">AI 只能基于这些事实改写，不会凭空增加数字、职责或技能。</p>
              <div className="fact-list">{activeVersion.facts.map((fact, index) => <article key={fact.id}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{fact.category}</strong><p>{fact.statement}</p><small>{fact.source_type === "upload" ? "来自上传简历" : "用户已确认"}</small></div></article>)}</div>
              {project.job_analysis && !currentQuestion && <button className="secondary-button" disabled={busy === "questions"} onClick={getFollowups}>让 AI 追问缺失证据</button>}
              {currentQuestion && <div className="question-card"><span>问题 {questionIndex + 1}/{questions.length}</span><h3>{currentQuestion.question}</h3><textarea aria-label="补充回答" rows={5} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="尽量说明你的行动、方法和可验证结果" /><div className="button-row"><button className="primary-button" disabled={!answer.trim() || busy === "answer"} onClick={saveAnswer}>保存回答</button><button className="secondary-button" onClick={() => { setAnswer(""); setQuestionIndex((index) => index + 1); }}>跳过</button></div></div>}
              {questionIndex >= questions.length && questions.length > 0 && <div className="completion-note">本轮追问已完成，可前往匹配分析查看证据覆盖。</div>}
            </section>}

            {stage === "match" && (project.job_analysis ? <>
              <JobAnalysisPanel analysis={project.job_analysis} match={matchQuery.data} />
              <div className="action-strip"><div><strong>基于事实生成优化建议</strong><p>建议会逐项展示，默认不会应用。</p></div><button className="primary-button" disabled={busy === "suggest"} onClick={suggest}>生成优化建议</button></div>
            </> : <EmptyStage title="尚未分析 JD" action="前往岗位信息" onClick={() => setStage("job")} />)}

            {stage === "optimize" && draft && <>
              {patch ? <PatchReview patch={patch} onApply={applySelected} busy={busy === "apply"} /> : <div className="action-strip"><div><strong>获取针对当前岗位的改写建议</strong><p>所有建议都需要事实依据，并且由你逐项接受。</p></div><button className="primary-button" disabled={!project.job_analysis || busy === "suggest"} onClick={suggest}>生成优化建议</button></div>}
              <ResumeEditor resume={draft} onChange={setDraft} onSave={saveDraft} onDiscard={() => setDraft(structuredClone(activeVersion.resume))} busy={busy === "save"} />
              <TemplatePicker selected={project.selected_template_id} recommended={recommendation?.id} onChange={selectTemplate} />
              {recommendation && <p className="recommendation-reason">推荐理由：{recommendation.reason}。手动选择始终优先。</p>}
            </>}

            {stage === "export" && <section className="export-panel">
              <div className="panel-heading"><div><span className="panel-index">05</span><h2>本地导出</h2></div><span>{overflow ? "需先调整到一页" : "可导出"}</span></div>
              {overflow && <div className="overflow-warning"><strong>校招/实习简历必须为一页</strong><span>右侧内容不会被截断，但 DOCX 与 PDF 暂停导出。</span></div>}
              <div className="export-grid">
                <button disabled={overflow} onClick={() => window.print()}><span>PDF</span><strong>打印或保存 PDF</strong><small>使用系统打印对话框</small></button>
                <button disabled={overflow} onClick={() => downloadFile(`/api/projects/${id}/export/docx`, `${project.title}.docx`, "POST")}><span>DOCX</span><strong>下载可编辑文档</strong><small>沿用当前模板与页数策略</small></button>
                <button onClick={() => downloadFile(`/api/projects/${id}/export/json`, `${project.title}.json`)}><span>JSON</span><strong>下载结构化简历</strong><small>不包含模型密钥</small></button>
                <button onClick={() => copyHandoff(false)}><span>CODEX</span><strong>复制 Codex 上下文</strong><small>交给 Codex 聊天继续优化</small></button>
                <button onClick={() => copyHandoff(true)}><span>MD</span><strong>下载 Codex 上下文</strong><small>本地 Markdown 文件</small></button>
              </div>
            </section>}

            {stage === "practice" && <section className="practice-entry">
              <span className="panel-index">06</span><h2>把当前岗位与简历带进训练</h2><p>模拟面试会从事实证据继续追问；笔试练习会在提交答案后显示解析。</p>
              <Link className="primary-link" to={`/projects/${id}/practice`}>进入面试 / 笔试训练</Link>
            </section>}
          </>
        )}
      </section>

      <aside className="preview-column">
        {draft ? <ResumePreview resume={draft} templateId={project.selected_template_id} applicationType={project.application_type} onOverflowChange={setOverflow} /> : <div className="preview-empty"><span>A4</span><strong>简历预览将在这里出现</strong><p>先上传一份简历，或从你的经历开始创建。</p></div>}
        {activeVersion && <div className="evidence-legend"><span className="evidence-mark" /> 表示这段内容带有可追溯的事实依据</div>}
      </aside>
    </main>
  );
}


function EmptyStage({ title, action, onClick }: { title: string; action: string; onClick: () => void }) {
  return <section className="empty-stage"><span>等待输入</span><h2>{title}</h2><button className="primary-button" onClick={onClick}>{action}</button></section>;
}
