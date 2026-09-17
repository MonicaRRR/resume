import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError, downloadFile } from "../api/client";
import { ResumeEditor } from "../components/ResumeEditor";
import { blankResume } from "../resume";
import type { ResumeDocument } from "../types";


export function ProfilePage() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [draft, setDraft] = useState<ResumeDocument | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [qualityScore, setQualityScore] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  // React Query may refetch the singleton profile while the user is editing
  // (for example when the window regains focus). Only hydrate the local draft
  // once; subsequent server updates must not overwrite unsaved education,
  // work, or project entries.
  const draftHydratedRef = useRef(false);

  useEffect(() => {
    if (profileQuery.data && !draftHydratedRef.current) {
      setDraft(structuredClone(profileQuery.data.resume));
      draftHydratedRef.current = true;
    }
  }, [profileQuery.data]);

  const save = useMutation({
    mutationFn: (resume: ResumeDocument) => api.saveProfile(resume),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      setDraft(structuredClone(payload.resume));
      setError("");
      setImportWarnings([]);
      setQualityScore(null);
      setMessage(payload.ready
        ? `经历库已保存（${payload.facts.length} 条事实）。现在可以去创建求职项目，先分析 JD 再生成适配建议。`
        : "已保存。请至少填写姓名，以及教育 / 工作 / 项目 / 技能之一，才能创建求职项目。");
    },
    onError: (reason) => {
      setMessage("");
      setError(reason instanceof ApiError ? reason.message : "保存失败");
    },
  });

  const importResume = useMutation({
    mutationFn: (file: File) => api.importProfileResume(file),
    onSuccess: (result) => {
      setDraft(structuredClone(result.resume));
      setImportWarnings(result.warnings);
      setQualityScore(result.quality_score);
      setError("");
      setMessage("已填入导入结果，请核对后点击保存经历库。");
      if (fileRef.current) fileRef.current.value = "";
    },
    onError: (reason) => {
      setMessage("");
      setError(reason instanceof ApiError ? reason.message : "导入失败");
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  function onPickFile(file: File) {
    if (draft?.basics.name.trim()) {
      const ok = window.confirm("用导入结果覆盖当前未保存草稿？");
      if (!ok) {
        if (fileRef.current) fileRef.current.value = "";
        return;
      }
    }
    importResume.mutate(file);
  }

  if (profileQuery.isLoading || !draft) {
    return <main className="page-placeholder"><h1>个人经历库</h1><p>正在读取本机资料……</p></main>;
  }

  const busy = save.isPending || importResume.isPending;

  return (
    <main className="settings-page profile-page">
      <header className="settings-hero">
        <div>
          <span className="eyebrow">PERSONAL LIBRARY</span>
          <h1>先写全你的经历</h1>
          <p>尽量详细填写基本信息、教育、实习/工作、项目与技能。这里是素材库；开启求职项目后，AI 会按 JD 筛选润色，并经你同意后才改投递稿。</p>
        </div>
        <a href="/">返回项目</a>
      </header>
      {message && <div className="settings-message success" role="status">{message}</div>}
      {error && <div className="settings-message error" role="alert">{error}</div>}
      {(qualityScore !== null || importWarnings.length > 0) && (
        <div className="settings-message" role="status">
          {qualityScore !== null && <p>解析质量分：{qualityScore.toFixed(2)}</p>}
          {importWarnings.length > 0 && (
            <ul>
              {importWarnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          )}
        </div>
      )}
      <div className={`provider-card ${profileQuery.data?.ready ? "connected" : ""}`} style={{ minHeight: "auto" }}>
        <div className="profile-import-bar">
          <div className="button-row">
            <button
              type="button"
              className="primary-button"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              {importResume.isPending ? "正在解析…" : "上传已有简历 / 备份"}
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={() => void downloadFile("/api/profile/export/json", "个人经历库.json")}
            >
              导出经历库 JSON
            </button>
          </div>
          <input
            ref={fileRef}
            className="visually-hidden"
            type="file"
            accept=".json,.docx,.pdf,.txt,application/json"
            aria-label="上传已有简历"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onPickFile(file);
            }}
          />
          <p className="privacy-note">支持经历库 JSON 备份及 PDF / DOCX / TXT（≤10 MiB）。导入只填入草稿，需点保存后才会写入经历库。</p>
        </div>
        <ResumeEditor
          resume={draft}
          onChange={setDraft}
          onSave={() => save.mutate(draft)}
          onDiscard={() => {
            setDraft(structuredClone(profileQuery.data?.resume ?? blankResume()));
            setImportWarnings([]);
            setQualityScore(null);
            setMessage("");
            setError("");
          }}
          busy={busy}
        />
        <p className="privacy-note">
          {profileQuery.data?.ready
            ? "经历库已就绪，可创建求职项目。"
            : "未就绪：至少填写姓名 +（教育 / 工作 / 项目 / 技能）之一。"}
        </p>
        <Link className="primary-link" to="/">去创建求职项目</Link>
      </div>
    </main>
  );
}
