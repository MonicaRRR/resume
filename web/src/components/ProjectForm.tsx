import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import type { ApplicationType, ProjectCreateInput } from "../types";


type Props = {
  onCreate: (input: ProjectCreateInput) => void | Promise<unknown>;
  pending?: boolean;
  profileReady?: boolean;
};

const APPLICATION_TYPES: { value: ApplicationType; label: string; note: string }[] = [
  { value: "campus", label: "校招", note: "固定一页" },
  { value: "internship", label: "实习", note: "固定一页" },
  { value: "experienced", label: "社招", note: "自然分页" },
];

export function ProjectForm({ onCreate, pending = false, profileReady = false }: Props) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [applicationType, setApplicationType] = useState<ApplicationType>("experienced");
  const [jd, setJd] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!profileReady) {
      setError("请先完善个人经历库");
      return;
    }
    if (!title.trim()) {
      setError("请填写项目名称");
      return;
    }
    if (!jd.trim()) {
      setError("请先粘贴职位描述");
      return;
    }
    setError("");
    await onCreate({
      title: title.trim(),
      company_name: company.trim(),
      application_type: applicationType,
      job_description: jd.trim(),
    });
  }

  return (
    <form className="project-form" onSubmit={submit}>
      <div className="form-heading">
        <span className="step-chip">新项目</span>
        <h2>这次准备投哪里？</h2>
        <p>填写岗位信息后，创建时会自动分析 JD 并做证据匹配；随后可在工作台确认建议。</p>
      </div>
      {!profileReady && (
        <p className="form-error" role="alert">
          尚未完善经历库。<Link to="/profile">先去填写</Link>
        </p>
      )}
      <label>
        <span>项目名称</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例：字节跳动后端工程师" disabled={!profileReady} />
      </label>
      <label>
        <span>公司名称 <small>选填</small></span>
        <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例：示例科技" disabled={!profileReady} />
      </label>
      <fieldset className="type-selector">
        <legend>求职类型</legend>
        {APPLICATION_TYPES.map((item) => (
          <label key={item.value} className={applicationType === item.value ? "type-option active" : "type-option"}>
            <input
              type="radio"
              name="application-type"
              aria-label={item.label}
              value={item.value}
              checked={applicationType === item.value}
              disabled={!profileReady}
              onChange={() => setApplicationType(item.value)}
            />
            <strong>{item.label}</strong>
            <small>{item.note}</small>
          </label>
        ))}
      </fieldset>
      <label>
        <span>职位描述</span>
        <textarea value={jd} onChange={(event) => setJd(event.target.value)} rows={8} placeholder="粘贴完整 JD，保留职责与要求原文" disabled={!profileReady} />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={pending || !profileReady}>
        {pending ? "正在创建并分析岗位…" : "创建项目并分析 JD"}
      </button>
    </form>
  );
}
