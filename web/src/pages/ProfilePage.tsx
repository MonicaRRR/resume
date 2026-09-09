import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ResumeEditor } from "../components/ResumeEditor";
import { blankResume } from "../resume";
import type { ResumeDocument } from "../types";


export function ProfilePage() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [draft, setDraft] = useState<ResumeDocument | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (profileQuery.data) setDraft(structuredClone(profileQuery.data.resume));
  }, [profileQuery.data]);

  const save = useMutation({
    mutationFn: (resume: ResumeDocument) => api.saveProfile(resume),
    onSuccess: async (payload) => {
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      setDraft(structuredClone(payload.resume));
      setError("");
      setMessage(payload.ready
        ? `经历库已保存（${payload.facts.length} 条事实）。现在可以去创建求职项目，先分析 JD 再生成适配建议。`
        : "已保存。请至少填写姓名，以及教育 / 工作 / 项目 / 技能之一，才能创建求职项目。");
    },
    onError: (reason) => {
      setMessage("");
      setError(reason instanceof ApiError ? reason.message : "保存失败");
    },
  });

  if (profileQuery.isLoading || !draft) {
    return <main className="page-placeholder"><h1>个人经历库</h1><p>正在读取本机资料……</p></main>;
  }

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
      <div className={`provider-card ${profileQuery.data?.ready ? "connected" : ""}`} style={{ minHeight: "auto" }}>
        <ResumeEditor
          resume={draft}
          onChange={setDraft}
          onSave={() => save.mutate(draft)}
          onDiscard={() => setDraft(structuredClone(profileQuery.data?.resume ?? blankResume()))}
          busy={save.isPending}
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
