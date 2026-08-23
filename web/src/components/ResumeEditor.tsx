import type { ResumeDocument, SourcedText } from "../types";


export function ResumeEditor({ resume, onChange, onSave, onDiscard, busy = false }: {
  resume: ResumeDocument;
  onChange: (resume: ResumeDocument) => void;
  onSave: () => void;
  onDiscard: () => void;
  busy?: boolean;
}) {
  const updateBasics = (key: "name" | "email" | "phone" | "location", value: string) => {
    const next = structuredClone(resume);
    next.basics[key] = value;
    onChange(next);
  };
  const updateSourced = (key: "target_role" | "summary", value: string) => {
    const next = structuredClone(resume);
    next.basics[key].value = value;
    next.basics[key].origin = "manual";
    onChange(next);
  };
  const updateBullet = (section: "work_experience" | "projects", entryIndex: number, bulletIndex: number, value: string) => {
    const next = structuredClone(resume);
    const entry = next[section][entryIndex];
    (entry.bullets[bulletIndex] as SourcedText).value = value;
    (entry.bullets[bulletIndex] as SourcedText).origin = "manual";
    onChange(next);
  };

  return (
    <section className="resume-editor">
      <div className="panel-heading"><div><span className="panel-index">E</span><h2>编辑当前版本</h2></div><span>修改不会覆盖旧版本</span></div>
      <div className="editor-grid">
        <label>姓名<input value={resume.basics.name} onChange={(event) => updateBasics("name", event.target.value)} /></label>
        <label>目标岗位<input value={resume.basics.target_role.value} onChange={(event) => updateSourced("target_role", event.target.value)} /></label>
        <label>邮箱<input value={resume.basics.email} onChange={(event) => updateBasics("email", event.target.value)} /></label>
        <label>电话<input value={resume.basics.phone} onChange={(event) => updateBasics("phone", event.target.value)} /></label>
        <label className="editor-wide">个人概述<textarea rows={4} value={resume.basics.summary.value} onChange={(event) => updateSourced("summary", event.target.value)} /></label>
      </div>
      {[{ key: "work_experience" as const, title: "工作经历" }, { key: "projects" as const, title: "项目经历" }].map(({ key, title }) => resume[key].length > 0 && (
        <div className="editor-section" key={key}><h3>{title}</h3>{resume[key].map((entry, entryIndex) => <div key={entry.id}><strong>{"company" in entry ? entry.company : entry.name}</strong>{entry.bullets.map((bullet, bulletIndex) => <label key={bulletIndex}>要点 {bulletIndex + 1}<textarea rows={3} value={bullet.value} onChange={(event) => updateBullet(key, entryIndex, bulletIndex, event.target.value)} /></label>)}</div>)}</div>
      ))}
      <div className="button-row"><button type="button" className="primary-button" disabled={busy} onClick={onSave}>保存为新版本</button><button type="button" className="secondary-button" onClick={onDiscard}>放弃草稿</button></div>
    </section>
  );
}
