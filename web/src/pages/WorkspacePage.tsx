import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError, downloadDraftDocx, downloadFile, downloadPreviewPdf } from "../api/client";
import { JobAnalysisPanel } from "../components/JobAnalysisPanel";
import { PatchReview } from "../components/PatchReview";
import { ResumeEditor } from "../components/ResumeEditor";
import { ResumePreview } from "../components/ResumePreview";
import { TemplatePicker } from "../components/TemplatePicker";
import { AppleAlert } from "../components/ui/AppleAlert";
import { recommendTemplate } from "../templates/registry";
import type { ResumeDocument, ResumePatch } from "../types";


type Stage = "job" | "facts" | "match" | "optimize" | "export" | "practice";

const STAGES: { id: Stage; number: string; label: string }[] = [
  { id: "job", number: "01", label: "岗位信息" },
  { id: "match", number: "02", label: "匹配分析" },
  { id: "facts", number: "03", label: "事实讨论" },
  { id: "optimize", number: "04", label: "建议确认" },
  { id: "export", number: "05", label: "导出" },
  { id: "practice", number: "06", label: "求职训练" },
];


export function WorkspacePage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("job");
  const [draft, setDraft] = useState<ResumeDocument | null>(null);
  const [jdDraft, setJdDraft] = useState("");
  const [patch, setPatch] = useState<ResumePatch | null>(null);
  const [questions, setQuestions] = useState<Array<{ id: string; question: string; topic: string; guidance?: string }>>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [overflow, setOverflow] = useState(false);
  const [pendingVersionId, setPendingVersionId] = useState<string | null>(null);
  const [restoreConfirmOpen, setRestoreConfirmOpen] = useState(false);
  const matchBootstrapped = useRef(false);

  const projectQuery = useQuery({ queryKey: ["project", id], queryFn: () => api.getProject(id), enabled: Boolean(id) });
  const versionsQuery = useQuery({ queryKey: ["versions", id], queryFn: () => api.getVersions(id), enabled: Boolean(id) });
  const providerQuery = useQuery({
    queryKey: ["provider-settings"],
    queryFn: api.getProviderSettings,
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
  });
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

  async function analyze() {
    await run("analyze", async () => {
      const jd = jdDraft.trim() || project?.job_description.trim() || "";
      if (!jd) {
        setMessage("请先粘贴职位描述再分析。");
        return;
      }
      if (jd !== project?.job_description) await api.updateProject(id, { job_description: jd });
      await api.analyzeJob(id, provider);
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
      await queryClient.invalidateQueries({ queryKey: ["match", id] });
      setStage("match");
      setMessage("岗位分析与证据匹配已更新。可继续补充事实或生成适配建议。");
    });
  }

  async function refreshMatch() {
    await run("match", async () => {
      await api.refreshMatch(id, provider);
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
      await queryClient.invalidateQueries({ queryKey: ["match", id] });
      setMessage("已用 AI 重新匹配证据（学历/技能硬条件由规则校正）。");
    });
  }

  useEffect(() => {
    const requested = searchParams.get("stage");
    if (requested === "match" || requested === "job" || requested === "facts" || requested === "optimize" || requested === "export" || requested === "practice") {
      setStage(requested);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (matchBootstrapped.current) return;
    if (stage !== "match") return;
    if (!project?.job_analysis || !activeVersion || !providerQuery.data?.configured) return;
    if (project.match_report) {
      matchBootstrapped.current = true;
      return;
    }
    matchBootstrapped.current = true;
    void refreshMatch();
  }, [stage, project, activeVersion, providerQuery.data?.configured]);

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
      const version = await api.applyPatch(id, patch, accepted);
      setPatch(null);
      setDraft(structuredClone(version.resume));
      await refreshResume();
      setMessage(`已应用 ${accepted.length} 条建议并生成新版本；右侧预览已更新，未同意内容保持不变。`);
    });
  }

  async function answerExperienceAsk(ask: { id: string; topic: string }, answerText: string) {
    await run("ask", async () => {
      if (answerText.trim()) {
        await api.addFact(id, answerText.trim(), ask.topic || "项目经历");
        await refreshResume();
        setMessage("已把补充经历记入事实库。可再到经历库完善成正式项目条目，然后重新生成适配建议。");
      }
      setPatch((prev) => (
        prev
          ? { ...prev, experience_asks: prev.experience_asks.filter((item) => item.id !== ask.id) }
          : prev
      ));
    });
  }

  async function restoreFromProfile() {
    await run("restore", async () => {
      const version = await api.restoreFromProfile(id);
      setPatch(null);
      setQuestions([]);
      setQuestionIndex(0);
      setAnswer("");
      setDraft(structuredClone(version.resume));
      await refreshResume();
      setMessage("已从经历库复原投递底稿。之后的 AI 分析会重新基于经历库内容；历史改坏版本仍保留在左侧记录里。");
      setRestoreConfirmOpen(false);
      setStage("match");
    });
  }

  async function discussOperation(operationId: string, message: string, history: Array<{ role: "user" | "assistant"; content: string }>) {
    if (!patch) throw new Error("没有可讨论的建议");
    return api.refinePatchOperation(id, provider, patch, operationId, message, history);
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
    setPendingVersionId(versionId);
  }

  async function confirmActivateVersion() {
    if (!pendingVersionId) return;
    const versionId = pendingVersionId;
    setPendingVersionId(null);
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
          <div className="workbench-header-actions">
            {activeVersion && (
              <button
                type="button"
                className="secondary-button"
                disabled={busy === "restore"}
                onClick={() => setRestoreConfirmOpen(true)}
              >
                {busy === "restore" ? "正在复原…" : "从经历库复原"}
              </button>
            )}
            <span className={`connection-chip ${providerQuery.data?.configured ? "ready" : ""}`}>{providerQuery.data?.configured ? `${provider === "codex" ? "Codex" : "API"} 已连接` : "AI 未配置"}</span>
          </div>
        </header>
        {message && <div className="workspace-message" role="status">{message}</div>}
        {!activeVersion ? (
          <EmptyStage title="缺少经历底稿" action="去完善经历库" onClick={() => navigate("/profile")} />
        ) : (
          <>
            {stage === "job" && <section className="job-panel">
              <div className="panel-heading"><div><span className="panel-index">01</span><h2>职位描述</h2></div><span>{project.company_name || "目标公司待定"}</span></div>
              <p className="panel-note">
                创建项目时已自动分析 JD。这里可改 JD 后重新分析；会同步刷新证据匹配。
                {project.job_analysis ? " 当前已有岗位分析结果。" : " 当前还没有分析结果，请先分析。"}
              </p>
              <textarea aria-label="职位描述" rows={15} value={jdDraft} onChange={(event) => setJdDraft(event.target.value)} />
              {!providerQuery.data?.configured && <p className="panel-note">先在<Link to="/settings">模型设置</Link>中连接 OpenAI 兼容 API 或确认使用 Codex。</p>}
              <div className="button-row">
                <button className="primary-button" disabled={busy === "analyze" || !jdDraft.trim() || !providerQuery.data?.configured} onClick={analyze}>
                  {busy === "analyze" ? "正在分析…" : project.job_analysis ? "重新分析职位描述" : "分析职位描述"}
                </button>
                {project.job_analysis && (
                  <button className="secondary-button" type="button" onClick={() => setStage("match")}>查看匹配分析</button>
                )}
              </div>
            </section>}

            {stage === "match" && (project.job_analysis ? <>
              <JobAnalysisPanel analysis={project.job_analysis} match={matchQuery.data ?? project.match_report ?? null} />
              <div className="action-strip">
                <div>
                  <strong>生成面向 JD 的筛选与润色建议</strong>
                  <p>匹配以 AI 为主，学历/技能/全栈等硬条件由规则校正。建议默认不生效，需你在「建议确认」逐项同意。</p>
                </div>
                <div className="button-row">
                  <button className="primary-button" disabled={busy === "suggest"} onClick={suggest}>生成适配建议</button>
                  <button className="secondary-button" type="button" disabled={busy === "match" || !providerQuery.data?.configured} onClick={refreshMatch}>
                    {busy === "match" ? "正在匹配…" : "重新匹配证据"}
                  </button>
                  <button className="secondary-button" type="button" onClick={() => setStage("facts")}>补充事实缺口</button>
                </div>
              </div>
            </> : <EmptyStage title="尚未分析 JD" action="前往岗位信息" onClick={() => setStage("job")} />)}

            {stage === "facts" && <section className="facts-panel">
              <div className="panel-heading"><div><span className="panel-index">03</span><h2>与 AI 讨论事实缺口</h2></div><span>{activeVersion.facts.length} 条事实</span></div>
              <p className="panel-note">
                建议先完成「匹配分析」，再针对缺口追问。全局经历请在 <Link to="/profile">经历库</Link> 维护；这里可补当前岗位证据，或微调本项目投递稿。
                若被 AI 改坏，可点右上角「从经历库复原」。
              </p>
              {!project.job_analysis && (
                <div className="completion-note">尚未分析 JD。请先回「岗位信息」分析职位描述，再让 AI 追问缺失证据。</div>
              )}
              {draft && (
                <ResumeEditor
                  resume={draft}
                  onChange={setDraft}
                  onSave={saveDraft}
                  onDiscard={() => setDraft(structuredClone(activeVersion.resume))}
                  busy={busy === "save"}
                />
              )}
              <div className="panel-heading" style={{ marginTop: 24 }}><div><span className="panel-index">证</span><h2>已沉淀事实</h2></div></div>
              <div className="fact-list">{activeVersion.facts.map((fact, index) => <article key={fact.id}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{fact.category}</strong><p>{fact.statement}</p><small>{fact.source_type === "upload" ? "来自上传简历" : "用户已确认"}</small></div></article>)}</div>
              {project.job_analysis && !currentQuestion && <button className="secondary-button" disabled={busy === "questions"} onClick={getFollowups}>让 AI 追问缺失证据</button>}
              {currentQuestion && (
                <div className="question-card">
                  <span>讨论 {questionIndex + 1}/{questions.length}</span>
                  <h3>{currentQuestion.question}</h3>
                  {currentQuestion.guidance && (
                    <ul className="ask-guidance">
                      {currentQuestion.guidance
                        .split(/\n|·/)
                        .map((line) => line.replace(/^[\s•\-]+/, "").trim())
                        .filter(Boolean)
                        .map((line) => <li key={line}>{line}</li>)}
                    </ul>
                  )}
                  <textarea aria-label="补充回答" rows={5} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="尽量说明你的行动、方法和可验证结果；也可按上方线索回忆相关项目" />
                  <div className="button-row">
                    <button className="primary-button" disabled={!answer.trim() || busy === "answer"} onClick={saveAnswer}>保存回答</button>
                    <button className="secondary-button" onClick={() => { setAnswer(""); setQuestionIndex((index) => index + 1); }}>跳过</button>
                  </div>
                </div>
              )}
              {questionIndex >= questions.length && questions.length > 0 && <div className="completion-note">本轮讨论已完成，可回到匹配分析生成适配建议。</div>}
            </section>}

            {stage === "optimize" && draft && <>
              {patch ? (
                <PatchReview
                  patch={patch}
                  onChange={setPatch}
                  onDiscuss={discussOperation}
                  onAnswerAsk={answerExperienceAsk}
                  askBusy={busy === "ask"}
                  onApply={applySelected}
                  busy={busy === "apply"}
                />
              ) : (
                <div className="action-strip">
                  <div>
                    <strong>针对当前岗位讨论改写方案</strong>
                    <p>请先在「匹配分析」生成建议；也可在此重新生成。每条都要你同意才会写入。</p>
                  </div>
                  <button className="primary-button" disabled={!project.job_analysis || busy === "suggest"} onClick={suggest}>生成适配建议</button>
                </div>
              )}
              <TemplatePicker selected={project.selected_template_id} recommended={recommendation?.id} onChange={selectTemplate} />
              {recommendation && <p className="recommendation-reason">推荐理由：{recommendation.reason}。手动选择始终优先。</p>}
            </>}

            {stage === "export" && <section className="export-panel">
              <div className="panel-heading"><div><span className="panel-index">05</span><h2>本地导出</h2></div><span>可导出</span></div>
              {overflow && <div className="overflow-warning"><strong>当前超过 1 页</strong><span>仍可导出 Word / PDF；校招/实习投递时建议再精简。</span></div>}
              <p className="panel-note">正式投递推荐导出 <strong>Word（DOCX）</strong>；右侧是同一份 Word 转成的真实 PDF 分页预览。</p>
              <div className="export-grid">
                <button onClick={() => draft && void downloadDraftDocx(id, draft, project.selected_template_id, `${project.title}.docx`)} disabled={!draft}><span>DOCX</span><strong>下载 Word 简历</strong><small>与右侧预览同源，含当前基础信息</small></button>
                <button onClick={() => draft && void downloadPreviewPdf(id, draft, project.selected_template_id, `${project.title}.pdf`)} disabled={!draft}><span>PDF</span><strong>下载 PDF 预览稿</strong><small>与右侧预览同源排版</small></button>
                <button onClick={() => downloadFile(`/api/projects/${id}/export/json`, `${project.title}.json`)}><span>JSON</span><strong>下载结构化简历</strong><small>不包含模型密钥</small></button>
                <button onClick={() => copyHandoff(false)}><span>CODEX</span><strong>复制 Codex 上下文</strong><small>交给 Codex 聊天继续优化</small></button>
                <button onClick={() => copyHandoff(true)}><span>MD</span><strong>下载 Codex 上下文</strong><small>仅供 AI 协作，非投递稿</small></button>
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
        {draft ? <ResumePreview projectId={id} resume={draft} templateId={project.selected_template_id} applicationType={project.application_type} onOverflowChange={setOverflow} /> : <div className="preview-empty"><span>A4</span><strong>简历预览将在这里出现</strong><p>先在经历库写全资料，再创建求职项目。</p></div>}
        {activeVersion && <div className="evidence-legend"><span className="evidence-mark" /> 表示这段内容带有可追溯的事实依据</div>}
      </aside>

      <AppleAlert
        open={Boolean(pendingVersionId)}
        title="切换历史版本？"
        message="确定切换到这个历史版本？当前版本不会被删除，可随时再切换回来。"
        confirmLabel="切换"
        onCancel={() => setPendingVersionId(null)}
        onConfirm={() => void confirmActivateVersion()}
      />
      <AppleAlert
        open={restoreConfirmOpen}
        title="从经历库复原投递底稿？"
        message="会用当前经历库覆盖本项目投递稿，并生成新版本。被 AI 改坏的内容不会丢，仍可在左侧版本记录里找回。之后的 AI 建议会重新基于经历库分析。"
        confirmLabel="一键复原"
        onCancel={() => setRestoreConfirmOpen(false)}
        onConfirm={() => void restoreFromProfile()}
      />
    </main>
  );
}


function EmptyStage({ title, action, onClick }: { title: string; action: string; onClick: () => void }) {
  return <section className="empty-stage"><span>等待输入</span><h2>{title}</h2><button className="primary-button" onClick={onClick}>{action}</button></section>;
}
