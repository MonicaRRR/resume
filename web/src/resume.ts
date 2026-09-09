import type { ResumeDocument, SourcedText } from "./types";


export function sourcedText(value = ""): SourcedText {
  return { value, source_fact_ids: [], origin: "manual", confidence: 1 };
}


export function blankResume(): ResumeDocument {
  return {
    basics: {
      name: "",
      gender: "",
      birthday: "",
      email: "",
      phone: "",
      location: "",
      wechat: "",
      political_status: "",
      photo_data_url: "",
      target_role: sourcedText(),
      summary: sourcedText(),
    },
    education: [],
    work_experience: [],
    projects: [],
    skills: [],
    certificates: [],
    awards: [],
    custom_sections: [],
    section_order: [
      "basics",
      "education",
      "skills",
      "work_experience",
      "projects",
      "certificates",
      "awards",
      "custom_sections",
    ],
    layout_profile: {
      source_kind: "builtin",
      font_family: "",
      heading_font_family: "",
      accent_color: "#2457d6",
      base_font_size: null,
      line_height: null,
      columns: 1,
      imported: false,
    },
  };
}


export function estimateResumeUnits(resume: ResumeDocument): number {
  const basics = 90 + [
    resume.basics.name,
    resume.basics.gender,
    resume.basics.birthday,
    resume.basics.email,
    resume.basics.phone,
    resume.basics.location,
    resume.basics.wechat,
    resume.basics.political_status,
    resume.basics.photo_data_url ? "photo" : "",
    resume.basics.target_role.value,
    resume.basics.summary.value,
  ].reduce((total, value) => total + value.length, 0);
  const work = resume.work_experience.reduce(
    (total, item) => total + 70 + item.company.length + item.title.length
      + item.bullets.reduce((sum, bullet) => sum + bullet.value.length + 20, 0),
    0,
  );
  const projects = resume.projects.reduce(
    (total, item) => total + 65 + item.name.length + item.role.length
      + item.bullets.reduce((sum, bullet) => sum + bullet.value.length + 20, 0),
    0,
  );
  const education = resume.education.reduce(
    (total, item) => total + 55 + item.institution.length + item.degree.length + item.field.length
      + item.highlights.reduce((sum, highlight) => sum + highlight.value.length + 15, 0),
    0,
  );
  const skills = resume.skills.reduce(
    (total, group) => total + 35 + group.name.length
      + group.items.reduce((sum, item) => sum + item.value.length + 5, 0),
    0,
  );
  const custom = resume.custom_sections.reduce(
    (total, section) => total + 35 + section.title.length
      + section.items.reduce((sum, item) => sum + item.value.length + 15, 0),
    0,
  );
  const extras = [...resume.certificates, ...resume.awards].reduce(
    (total, item) => total + 35 + item.name.length + item.detail.value.length,
    0,
  );
  return basics + work + projects + education + skills + custom + extras;
}


export function isOnePageApplication(applicationType: "campus" | "internship" | "experienced"): boolean {
  return applicationType === "campus" || applicationType === "internship";
}
