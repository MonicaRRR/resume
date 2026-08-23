import type { CSSProperties, ReactNode } from "react";

import type { JobAnalysis, ResumeDocument, SourcedText } from "../types";


export type ResumeTemplate = {
  id: string;
  label: string;
  description: string;
};

export const TEMPLATES: ResumeTemplate[] = [
  { id: "clear-single", label: "清晰单栏", description: "信息顺序清楚，适合多数岗位" },
  { id: "pro-double", label: "专业双栏", description: "突出技能密度与专业能力" },
  { id: "project-focus", label: "项目聚焦", description: "将项目证据放在视觉中心" },
  { id: "career-depth", label: "经历纵深", description: "适合多段工作经历自然分页" },
];


export function recommendTemplate(resume: ResumeDocument, _job: JobAnalysis | null): ResumeTemplate & { reason: string } {
  const skillCount = resume.skills.reduce((total, group) => total + group.items.length, 0);
  let id = "clear-single";
  let reason = "信息结构均衡，优先保证阅读清晰";
  if (resume.projects.length > resume.work_experience.length) {
    id = "project-focus";
    reason = "项目证据比工作经历更丰富";
  } else if (skillCount > 8) {
    id = "pro-double";
    reason = "技能项较多，双栏能提高信息密度";
  } else if (resume.work_experience.length > 3) {
    id = "career-depth";
    reason = "工作经历较多，纵向时间线更易阅读";
  }
  return { ...TEMPLATES.find((item) => item.id === id)!, reason };
}


function EvidenceText({ text }: { text: SourcedText }) {
  return (
    <span>
      {text.value}
      {text.source_fact_ids.length > 0 && (
        <span
          className="evidence-mark"
          title={`事实依据：${text.source_fact_ids.join("、")}`}
          aria-label={`有 ${text.source_fact_ids.length} 条事实依据`}
        />
      )}
    </span>
  );
}


function Section({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return <section className={`resume-section ${className}`}><h2>{title}</h2>{children}</section>;
}


function ContactLine({ resume }: { resume: ResumeDocument }) {
  const details = [resume.basics.phone, resume.basics.email, resume.basics.location].filter(Boolean);
  return <p className="resume-contact">{details.join(" · ") || "电话 · 邮箱 · 所在地"}</p>;
}


export function TemplateResume({ resume, templateId }: { resume: ResumeDocument; templateId: string }) {
  const preserveImported = resume.layout_profile.imported && templateId === "clear-single";
  const effectiveTemplateId = preserveImported && resume.layout_profile.columns === 2 ? "pro-double" : templateId;
  const ordered = effectiveTemplateId === "project-focus"
    ? ["projects", "education", "work", "skills"]
    : effectiveTemplateId === "pro-double"
      ? ["summary", "work", "projects", "education", "skills"]
      : ["summary", "education", "work", "projects", "skills"];
  const importedStyle: CSSProperties & Record<`--${string}`, string | number> = {};
  if (preserveImported) {
    const profile = resume.layout_profile;
    if (profile.font_family.trim()) importedStyle.fontFamily = profile.font_family.trim();
    if (profile.heading_font_family.trim()) importedStyle["--resume-heading-font"] = profile.heading_font_family.trim();
    if (/^#[0-9a-f]{6}$/i.test(profile.accent_color)) importedStyle["--resume-accent"] = profile.accent_color;
    if (profile.base_font_size && profile.base_font_size >= 8 && profile.base_font_size <= 14) importedStyle.fontSize = `${profile.base_font_size}px`;
    if (profile.line_height && profile.line_height >= 1.1 && profile.line_height <= 1.8) importedStyle.lineHeight = String(profile.line_height);
  }

  const sections: Record<string, ReactNode> = {
    summary: resume.basics.summary.value ? (
      <Section title="个人概述"><p><EvidenceText text={resume.basics.summary} /></p></Section>
    ) : null,
    education: resume.education.length ? (
      <Section title="教育经历">
        {resume.education.map((item) => <article className="resume-entry" key={item.id}>
          <div className="entry-heading"><strong>{item.institution}</strong><span>{item.start_date} — {item.end_date}</span></div>
          <p>{[item.degree, item.field].filter(Boolean).join(" · ")}</p>
          {item.highlights.length > 0 && <ul>{item.highlights.map((line, index) => <li key={index}><EvidenceText text={line} /></li>)}</ul>}
        </article>)}
      </Section>
    ) : null,
    work: resume.work_experience.length ? (
      <Section title="工作经历">
        {resume.work_experience.map((item) => <article className="resume-entry" key={item.id}>
          <div className="entry-heading"><strong>{item.company}</strong><span>{item.start_date} — {item.end_date}</span></div>
          <p className="entry-role">{item.title}</p>
          <ul>{item.bullets.map((line, index) => <li key={index}><EvidenceText text={line} /></li>)}</ul>
        </article>)}
      </Section>
    ) : null,
    projects: resume.projects.length ? (
      <Section title="项目经历" className="project-section">
        {resume.projects.map((item) => <article className="resume-entry" key={item.id}>
          <div className="entry-heading"><strong>{item.name}</strong><span>{item.start_date} — {item.end_date}</span></div>
          <p className="entry-role">{item.role}</p>
          <ul>{item.bullets.map((line, index) => <li key={index}><EvidenceText text={line} /></li>)}</ul>
        </article>)}
      </Section>
    ) : null,
    skills: resume.skills.length ? (
      <Section title="专业技能" className="skill-section">
        {resume.skills.map((group) => <p key={group.id}><strong>{group.name}：</strong>{group.items.map((item, index) => <span key={index}><EvidenceText text={item} />{index < group.items.length - 1 ? "、" : ""}</span>)}</p>)}
      </Section>
    ) : null,
  };

  return (
    <article className={`resume-paper resume-sheet template-${effectiveTemplateId}`} style={importedStyle}>
      <header className="resume-header">
        <div>
          <h1>{resume.basics.name || "你的姓名"}</h1>
          <p className="target-role">{resume.basics.target_role.value || "目标岗位"}</p>
        </div>
        <ContactLine resume={resume} />
      </header>
      <div className="resume-sections">
        {ordered.map((key) => <div className={`resume-slot slot-${key}`} key={key}>{sections[key]}</div>)}
        {resume.certificates.length > 0 && <Section title="证书">{resume.certificates.map((item) => <p key={item.id}><strong>{item.name}</strong> <EvidenceText text={item.detail} /></p>)}</Section>}
        {resume.awards.length > 0 && <Section title="荣誉奖项">{resume.awards.map((item) => <p key={item.id}><strong>{item.name}</strong> <EvidenceText text={item.detail} /></p>)}</Section>}
        {resume.custom_sections.map((section) => <Section title={section.title} key={section.id}><ul>{section.items.map((item, index) => <li key={index}><EvidenceText text={item} /></li>)}</ul></Section>)}
      </div>
    </article>
  );
}
