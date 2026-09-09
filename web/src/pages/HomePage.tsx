import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ProjectForm } from "../components/ProjectForm";
import { AppleAlert } from "../components/ui/AppleAlert";
import type { ApplicationType, ProjectCreateInput } from "../types";


const TYPE_LABEL: Record<ApplicationType, string> = {
  campus: "校招 · 一页",
  internship: "实习 · 一页",
  experienced: "社招 · 不限页",
};

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.listProjects });
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);
  const create = useMutation({
    mutationFn: (input: ProjectCreateInput) => api.createProject(input),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}?stage=match`);
    },
  });
  const remove = useMutation({
    mutationFn: (projectId: string) => api.deleteProject(projectId),
    onSuccess: async () => {
      setPendingDelete(null);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const createError = create.error instanceof ApiError
    ? create.error.message
    : create.error
      ? "创建失败"
      : "";
  const deleteError = remove.error instanceof ApiError
    ? remove.error.message
    : remove.error
      ? "删除失败"
      : "";

  return (
    <main className="home-page">
      <section className="home-intro">
        <p className="eyebrow">RESUME EVIDENCE DESK</p>
        <h1>简历证据工作台</h1>
        <p className="lead">先在经历库写全自己，再为每个岗位只填 JD——AI 直接开始筛选润色，改动须你同意。</p>
        <div className="local-note"><span>本地优先</span>简历默认只保存在本机</div>

        <div className="action-strip" style={{ marginTop: 28 }}>
          <div>
            <strong>{profile.data?.ready ? "经历库已就绪" : "第一步：完善个人经历库"}</strong>
            <p>{profile.data?.ready
              ? `已沉淀 ${profile.data.facts.length} 条事实，可直接创建求职项目。`
              : "填写姓名与教育 / 工作 / 项目 / 技能，写得越详细越好。"}</p>
          </div>
          <Link className="primary-link" to="/profile">{profile.data?.ready ? "编辑经历库" : "去填写经历库"}</Link>
        </div>

        <div className="project-list" aria-live="polite">
          <div className="section-title"><h2>求职项目</h2><span>{projects.data?.length ?? 0} 个</span></div>
          {projects.isError && <p className="form-error">无法读取本地项目，请确认后端服务已启动。</p>}
          {deleteError && <p className="form-error">{deleteError}</p>}
          {projects.data?.length === 0 && <p className="empty-note">创建项目时只需填写名称、公司、求职类型与 JD。</p>}
          {projects.data?.map((project) => (
            <div className="project-row" key={project.id}>
              <Link className="project-card" to={`/projects/${project.id}`}>
                <div>
                  <span className="project-type">{TYPE_LABEL[project.application_type]}</span>
                  <h3>{project.title}</h3>
                  <p>{project.company_name || "未填写公司"}</p>
                </div>
                <span className="card-arrow" aria-hidden="true">↗</span>
              </Link>
              <button
                type="button"
                className="text-button project-delete"
                disabled={remove.isPending}
                aria-label={`删除项目 ${project.title}`}
                onClick={() => setPendingDelete({ id: project.id, title: project.title })}
              >
                删除
              </button>
            </div>
          ))}
        </div>
      </section>

      <aside className="create-panel">
        <ProjectForm
          onCreate={(input) => create.mutateAsync(input)}
          pending={create.isPending}
          profileReady={Boolean(profile.data?.ready)}
        />
        {createError && <p className="form-error">{createError}</p>}
      </aside>

      <AppleAlert
        open={Boolean(pendingDelete)}
        title="删除求职项目？"
        message={pendingDelete
          ? `确定删除「${pendingDelete.title}」？相关投递稿与版本会一并删除，经历库不受影响。`
          : ""}
        confirmLabel="删除"
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete.id)}
      />
    </main>
  );
}
