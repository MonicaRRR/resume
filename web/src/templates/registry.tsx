import type { CSSProperties, ReactNode } from "react";

import type { JobAnalysis, ResumeDocument, SourcedText } from "../types";


export type ResumeTemplate = {
  id: string;
  label: string;
  description: string;
};

export const TEMPLATES: ResumeTemplate[] = [
  { id: "overleaf-cn", label: "Overleaf 中文模板", description: "基于 resume-chinese 的 XeLaTeX 模板，紧凑单栏、日期右对齐" },
  { id: "classic-cn", label: "经典中文单栏", description: "居中页眉、章节下划线、日期右对齐，贴近校招纸质稿" },
  { id: "clear-single", label: "清晰单栏", description: "信息顺序清楚，适合多数岗位" },
  { id: "pro-double", label: "专业双栏", description: "突出技能密度与专业能力" },
  { id: "project-focus", label: "项目聚焦", description: "将项目证据放在视觉中心" },
  { id: "career-depth", label: "经历纵深", description: "适合多段工作经历自然分页" },
];


export function recommendTemplate(resume: ResumeDocument, _job: JobAnalysis | null): ResumeTemplate & { reason: string } {
  const skillCount = resume.skills.reduce((total, group) => total + group.items.length, 0);
  let id = "overleaf-cn";
  let reason = "Overleaf 中文模板使用 XeLaTeX 排版，中文字体与日期对齐更稳定";
  if (resume.projects.length > resume.work_experience.length + 1) {
    id = "project-focus";
    reason = "项目证据比工作经历更丰富";
  } else if (skillCount > 10) {
    id = "pro-double";
    reason = "技能项较多，双栏能提高信息密度";
  } else if (resume.work_experience.length > 4) {
    id = "career-depth";
    reason = "工作经历较多，纵向时间线更易阅读";
  }
  return { ...TEMPLATES.find((item) => item.id === id)!, reason };
}


const GENERIC_SKILL_NAMES = new Set(["", "技能", "专业技能", "skills", "skill"]);

function skillLinesForDisplay(groups: ResumeDocument["skills"]): string[] {
  const named: { name: string; items: string[] }[] = [];
  const generic: string[] = [];
  for (const group of groups) {
    const items = group.items.map((item) => item.value.trim()).filter(Boolean);
    if (!items.length) continue;
    const name = group.name.trim();
    if (GENERIC_SKILL_NAMES.has(name.toLowerCase())) {
      for (const item of items) {
        const parts = splitSkillTokens(item);
        generic.push(...parts);
      }
      continue;
    }
    named.push({ name, items });
  }
  const lines = named.map((group) => `${group.name}：${group.items.join("、")}`);
  const seen = new Set(lines);
  for (const item of generic) {
    if (seen.has(item)) continue;
    seen.add(item);
    lines.push(item);
  }
  return lines;
}

function splitSkillTokens(value: string): string[] {
  if (value.includes("：") || value.includes(":")) return [value];
  if (value.length > 40) return [value];
  const parts = value.replace(/，/g, "、").replace(/,/g, "、").split("、").map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2 || parts.some((part) => part.length > 18)) return [value];
  return parts;
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


type AnnotationTone = "pending" | "accepted" | "active" | "gap";

export type ResumeAnnotationMarks = Record<string, {
  count: number;
  tone: AnnotationTone;
  /** 1-based 批注序号，与右侧批注栏一致 */
  numbers: number[];
}>;


function badgeLabel(numbers: number[]): string {
  if (numbers.length <= 1) return String(numbers[0] ?? 1);
  if (numbers.length === 2) return `${numbers[0]}·${numbers[1]}`;
  return `${numbers[0]}+`;
}


function Annotatable({
  target,
  marks,
  activeTarget,
  onSelect,
  children,
  className = "",
}: {
  target: string;
  marks?: ResumeAnnotationMarks;
  activeTarget?: string | null;
  onSelect?: (target: string) => void;
  children: ReactNode;
  className?: string;
}) {
  const mark = marks?.[target];
  if (!mark && !onSelect) {
    return <div className={className || undefined}>{children}</div>;
  }
  const tone = activeTarget === target ? "active" : mark?.tone;
  const classes = [
    "resume-annotatable",
    className,
    mark ? "has-suggestion" : "",
    tone ? `tone-${tone}` : "",
  ].filter(Boolean).join(" ");
  const numbers = mark?.numbers ?? [];
  return (
    <div
      className={classes}
      data-annotation-target={target}
      role={mark ? "button" : undefined}
      tabIndex={mark ? 0 : undefined}
      aria-pressed={activeTarget === target || undefined}
      aria-label={mark ? `批注 ${numbers.join("、")}，共 ${mark.count} 条` : undefined}
      onClick={mark && onSelect ? (event) => {
        event.stopPropagation();
        onSelect(target);
      } : undefined}
      onKeyDown={mark && onSelect ? (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          onSelect(target);
        }
      } : undefined}
    >
      {children}
      {mark ? <span className="resume-annotation-badge">{badgeLabel(numbers)}</span> : null}
    </div>
  );
}


function ContactLine({ resume }: { resume: ResumeDocument }) {
  const identity = [
    resume.basics.gender ? `性别：${resume.basics.gender}` : "",
    resume.basics.birthday ? `生日：${resume.basics.birthday}` : "",
    resume.basics.political_status ? `政治面貌：${resume.basics.political_status}` : "",
    resume.basics.location ? `现居：${resume.basics.location}` : "",
  ].filter(Boolean);
  const contact = [
    resume.basics.phone ? `电话：${resume.basics.phone}` : "",
    resume.basics.email ? `邮箱：${resume.basics.email}` : "",
    resume.basics.wechat ? `微信：${resume.basics.wechat}` : "",
  ].filter(Boolean);
  const details = [...identity, ...contact];
  return <p className="resume-contact">{details.join(" · ") || "性别 · 生日 · 电话 · 邮箱 · 所在地"}</p>;
}


export function TemplateResume({
  resume,
  templateId,
  annotationMarks,
  activeAnnotationTarget = null,
  onSelectAnnotation,
}: {
  resume: ResumeDocument;
  templateId: string;
  annotationMarks?: ResumeAnnotationMarks;
  activeAnnotationTarget?: string | null;
  onSelectAnnotation?: (target: string) => void;
}) {
  const preserveImported = resume.layout_profile.imported && (templateId === "clear-single" || templateId === "classic-cn");
  const effectiveTemplateId = preserveImported && resume.layout_profile.columns === 2 ? "pro-double" : templateId;
  const ordered = effectiveTemplateId === "project-focus"
    ? ["projects", "education", "skills", "work"]
    : effectiveTemplateId === "pro-double"
      ? ["summary", "education", "skills", "work", "projects"]
      : ["summary", "education", "skills", "work", "projects"];
  const importedStyle: CSSProperties & Record<`--${string}`, string | number> = {};
  if (preserveImported) {
    const profile = resume.layout_profile;
    if (profile.font_family.trim()) importedStyle.fontFamily = profile.font_family.trim();
    if (profile.heading_font_family.trim()) importedStyle["--resume-heading-font"] = profile.heading_font_family.trim();
    if (/^#[0-9a-f]{6}$/i.test(profile.accent_color)) importedStyle["--resume-accent"] = profile.accent_color;
    if (profile.base_font_size && profile.base_font_size >= 8 && profile.base_font_size <= 14) importedStyle.fontSize = `${profile.base_font_size}px`;
    if (profile.line_height && profile.line_height >= 1.1 && profile.line_height <= 1.8) importedStyle.lineHeight = String(profile.line_height);
  }

  const bind = {
    marks: annotationMarks,
    activeTarget: activeAnnotationTarget,
    onSelect: onSelectAnnotation,
  };

  const sections: Record<string, ReactNode> = {
    summary: resume.basics.summary.value ? (
      <Annotatable target="basics.summary" {...bind}>
        <Section title="个人概述"><p><EvidenceText text={resume.basics.summary} /></p></Section>
      </Annotatable>
    ) : null,
    education: resume.education.length ? (
      <Section title="教育经历">
        {resume.education.map((item, index) => (
          <Annotatable key={item.id} target={`education.${index}`} className="resume-entry-wrap" {...bind}>
            <article className="resume-entry">
              <div className="entry-heading"><strong>{item.institution}</strong><span>{item.start_date} — {item.end_date}</span></div>
              <p>{[item.degree, item.field].filter(Boolean).join(" · ")}</p>
              {item.highlights.length > 0 && <ul>{item.highlights.map((line, lineIndex) => <li key={lineIndex}><EvidenceText text={line} /></li>)}</ul>}
            </article>
          </Annotatable>
        ))}
      </Section>
    ) : null,
    work: resume.work_experience.length ? (
      <Section title="实习工作经历">
        {resume.work_experience.map((item, index) => (
          <Annotatable key={item.id} target={`work_experience.${index}`} className="resume-entry-wrap" {...bind}>
            <article className="resume-entry">
              <div className="entry-heading"><strong>{item.company}</strong><span>{item.start_date} — {item.end_date}</span></div>
              <p className="entry-role">{item.title}</p>
              <ul>{item.bullets.map((line, lineIndex) => <li key={lineIndex}><EvidenceText text={line} /></li>)}</ul>
            </article>
          </Annotatable>
        ))}
      </Section>
    ) : null,
    projects: resume.projects.length ? (
      <Section title="项目经历" className="project-section">
        {resume.projects.map((item, index) => (
          <Annotatable key={item.id} target={`projects.${index}`} className="resume-entry-wrap" {...bind}>
            <article className="resume-entry">
              <div className="entry-heading"><strong>{item.name}</strong><span>{item.start_date} — {item.end_date}</span></div>
              <p className="entry-role">{item.role}</p>
              <ul>{item.bullets.map((line, lineIndex) => <li key={lineIndex}><EvidenceText text={line} /></li>)}</ul>
            </article>
          </Annotatable>
        ))}
      </Section>
    ) : null,
    skills: (() => {
      const lines = skillLinesForDisplay(resume.skills);
      if (!lines.length) return null;
      return (
        <Annotatable target="skills" {...bind}>
          <Section title="专业技能" className="skill-section">
            <ul>
              {lines.map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          </Section>
        </Annotatable>
      );
    })(),
  };

  return (
    <Annotatable target="resume" {...bind} className="resume-root-annotatable">
      <article className={`resume-paper resume-sheet template-${effectiveTemplateId}`} style={importedStyle}>
        <Annotatable target="basics.header" {...bind}>
          <header className={`resume-header${resume.basics.photo_data_url ? " resume-header-with-photo" : ""}`}>
            <div>
              <h1>{resume.basics.name || "你的姓名"}</h1>
              <Annotatable target="basics.target_role" {...bind}>
                <p className="target-role">{resume.basics.target_role.value || "目标岗位"}</p>
              </Annotatable>
              <ContactLine resume={resume} />
            </div>
            {resume.basics.photo_data_url ? (
              <img className="resume-photo" src={resume.basics.photo_data_url} alt="证件照" />
            ) : null}
          </header>
        </Annotatable>
        <div className="resume-sections">
          {ordered.map((key) => <div className={`resume-slot slot-${key}`} key={key}>{sections[key]}</div>)}
          {resume.certificates.length > 0 && (
            <Annotatable target="certificates" {...bind}>
              <Section title="证书">{resume.certificates.map((item) => <p key={item.id}><strong>{item.name}</strong> <EvidenceText text={item.detail} /></p>)}</Section>
            </Annotatable>
          )}
          {resume.awards.length > 0 && (
            <Annotatable target="awards" {...bind}>
              <Section title="荣誉奖项">{resume.awards.map((item) => <p key={item.id}><strong>{item.name}</strong> <EvidenceText text={item.detail} /></p>)}</Section>
            </Annotatable>
          )}
          {resume.custom_sections.map((section, index) => (
            <Annotatable key={section.id} target={`custom_sections.${index}`} {...bind}>
              <Section title={section.title}><ul>{section.items.map((item, itemIndex) => <li key={itemIndex}><EvidenceText text={item} /></li>)}</ul></Section>
            </Annotatable>
          ))}
        </div>
      </article>
    </Annotatable>
  );
}
