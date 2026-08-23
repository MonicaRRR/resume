import { type FormEvent, useRef, useState } from "react";

import { blankResume, sourcedText } from "../resume";
import type { Fact, ResumeDocument } from "../types";


export function ResumeIntake({ onUpload, onCreate, busy = false }: {
  onUpload: (file: File) => void;
  onCreate: (resume: ResumeDocument, facts: Fact[]) => void;
  busy?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"choose" | "manual">("choose");
  const [fields, setFields] = useState({ name: "", role: "", education: "", experience: "", project: "", skills: "" });

  function submit(event: FormEvent) {
    event.preventDefault();
    const resume = blankResume();
    resume.basics.name = fields.name.trim();
    resume.basics.target_role = sourcedText(fields.role.trim());
    const facts: Fact[] = [];
    const addFact = (category: string, statement: string) => {
      if (!statement.trim()) return null;
      const id = crypto.randomUUID();
      facts.push({ id, category, statement: statement.trim(), source_type: "manual", source_location: "经历表单", user_confirmed: true });
      return id;
    };
    const educationFact = addFact("教育经历", fields.education);
    if (fields.education.trim()) {
      resume.education.push({
        id: crypto.randomUUID(), institution: fields.education.trim(), degree: "", field: "", start_date: "", end_date: "",
        highlights: educationFact ? [{ ...sourcedText(fields.education.trim()), source_fact_ids: [educationFact] }] : [],
      });
    }
    const experienceFact = addFact("工作/实习经历", fields.experience);
    if (fields.experience.trim()) {
      resume.work_experience.push({
        id: crypto.randomUUID(), company: "经历待细化", title: fields.role.trim(), start_date: "", end_date: "",
        bullets: [{ ...sourcedText(fields.experience.trim()), source_fact_ids: experienceFact ? [experienceFact] : [] }],
      });
    }
    const projectFact = addFact("项目经历", fields.project);
    if (fields.project.trim()) {
      resume.projects.push({
        id: crypto.randomUUID(), name: "代表项目", role: fields.role.trim(), start_date: "", end_date: "",
        bullets: [{ ...sourcedText(fields.project.trim()), source_fact_ids: projectFact ? [projectFact] : [] }],
      });
    }
    const skills = fields.skills.split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean);
    const skillFact = addFact("专业技能", fields.skills);
    if (skills.length) {
      resume.skills.push({ id: crypto.randomUUID(), name: "技能", items: skills.map((item) => ({ ...sourcedText(item), source_fact_ids: skillFact ? [skillFact] : [] })) });
    }
    onCreate(resume, facts);
  }

  if (mode === "choose") return (
    <section className="intake-panel">
      <div className="panel-heading"><div><span className="panel-index">01</span><h2>建立事实底稿</h2></div></div>
      <p className="panel-note">上传后优先沿用原简历的字体、颜色与布局线索；所有个人事实只保存在本机。</p>
      <div className="intake-choices">
        <button type="button" className="intake-choice" disabled={busy} onClick={() => fileRef.current?.click()}>
          <span>DOCX · PDF · TXT</span><strong>上传现有简历</strong><small>优先保留原模板，PDF 将近似还原</small>
        </button>
        <input
          ref={fileRef}
          className="visually-hidden"
          type="file"
          accept=".docx,.pdf,.txt"
          aria-label="上传现有简历"
          onChange={(event) => event.target.files?.[0] && onUpload(event.target.files[0])}
        />
        <button type="button" className="intake-choice" disabled={busy} onClick={() => setMode("manual")}>
          <span>结构化输入</span><strong>从经历开始</strong><small>先录入已知信息，再由 AI 逐题追问</small>
        </button>
      </div>
    </section>
  );

  return (
    <form className="manual-intake" onSubmit={submit}>
      <div className="panel-heading"><div><span className="panel-index">01</span><h2>从经历创建简历</h2></div><button type="button" className="text-button" onClick={() => setMode("choose")}>返回</button></div>
      <label>姓名<input required value={fields.name} onChange={(event) => setFields({ ...fields, name: event.target.value })} /></label>
      <label>目标岗位<input required value={fields.role} onChange={(event) => setFields({ ...fields, role: event.target.value })} /></label>
      <label>教育经历<textarea required rows={2} placeholder="学校、专业、学历、时间" value={fields.education} onChange={(event) => setFields({ ...fields, education: event.target.value })} /></label>
      <label>最近的工作或实习经历<textarea rows={4} placeholder="做了什么、怎么做、产生什么结果" value={fields.experience} onChange={(event) => setFields({ ...fields, experience: event.target.value })} /></label>
      <label>代表项目<textarea rows={4} placeholder="项目目标、你的角色、难点与结果" value={fields.project} onChange={(event) => setFields({ ...fields, project: event.target.value })} /></label>
      <label>专业技能<textarea required rows={2} placeholder="用逗号分隔，例如 Python、FastAPI、PostgreSQL" value={fields.skills} onChange={(event) => setFields({ ...fields, skills: event.target.value })} /></label>
      <button className="primary-button" disabled={busy}>保存事实并生成初稿</button>
    </form>
  );
}
