/** Map a JSON Pointer patch path to a stable resume annotation target. */

import type { ResumeDocument } from "../types";

export function annotationTargetForPath(path: string): string {
  const parts = path.replace(/^\//, "").split("/").filter(Boolean);
  if (!parts.length) return "resume";
  const root = parts[0];
  if (root === "basics") {
    const field = parts[1] || "";
    if (field === "summary") return "basics.summary";
    if (field === "target_role") return "basics.target_role";
    if (field === "name" || field === "photo_data_url") return "basics.header";
    return "basics.header";
  }
  if (root === "education" || root === "work_experience" || root === "projects") {
    const index = parts[1];
    if (index !== undefined && /^\d+$/.test(index)) return `${root}.${index}`;
    return root;
  }
  if (root === "skills") return "skills";
  if (root === "certificates") return "certificates";
  if (root === "awards") return "awards";
  if (root === "custom_sections") {
    const index = parts[1];
    if (index !== undefined && /^\d+$/.test(index)) return `custom_sections.${index}`;
    return "custom_sections";
  }
  if (root === "section_order") return "resume";
  return root;
}


export function pathMatchesTarget(path: string, target: string): boolean {
  return annotationTargetForPath(path) === target;
}


function entryTitle(
  list: Array<{ company?: string; name?: string; institution?: string; title?: string; role?: string }>,
  index: number,
): string {
  const item = list[index];
  if (!item) return `第 ${index + 1} 条`;
  return (
    item.company
    || item.name
    || item.institution
    || item.title
    || item.role
    || `第 ${index + 1} 条`
  );
}


/** Human-readable resume block label for a target, used to map 批注 ↔ 区块. */
export function annotationLocationLabel(target: string, resume?: ResumeDocument | null): string {
  if (target === "resume") return "整份简历";
  if (target === "basics.header") return "姓名与联系方式";
  if (target === "basics.summary") return "个人概述";
  if (target === "basics.target_role") return "意向岗位";
  if (target === "skills") return "技能";
  if (target === "certificates") return "证书";
  if (target === "awards") return "奖项";
  if (target === "education") return "教育经历";
  if (target === "work_experience") return "工作经历";
  if (target === "projects") return "项目经历";
  if (target === "custom_sections") return "自定义栏目";

  const [root, indexText] = target.split(".");
  const index = Number(indexText);
  if (!Number.isInteger(index) || index < 0 || !resume) {
    if (root === "education") return "教育经历";
    if (root === "work_experience") return "工作经历";
    if (root === "projects") return "项目经历";
    if (root === "custom_sections") return "自定义栏目";
    return target;
  }
  if (root === "education") return `教育 · ${entryTitle(resume.education, index)}`;
  if (root === "work_experience") return `工作 · ${entryTitle(resume.work_experience, index)}`;
  if (root === "projects") return `项目 · ${entryTitle(resume.projects, index)}`;
  if (root === "custom_sections") {
    const section = resume.custom_sections[index];
    return `栏目 · ${section?.title || `第 ${index + 1} 栏`}`;
  }
  return target;
}
