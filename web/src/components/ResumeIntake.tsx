import { type ChangeEvent, type FormEvent, useRef, useState } from "react";

import { encodeResumePhoto } from "../lib/encodeResumePhoto";
import { blankResume, sourcedText } from "../resume";
import type { Fact, ResumeDocument } from "../types";
import { AppleDateParts } from "./ui/AppleDateParts";
import { AppleSelect } from "./ui/AppleSelect";


type EducationDraft = {
  id: string;
  institution: string;
  degree: string;
  field: string;
  start_date: string;
  end_date: string;
  highlight: string;
};

type WorkDraft = {
  id: string;
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  narrative: string;
};

type ProjectDraft = {
  id: string;
  name: string;
  role: string;
  start_date: string;
  end_date: string;
  narrative: string;
};

const DEGREE_OPTIONS = ["高中", "专科", "本科", "硕士", "博士", "MBA", "其他"];
const GENDER_OPTIONS = [
  { value: "", label: "未填写" },
  { value: "男", label: "男" },
  { value: "女", label: "女" },
  { value: "其他", label: "其他" },
];
const POLITICAL_OPTIONS = [
  { value: "", label: "未填写" },
  { value: "群众", label: "群众" },
  { value: "共青团员", label: "共青团员" },
  { value: "中共党员", label: "中共党员" },
  { value: "中共预备党员", label: "中共预备党员" },
  { value: "其他", label: "其他" },
];

function newId() {
  return crypto.randomUUID();
}

function emptyEducation(): EducationDraft {
  return { id: newId(), institution: "", degree: "本科", field: "", start_date: "", end_date: "", highlight: "" };
}

function emptyWork(): WorkDraft {
  return { id: newId(), company: "", title: "", start_date: "", end_date: "", narrative: "" };
}

function emptyProject(): ProjectDraft {
  return { id: newId(), name: "", role: "", start_date: "", end_date: "", narrative: "" };
}

function parseSkills(raw: string): string[] {
  return raw.split(/[，,、\n]/).map((item) => item.trim()).filter(Boolean);
}


export function ResumeIntake({ onUpload, onCreate, busy = false }: {
  onUpload: (file: File) => void;
  onCreate: (resume: ResumeDocument, facts: Fact[]) => void;
  busy?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"choose" | "manual">("choose");
  const [basics, setBasics] = useState({
    name: "",
    gender: "",
    birthday: "",
    phone: "",
    email: "",
    location: "",
    wechat: "",
    political_status: "",
    photo_data_url: "",
    target_role: "",
  });
  const [education, setEducation] = useState<EducationDraft[]>([emptyEducation()]);
  const [work, setWork] = useState<WorkDraft[]>([emptyWork()]);
  const [projects, setProjects] = useState<ProjectDraft[]>([emptyProject()]);
  const [skillInput, setSkillInput] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [error, setError] = useState("");

  function addSkillTokens(raw: string) {
    const next = [...skills];
    for (const item of parseSkills(raw)) {
      if (!next.includes(item)) next.push(item);
    }
    setSkills(next);
    setSkillInput("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!basics.name.trim()) {
      setError("请填写姓名");
      return;
    }
    if (!basics.target_role.trim()) {
      setError("请填写期望职位");
      return;
    }
    const filledEducation = education.filter((item) => item.institution.trim());
    if (!filledEducation.length) {
      setError("请至少填写一条教育经历（学校名称）");
      return;
    }
    if (!skills.length) {
      setError("请至少添加一项专业技能");
      return;
    }
    setError("");

    const resume = blankResume();
    const facts: Fact[] = [];
    const addFact = (category: string, statement: string, location: string) => {
      if (!statement.trim()) return null;
      const id = newId();
      facts.push({
        id,
        category,
        statement: statement.trim(),
        source_type: "manual",
        source_location: location,
        user_confirmed: true,
      });
      return id;
    };

    resume.basics.name = basics.name.trim();
    resume.basics.gender = basics.gender.trim();
    resume.basics.birthday = basics.birthday.trim();
    resume.basics.phone = basics.phone.trim();
    resume.basics.email = basics.email.trim();
    resume.basics.location = basics.location.trim();
    resume.basics.wechat = basics.wechat.trim();
    resume.basics.political_status = basics.political_status.trim();
    resume.basics.photo_data_url = basics.photo_data_url;
    resume.basics.target_role = sourcedText(basics.target_role.trim());
    addFact("基本信息", `${basics.name.trim()}，期望职位：${basics.target_role.trim()}`, "基本信息");
    if (basics.gender.trim()) addFact("基本信息", `性别：${basics.gender.trim()}`, "基本信息");
    if (basics.birthday.trim()) addFact("基本信息", `生日：${basics.birthday.trim()}`, "基本信息");
    if (basics.political_status.trim()) addFact("基本信息", `政治面貌：${basics.political_status.trim()}`, "基本信息");
    if (basics.photo_data_url) addFact("基本信息", "已上传证件照", "基本信息");

    for (const item of filledEducation) {
      const line = [item.institution, item.degree, item.field, [item.start_date, item.end_date].filter(Boolean).join(" ~ ")]
        .filter(Boolean)
        .join(" · ");
      const factId = addFact("教育经历", line, "教育经历");
      const highlights = item.highlight.trim()
        ? [{ ...sourcedText(item.highlight.trim()), source_fact_ids: factId ? [factId] : [] }]
        : [];
      resume.education.push({
        id: item.id,
        institution: item.institution.trim(),
        degree: item.degree.trim(),
        field: item.field.trim(),
        start_date: item.start_date.trim(),
        end_date: item.end_date.trim(),
        highlights,
      });
      if (item.highlight.trim()) addFact("教育经历", item.highlight.trim(), "教育亮点");
    }

    for (const item of work.filter((entry) => entry.company.trim() || entry.title.trim())) {
      const narrative = item.narrative.trim();
      const header = [item.company, item.title, [item.start_date, item.end_date].filter(Boolean).join(" ~ ")]
        .filter(Boolean)
        .join(" · ");
      const headerFact = addFact("工作/实习经历", header, "工作经历");
      const narrativeFact = narrative ? addFact("工作/实习经历", narrative, "工作经历描述") : null;
      resume.work_experience.push({
        id: item.id,
        company: item.company.trim() || "未命名公司",
        title: item.title.trim() || basics.target_role.trim(),
        start_date: item.start_date.trim(),
        end_date: item.end_date.trim(),
        bullets: [{
          ...sourcedText(narrative || header),
          source_fact_ids: [narrativeFact, headerFact].filter(Boolean) as string[],
        }],
      });
    }

    for (const item of projects.filter((entry) => entry.name.trim())) {
      const narrative = item.narrative.trim();
      const header = [item.name, item.role, [item.start_date, item.end_date].filter(Boolean).join(" ~ ")]
        .filter(Boolean)
        .join(" · ");
      const headerFact = addFact("项目经历", header, "项目经历");
      const narrativeFact = narrative ? addFact("项目经历", narrative, "项目经历描述") : null;
      resume.projects.push({
        id: item.id,
        name: item.name.trim(),
        role: item.role.trim(),
        start_date: item.start_date.trim(),
        end_date: item.end_date.trim(),
        bullets: [{
          ...sourcedText(narrative || header),
          source_fact_ids: [narrativeFact, headerFact].filter(Boolean) as string[],
        }],
      });
    }

    const skillFact = addFact("专业技能", skills.join("、"), "专业技能");
    resume.skills.push({
      id: newId(),
      name: "专业技能",
      items: skills.map((item) => ({ ...sourcedText(item), source_fact_ids: skillFact ? [skillFact] : [] })),
    });

    onCreate(resume, facts);
  }

  if (mode === "choose") {
    return (
      <section className="intake-panel">
        <div className="panel-heading"><div><span className="panel-index">01</span><h2>建立事实底稿</h2></div></div>
        <p className="panel-note">上传后优先沿用原简历的字体、颜色与布局线索；也可以先把经历尽量写全，后续由 AI 按 JD 筛选润色（须你同意）。</p>
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
            <span>结构化输入</span><strong>从经历开始</strong><small>实习/工作/项目/技能可无限添加，AI 稍后按 JD 筛选</small>
          </button>
        </div>
      </section>
    );
  }

  return (
    <form className="manual-intake" onSubmit={submit}>
      <div className="panel-heading">
        <div><span className="panel-index">01</span><h2>填写个人简历信息</h2></div>
        <button type="button" className="text-button" onClick={() => setMode("choose")}>返回</button>
      </div>
      <p className="panel-note">像招聘平台一样分栏填写，条目可随时继续添加。先写全素材库，投递某岗位时再由 AI 筛选与润色，并经你逐项同意。</p>

      <section className="intake-section">
        <div className="intake-section-head">
          <h3>基本信息</h3>
          <small>姓名与期望职位必填；证件照、生日等建议填全</small>
        </div>
        <div className="basics-editor">
          <div className="photo-uploader">
            {basics.photo_data_url ? (
              <img src={basics.photo_data_url} alt="证件照预览" className="photo-preview" />
            ) : (
              <div className="photo-placeholder">证件照</div>
            )}
            <label className="secondary-button photo-upload-button">
              {basics.photo_data_url ? "更换照片" : "上传证件照"}
              <input
                type="file"
                accept="image/*"
                hidden
                aria-label="上传证件照"
                onChange={(event: ChangeEvent<HTMLInputElement>) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (!file) return;
                  void encodeResumePhoto(file)
                    .then((photo_data_url) => setBasics({ ...basics, photo_data_url }))
                    .catch((error: unknown) => setError(error instanceof Error ? error.message : "上传证件照失败"));
                }}
              />
            </label>
            {basics.photo_data_url && (
              <button type="button" className="text-button" onClick={() => setBasics({ ...basics, photo_data_url: "" })}>
                移除照片
              </button>
            )}
          </div>
          <div className="intake-grid">
            <label>姓名<input required aria-label="姓名" value={basics.name} onChange={(event) => setBasics({ ...basics, name: event.target.value })} placeholder="例：张三" /></label>
            <label>期望职位<input required aria-label="期望职位" value={basics.target_role} onChange={(event) => setBasics({ ...basics, target_role: event.target.value })} placeholder="例：后端开发工程师" /></label>
            <label>性别
              <AppleSelect aria-label="性别" value={basics.gender} options={GENDER_OPTIONS} onChange={(gender) => setBasics({ ...basics, gender })} />
            </label>
            <label>生日
              <AppleDateParts aria-label="生日" precision="day" minYear={1960} value={basics.birthday} onChange={(birthday) => setBasics({ ...basics, birthday })} />
            </label>
            <label>政治面貌
              <AppleSelect aria-label="政治面貌" value={basics.political_status} options={POLITICAL_OPTIONS} onChange={(political_status) => setBasics({ ...basics, political_status })} />
            </label>
            <label>所在城市<input aria-label="所在城市" value={basics.location} onChange={(event) => setBasics({ ...basics, location: event.target.value })} placeholder="例：上海" /></label>
            <label>手机号<input aria-label="手机号" value={basics.phone} onChange={(event) => setBasics({ ...basics, phone: event.target.value })} placeholder="选填" /></label>
            <label>邮箱<input aria-label="邮箱" type="email" value={basics.email} onChange={(event) => setBasics({ ...basics, email: event.target.value })} placeholder="选填" /></label>
            <label>微信<input aria-label="微信" value={basics.wechat} onChange={(event) => setBasics({ ...basics, wechat: event.target.value })} placeholder="选填" /></label>
          </div>
        </div>
      </section>

      <section className="intake-section">
        <div className="intake-section-head">
          <h3>教育经历</h3>
          <button type="button" className="text-button" onClick={() => setEducation([...education, emptyEducation()])}>+ 添加教育</button>
        </div>
        {education.map((item, index) => (
          <div className="intake-card" key={item.id}>
            <div className="intake-card-head">
              <strong>教育 {index + 1}</strong>
              {education.length > 1 && (
                <button type="button" className="text-button" onClick={() => setEducation(education.filter((entry) => entry.id !== item.id))}>删除</button>
              )}
            </div>
            <div className="intake-grid">
              <label>学校名称<input required={index === 0} aria-label={`学校名称 ${index + 1}`} value={item.institution} onChange={(event) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, institution: event.target.value } : entry))} placeholder="例：某某大学" /></label>
              <label>学历
                <AppleSelect
                  aria-label={`学历 ${index + 1}`}
                  value={item.degree}
                  options={DEGREE_OPTIONS.map((degree) => ({ value: degree, label: degree }))}
                  onChange={(degree) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, degree } : entry))}
                />
              </label>
              <label>专业<input aria-label={`专业 ${index + 1}`} value={item.field} onChange={(event) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, field: event.target.value } : entry))} placeholder="例：计算机科学与技术" /></label>
              <label>入学时间
                <AppleDateParts
                  aria-label={`入学时间 ${index + 1}`}
                  precision="month"
                  value={item.start_date}
                  onChange={(start_date) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, start_date } : entry))}
                />
              </label>
              <label>毕业时间
                <AppleDateParts
                  aria-label={`毕业时间 ${index + 1}`}
                  precision="month"
                  value={item.end_date}
                  onChange={(end_date) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, end_date } : entry))}
                />
              </label>
              <label className="intake-wide">在校亮点<small>选填，一句话</small>
                <input aria-label={`在校亮点 ${index + 1}`} value={item.highlight} onChange={(event) => setEducation(education.map((entry) => entry.id === item.id ? { ...entry, highlight: event.target.value } : entry))} placeholder="例：GPA 3.7 / 4.0，获得校级奖学金" />
              </label>
            </div>
          </div>
        ))}
      </section>

      <section className="intake-section">
        <div className="intake-section-head">
          <h3>工作 / 实习经历</h3>
          <button type="button" className="text-button" onClick={() => setWork([...work, emptyWork()])}>+ 添加经历</button>
        </div>
        {work.map((item, index) => (
          <div className="intake-card" key={item.id}>
            <div className="intake-card-head">
              <strong>经历 {index + 1}</strong>
              {work.length > 1 && (
                <button type="button" className="text-button" onClick={() => setWork(work.filter((entry) => entry.id !== item.id))}>删除</button>
              )}
            </div>
            <div className="intake-grid">
              <label>公司名称<input aria-label={`公司名称 ${index + 1}`} value={item.company} onChange={(event) => setWork(work.map((entry) => entry.id === item.id ? { ...entry, company: event.target.value } : entry))} placeholder="例：示例科技" /></label>
              <label>职位名称<input aria-label={`职位名称 ${index + 1}`} value={item.title} onChange={(event) => setWork(work.map((entry) => entry.id === item.id ? { ...entry, title: event.target.value } : entry))} placeholder="例：后端开发实习生" /></label>
              <label>开始时间
                <AppleDateParts
                  aria-label={`工作开始时间 ${index + 1}`}
                  precision="day"
                  value={item.start_date}
                  onChange={(start_date) => setWork(work.map((entry) => entry.id === item.id ? { ...entry, start_date } : entry))}
                />
              </label>
              <label>结束时间
                <AppleDateParts
                  aria-label={`工作结束时间 ${index + 1}`}
                  precision="day"
                  value={item.end_date}
                  onChange={(end_date) => setWork(work.map((entry) => entry.id === item.id ? { ...entry, end_date } : entry))}
                />
              </label>
            </div>
            <label className="intake-wide narrative-field">
              <span>经历描述</span>
              <textarea
                aria-label={`工作经历描述 ${index + 1}`}
                rows={6}
                value={item.narrative}
                onChange={(event) => setWork(work.map((entry) => entry.id === item.id ? { ...entry, narrative: event.target.value } : entry))}
                placeholder="尽量详细写你做了什么、怎么做的、结果如何。后续 AI 会按 JD 筛选润色。"
              />
            </label>
          </div>
        ))}
      </section>

      <section className="intake-section">
        <div className="intake-section-head">
          <h3>项目经历</h3>
          <button type="button" className="text-button" onClick={() => setProjects([...projects, emptyProject()])}>+ 添加项目</button>
        </div>
        {projects.map((item, index) => (
          <div className="intake-card" key={item.id}>
            <div className="intake-card-head">
              <strong>项目 {index + 1}</strong>
              {projects.length > 1 && (
                <button type="button" className="text-button" onClick={() => setProjects(projects.filter((entry) => entry.id !== item.id))}>删除</button>
              )}
            </div>
            <div className="intake-grid">
              <label>项目名称<input aria-label={`项目名称 ${index + 1}`} value={item.name} onChange={(event) => setProjects(projects.map((entry) => entry.id === item.id ? { ...entry, name: event.target.value } : entry))} placeholder="例：简历证据工作台" /></label>
              <label>担任角色<input aria-label={`项目角色 ${index + 1}`} value={item.role} onChange={(event) => setProjects(projects.map((entry) => entry.id === item.id ? { ...entry, role: event.target.value } : entry))} placeholder="例：后端负责人" /></label>
              <label>开始时间
                <AppleDateParts
                  aria-label={`项目开始时间 ${index + 1}`}
                  precision="day"
                  value={item.start_date}
                  onChange={(start_date) => setProjects(projects.map((entry) => entry.id === item.id ? { ...entry, start_date } : entry))}
                />
              </label>
              <label>结束时间
                <AppleDateParts
                  aria-label={`项目结束时间 ${index + 1}`}
                  precision="day"
                  value={item.end_date}
                  onChange={(end_date) => setProjects(projects.map((entry) => entry.id === item.id ? { ...entry, end_date } : entry))}
                />
              </label>
            </div>
            <label className="intake-wide narrative-field">
              <span>经历描述</span>
              <textarea
                aria-label={`项目经历描述 ${index + 1}`}
                rows={6}
                value={item.narrative}
                onChange={(event) => setProjects(projects.map((entry) => entry.id === item.id ? { ...entry, narrative: event.target.value } : entry))}
                placeholder="尽量详细写你做了什么、怎么做的、结果如何。后续 AI 会按 JD 筛选润色。"
              />
            </label>
          </div>
        ))}
      </section>

      <section className="intake-section">
        <div className="intake-section-head">
          <h3>专业技能</h3>
          <small>回车或逗号添加标签</small>
        </div>
        <div className="skill-composer">
          <input
            aria-label="添加专业技能"
            value={skillInput}
            onChange={(event) => setSkillInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === "," || event.key === "、") {
                event.preventDefault();
                addSkillTokens(skillInput);
              }
            }}
            onBlur={() => { if (skillInput.trim()) addSkillTokens(skillInput); }}
            placeholder="输入后回车，例：Python"
          />
          <button type="button" className="secondary-button" onClick={() => addSkillTokens(skillInput)}>添加</button>
        </div>
        {skills.length > 0 && (
          <div className="skill-chips" aria-label="已添加技能">
            {skills.map((skill) => (
              <button key={skill} type="button" className="skill-chip" onClick={() => setSkills(skills.filter((item) => item !== skill))}>
                {skill}<span aria-hidden="true">×</span>
              </button>
            ))}
          </div>
        )}
      </section>

      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? "正在保存…" : "保存事实并生成初稿"}</button>
    </form>
  );
}
