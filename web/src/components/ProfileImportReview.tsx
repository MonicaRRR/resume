import { useMemo, useState } from "react";

import type { ProfileImportResult, ResumeDocument } from "../types";


type BasicKey = "name" | "gender" | "birthday" | "phone" | "email" | "location" | "wechat" | "political_status" | "summary";
type ReplaceableSection = "education" | "work_experience" | "skills" | "certificates" | "awards" | "custom_sections";

const BASIC_FIELDS: { key: BasicKey; label: string }[] = [
  { key: "name", label: "姓名" },
  { key: "gender", label: "性别" },
  { key: "birthday", label: "生日" },
  { key: "phone", label: "手机号" },
  { key: "email", label: "邮箱" },
  { key: "location", label: "所在城市" },
  { key: "wechat", label: "微信" },
  { key: "political_status", label: "政治面貌" },
  { key: "summary", label: "个人概述" },
];

const SECTION_LABELS: Record<ReplaceableSection, string> = {
  education: "教育经历",
  work_experience: "工作/实习经历",
  skills: "专业技能",
  certificates: "证书",
  awards: "荣誉奖项",
  custom_sections: "自定义栏目",
};

function basicValue(resume: ResumeDocument, key: BasicKey): string {
  if (key === "summary") return resume.basics.summary.value;
  return resume.basics[key];
}

function sectionValue(resume: ResumeDocument, key: ReplaceableSection): string {
  if (key === "education") {
    return resume.education.map((item) => [item.institution, item.degree, item.field, item.start_date, item.end_date, ...item.highlights.map((line) => line.value)].filter(Boolean).join(" · ")).join("\n");
  }
  if (key === "work_experience") {
    return resume.work_experience.map((item) => [item.company, item.title, item.start_date, item.end_date, ...item.bullets.map((line) => line.value)].filter(Boolean).join(" · ")).join("\n");
  }
  if (key === "skills") return resume.skills.map((group) => `${group.name}：${group.items.map((item) => item.value).filter(Boolean).join("、")}`).join("\n");
  if (key === "custom_sections") return resume.custom_sections.map((item) => `${item.title}：${item.items.map((line) => line.value).filter(Boolean).join("、")}`).join("\n");
  if (key === "certificates") return resume.certificates.map((item) => [item.name, item.detail.value, item.date].filter(Boolean).join(" · ")).join("\n");
  return resume.awards.map((item) => [item.name, item.detail.value, item.date].filter(Boolean).join(" · ")).join("\n");
}

function compact(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function display(value: string): string {
  const text = value.trim();
  return text || "（空）";
}

export function ProfileImportReview({
  current,
  imported,
  onApply,
  onCancel,
}: {
  current: ResumeDocument;
  imported: ProfileImportResult;
  onApply: (resume: ResumeDocument) => void;
  onCancel: () => void;
}) {
  const [selectedBasics, setSelectedBasics] = useState<Set<BasicKey>>(new Set());
  const [selectedSections, setSelectedSections] = useState<Set<ReplaceableSection>>(new Set());
  const [selectedProjects, setSelectedProjects] = useState<Set<number>>(new Set());

  const changedBasics = useMemo(
    () => BASIC_FIELDS.filter(({ key }) => compact(basicValue(imported.resume, key)) && basicValue(current, key) !== basicValue(imported.resume, key)),
    [current, imported.resume],
  );
  const changedSections = useMemo(
    () => (Object.keys(SECTION_LABELS) as ReplaceableSection[]).filter((key) => {
      const incoming = sectionValue(imported.resume, key);
      return incoming && incoming !== sectionValue(current, key);
    }),
    [current, imported.resume],
  );
  const importedProjects = imported.resume.projects.filter((project) => project.name.trim() || project.bullets.some((bullet) => bullet.value.trim()));

  function toggleBasic(key: BasicKey) {
    setSelectedBasics((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleSection(key: ReplaceableSection) {
    setSelectedSections((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleProject(index: number) {
    setSelectedProjects((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index); else next.add(index);
      return next;
    });
  }

  function apply() {
    const next = structuredClone(current);
    for (const field of selectedBasics) {
      if (field === "summary") next.basics.summary = structuredClone(imported.resume.basics.summary);
      else next.basics[field] = imported.resume.basics[field];
    }
    for (const section of selectedSections) {
      if (section === "education") next.education = structuredClone(imported.resume.education);
      if (section === "work_experience") next.work_experience = structuredClone(imported.resume.work_experience);
      if (section === "skills") next.skills = structuredClone(imported.resume.skills);
      if (section === "certificates") next.certificates = structuredClone(imported.resume.certificates);
      if (section === "awards") next.awards = structuredClone(imported.resume.awards);
      if (section === "custom_sections") next.custom_sections = structuredClone(imported.resume.custom_sections);
    }
    next.projects = [
      ...next.projects,
      ...[...selectedProjects].map((index) => ({
        ...structuredClone(importedProjects[index]),
        id: crypto.randomUUID(),
      })),
    ];
    onApply(next);
  }

  return (
    <section className="profile-import-review" aria-labelledby="profile-import-review-title">
      <div className="panel-heading">
        <div><span className="panel-index">核对</span><h2 id="profile-import-review-title">核对导入内容</h2></div>
        <button type="button" className="text-button" onClick={onCancel}>取消导入</button>
      </div>
      <p className="panel-note">
        当前已有内容不会自动覆盖。个人信息和经历区块请逐项勾选替换；项目只会追加你选中的条目，已有项目会保留。
      </p>
      {changedBasics.length === 0 && changedSections.length === 0 && (
        <p className="import-review-empty">未发现个人信息或经历区块差异。</p>
      )}

      {changedBasics.length > 0 && (
        <div className="import-review-section">
          <div className="import-review-section-head"><h3>个人信息差异</h3><small>勾选后才替换</small></div>
          {changedBasics.map(({ key, label }) => (
            <label className="import-diff-row" key={key}>
              <input type="checkbox" aria-label={`替换${label}`} checked={selectedBasics.has(key)} onChange={() => toggleBasic(key)} />
              <span className="import-diff-body">
                <strong>{label}</strong>
                <span className="import-diff-old">原内容：{display(basicValue(current, key))}</span>
                <span className="import-diff-new">导入内容：{display(basicValue(imported.resume, key))}</span>
              </span>
            </label>
          ))}
        </div>
      )}

      {changedSections.length > 0 && (
        <div className="import-review-section">
          <div className="import-review-section-head"><h3>经历区块差异</h3><small>勾选后替换整个区块</small></div>
          {changedSections.map((key) => (
            <label className="import-diff-row" key={key}>
              <input type="checkbox" aria-label={`替换${SECTION_LABELS[key]}`} checked={selectedSections.has(key)} onChange={() => toggleSection(key)} />
              <span className="import-diff-body">
                <strong>{SECTION_LABELS[key]}</strong>
                <span className="import-diff-old">原内容：{display(sectionValue(current, key))}</span>
                <span className="import-diff-new">导入内容：{display(sectionValue(imported.resume, key))}</span>
              </span>
            </label>
          ))}
        </div>
      )}

      <div className="import-review-section">
        <div className="import-review-section-head"><h3>新增项目</h3><small>选择要追加的项目</small></div>
        {importedProjects.length > 0 ? importedProjects.map((project, index) => (
          <label className="import-project-row" key={`${project.name}-${index}`}>
            <input type="checkbox" aria-label={`新增项目 ${project.name || "未命名项目"}`} checked={selectedProjects.has(index)} onChange={() => toggleProject(index)} />
            <span><strong>{project.name || "未命名项目"}</strong><small>{project.role || ""}</small></span>
          </label>
        )) : <p className="import-review-empty">上传内容中没有识别到项目经历。</p>}
      </div>

      <div className="import-review-actions">
        <button type="button" className="secondary-button" onClick={onCancel}>放弃本次导入</button>
        <button type="button" className="primary-button" onClick={apply}>
          应用已选择内容（替换 {selectedBasics.size + selectedSections.size} 项，新增 {selectedProjects.size} 个项目）
        </button>
      </div>
    </section>
  );
}
