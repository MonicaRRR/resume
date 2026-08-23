import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { ProjectForm } from "../components/ProjectForm";
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
  const create = useMutation({
    mutationFn: (input: ProjectCreateInput) => api.createProject(input),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
  });

  return (
    <main className="home-page">
      <section className="home-intro">
        <p className="eyebrow">RESUME EVIDENCE DESK</p>
        <h1>简历证据工作台</h1>
        <p className="lead">不是把关键词塞进简历，而是让每一句话都有经历支撑、与岗位相关。</p>
        <div className="local-note"><span>本地优先</span>简历默认只保存在本机</div>

        <div className="project-list" aria-live="polite">
          <div className="section-title"><h2>求职项目</h2><span>{projects.data?.length ?? 0} 个</span></div>
          {projects.isError && <p className="form-error">无法读取本地项目，请确认后端服务已启动。</p>}
          {projects.data?.length === 0 && <p className="empty-note">创建第一份针对岗位的简历，分析会从 JD 原文开始。</p>}
          {projects.data?.map((project) => (
            <Link className="project-card" key={project.id} to={`/projects/${project.id}`}>
              <div>
                <span className="project-type">{TYPE_LABEL[project.application_type]}</span>
                <h3>{project.title}</h3>
                <p>{project.company_name || "未填写公司"}</p>
              </div>
              <span className="card-arrow" aria-hidden="true">↗</span>
            </Link>
          ))}
        </div>
      </section>

      <aside className="create-panel">
        <ProjectForm onCreate={(input) => create.mutateAsync(input)} pending={create.isPending} />
        {create.error && <p className="form-error">{create.error.message}</p>}
      </aside>
    </main>
  );
}
