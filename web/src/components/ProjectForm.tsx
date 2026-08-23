import { useState, type FormEvent } from "react";

import type { ApplicationType, ProjectCreateInput } from "../types";


type Props = {
  onCreate: (input: ProjectCreateInput) => void | Promise<unknown>;
  pending?: boolean;
};

const APPLICATION_TYPES: { value: ApplicationType; label: string; note: string }[] = [
  { value: "campus", label: "校招", note: "固定一页" },
  { value: "internship", label: "实习", note: "固定一页" },
  { value: "experienced", label: "社招", note: "自然分页" },
];

export function ProjectForm({ onCreate, pending = false }: Props) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [applicationType, setApplicationType] = useState<ApplicationType>("experienced");
  const [jd, setJd] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
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
        <p>先确定岗位，后续每条修改都会回到这份 JD 找依据。</p>
      </div>
      <label>
        <span>项目名称</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例：字节跳动后端工程师" />
      </label>
      <label>
        <span>公司名称 <small>选填</small></span>
        <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="例：示例科技" />
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
              onChange={() => setApplicationType(item.value)}
            />
            <strong>{item.label}</strong>
            <small>{item.note}</small>
          </label>
        ))}
      </fieldset>
      <label>
        <span>职位描述</span>
        <textarea value={jd} onChange={(event) => setJd(event.target.value)} rows={8} placeholder="粘贴完整 JD，保留职责与要求原文" />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" type="submit" disabled={pending}>
        {pending ? "正在创建…" : "创建求职项目"}
      </button>
    </form>
  );
}
