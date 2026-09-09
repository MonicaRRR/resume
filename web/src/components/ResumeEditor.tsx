import type { ClipboardEvent, ChangeEvent, ReactNode } from "react";

import { encodeResumePhoto } from "../lib/encodeResumePhoto";
import { tidyPasteArtifacts } from "../lib/tidyPasteArtifacts";
import { sourcedText } from "../resume";
import type { ResumeDocument, SourcedText } from "../types";
import { AppleDateParts } from "./ui/AppleDateParts";
import { AppleSelect } from "./ui/AppleSelect";


const DEGREE_OPTIONS = [
  "高中",
  "专科",
  "本科",
  "硕士",
  "博士",
  "MBA",
  "其他",
].map((degree) => ({ value: degree, label: degree }));

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


function narrativeFromBullets(bullets: SourcedText[]): string {
  if (bullets.length <= 1) return bullets[0]?.value ?? "";
  return bullets.map((bullet) => bullet.value).join("\n");
}


function bulletsFromNarrative(text: string, previous: SourcedText[]): SourcedText[] {
  const first = previous[0];
  return [{
    value: text,
    source_fact_ids: first?.source_fact_ids ?? [],
    origin: "manual",
    confidence: first?.confidence ?? 1,
  }];
}


function pasteTidied(
  event: ClipboardEvent<HTMLTextAreaElement>,
  current: string,
  onChange: (value: string) => void,
) {
  const raw = event.clipboardData.getData("text");
  const tidied = tidyPasteArtifacts(raw);
  if (tidied === raw) return;
  event.preventDefault();
  const target = event.currentTarget;
  const start = target.selectionStart ?? current.length;
  const end = target.selectionEnd ?? current.length;
  onChange(`${current.slice(0, start)}${tidied}${current.slice(end)}`);
}


type BasicsTextKey = "name" | "email" | "phone" | "location" | "wechat" | "gender" | "birthday" | "political_status";


export function ResumeEditor({ resume, onChange, onSave, onDiscard, busy = false }: {
  resume: ResumeDocument;
  onChange: (resume: ResumeDocument) => void;
  onSave: () => void;
  onDiscard: () => void;
  busy?: boolean;
}) {
  const updateBasics = (key: BasicsTextKey, value: string) => {
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

  const commit = (mutator: (draft: ResumeDocument) => void) => {
    const next = structuredClone(resume);
    mutator(next);
    onChange(next);
  };

  const onPhotoChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const photo = await encodeResumePhoto(file);
      commit((draft) => { draft.basics.photo_data_url = photo; });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "上传证件照失败");
    }
  };

  return (
    <section className="resume-editor">
      <div className="panel-heading">
        <div><span className="panel-index">库</span><h2>经历素材库</h2></div>
        <span>可无限添加；AI 只建议筛选与润色</span>
      </div>
      <p className="panel-note">
        尽量把实习、工作、项目和技能都写进来。针对某份 JD 时，AI 会提出筛选、润色与适配建议，
        <strong>未经你勾选同意不会改简历</strong>。基础信息请尽量填全，证件照会出现在导出简历页眉。
      </p>

      <div className="basics-editor">
        <div className="photo-uploader">
          {resume.basics.photo_data_url ? (
            <img src={resume.basics.photo_data_url} alt="证件照预览" className="photo-preview" />
          ) : (
            <div className="photo-placeholder">证件照</div>
          )}
          <label className="secondary-button photo-upload-button">
            {resume.basics.photo_data_url ? "更换照片" : "上传证件照"}
            <input type="file" accept="image/*" hidden onChange={(event) => void onPhotoChange(event)} />
          </label>
          {resume.basics.photo_data_url && (
            <button type="button" className="text-button" onClick={() => commit((draft) => { draft.basics.photo_data_url = ""; })}>
              移除照片
            </button>
          )}
        </div>
        <div className="editor-grid">
          <label>姓名<input value={resume.basics.name} onChange={(event) => updateBasics("name", event.target.value)} /></label>
          <label>目标岗位<input value={resume.basics.target_role.value} onChange={(event) => updateSourced("target_role", event.target.value)} /></label>
          <label>性别
            <AppleSelect
              aria-label="性别"
              value={resume.basics.gender}
              options={GENDER_OPTIONS}
              onChange={(gender) => updateBasics("gender", gender)}
            />
          </label>
          <label>生日
            <AppleDateParts
              aria-label="生日"
              precision="day"
              minYear={1960}
              value={resume.basics.birthday}
              onChange={(birthday) => updateBasics("birthday", birthday)}
            />
          </label>
          <label>政治面貌
            <AppleSelect
              aria-label="政治面貌"
              value={resume.basics.political_status}
              options={
                resume.basics.political_status
                  && !POLITICAL_OPTIONS.some((option) => option.value === resume.basics.political_status)
                  ? [...POLITICAL_OPTIONS, { value: resume.basics.political_status, label: resume.basics.political_status }]
                  : POLITICAL_OPTIONS
              }
              onChange={(political_status) => updateBasics("political_status", political_status)}
            />
          </label>
          <label>现居城市<input value={resume.basics.location} onChange={(event) => updateBasics("location", event.target.value)} placeholder="例：上海" /></label>
          <label>电话<input value={resume.basics.phone} onChange={(event) => updateBasics("phone", event.target.value)} /></label>
          <label>邮箱<input value={resume.basics.email} onChange={(event) => updateBasics("email", event.target.value)} /></label>
          <label>微信<input value={resume.basics.wechat} onChange={(event) => updateBasics("wechat", event.target.value)} placeholder="选填" /></label>
          <label className="editor-wide">个人概述<textarea rows={3} value={resume.basics.summary.value} onChange={(event) => updateSourced("summary", event.target.value)} onPaste={(event) => pasteTidied(event, resume.basics.summary.value, (value) => updateSourced("summary", value))} placeholder="可留空，交给 AI 基于事实起草后再由你确认" /></label>
        </div>
      </div>

      <EditorSection
        title="教育经历"
        onAdd={() => commit((draft) => {
          draft.education.push({
            id: newId(), institution: "", degree: "本科", field: "", start_date: "", end_date: "", highlights: [],
          });
        })}
      >
        {resume.education.map((item, index) => (
          <div className="intake-card" key={item.id}>
            <div className="intake-card-head">
              <strong>教育 {index + 1}</strong>
              <button type="button" className="text-button" onClick={() => commit((draft) => { draft.education = draft.education.filter((entry) => entry.id !== item.id); })}>删除</button>
            </div>
            <div className="intake-grid">
              <label>学校<input value={item.institution} onChange={(event) => commit((draft) => { draft.education[index].institution = event.target.value; })} /></label>
              <label>学历
                <AppleSelect
                  aria-label={`学历 ${index + 1}`}
                  value={DEGREE_OPTIONS.some((option) => option.value === item.degree) ? item.degree : (item.degree || "本科")}
                  options={
                    item.degree && !DEGREE_OPTIONS.some((option) => option.value === item.degree)
                      ? [...DEGREE_OPTIONS, { value: item.degree, label: item.degree }]
                      : DEGREE_OPTIONS
                  }
                  onChange={(degree) => commit((draft) => { draft.education[index].degree = degree; })}
                />
              </label>
              <label>专业<input value={item.field} onChange={(event) => commit((draft) => { draft.education[index].field = event.target.value; })} /></label>
              <label>入学时间
                <AppleDateParts
                  aria-label={`入学时间 ${index + 1}`}
                  precision="month"
                  value={item.start_date}
                  onChange={(start_date) => commit((draft) => { draft.education[index].start_date = start_date; })}
                />
              </label>
              <label>毕业时间
                <AppleDateParts
                  aria-label={`毕业时间 ${index + 1}`}
                  precision="month"
                  value={item.end_date}
                  onChange={(end_date) => commit((draft) => { draft.education[index].end_date = end_date; })}
                />
              </label>
            </div>
          </div>
        ))}
      </EditorSection>

      <EditorSection
        title="专业技能"
        onAdd={() => commit((draft) => {
          if (!draft.skills.length) {
            draft.skills.push({ id: newId(), name: "专业技能", items: [] });
          }
          draft.skills[0].items.push(sourcedText(""));
        })}
      >
        <p className="panel-note">
          不要只写「Python / SQL」。按类别拆开，并补上场景或栈，例如「后端：Python、FastAPI；数据：SQL、Pandas；工具：Git、Linux」。
        </p>
        {(resume.skills[0]?.items ?? []).map((item, index) => (
          <div className="bullet-row" key={`skill-item-${index}`}>
            <span>{index + 1}</span>
            <input
              aria-label={`技能 ${index + 1}`}
              value={item.value}
              onChange={(event) => commit((draft) => {
                if (!draft.skills[0]) draft.skills.push({ id: newId(), name: "专业技能", items: [] });
                const target = draft.skills[0].items[index] ?? sourcedText("");
                target.value = event.target.value;
                target.origin = "manual";
                draft.skills[0].items[index] = target;
              })}
              placeholder="例：后端：Python、FastAPI、PostgreSQL"
            />
            <button
              type="button"
              className="text-button"
              onClick={() => commit((draft) => {
                if (!draft.skills[0]) return;
                draft.skills[0].items = draft.skills[0].items.filter((_, itemIndex) => itemIndex !== index);
              })}
            >
              删
            </button>
          </div>
        ))}
        {!resume.skills[0]?.items.length && <p className="panel-note">还没有技能条目，点击「添加」开始填写。</p>}
      </EditorSection>

      <EditorSection
        title="实习工作经历"
        onAdd={() => commit((draft) => {
          draft.work_experience.push({
            id: newId(), company: "", title: "", start_date: "", end_date: "", bullets: [sourcedText("")],
          });
        })}
      >
        {resume.work_experience.map((item, entryIndex) => (
          <ExperienceCard
            key={item.id}
            title={`经历 ${entryIndex + 1}`}
            heading={(
              <div className="intake-grid">
                <label>公司<input value={item.company} onChange={(event) => commit((draft) => { draft.work_experience[entryIndex].company = event.target.value; })} /></label>
                <label>职位<input value={item.title} onChange={(event) => commit((draft) => { draft.work_experience[entryIndex].title = event.target.value; })} /></label>
                <label>开始时间
                  <AppleDateParts
                    aria-label={`工作开始时间 ${entryIndex + 1}`}
                    precision="day"
                    value={item.start_date}
                    onChange={(start_date) => commit((draft) => { draft.work_experience[entryIndex].start_date = start_date; })}
                  />
                </label>
                <label>结束时间
                  <AppleDateParts
                    aria-label={`工作结束时间 ${entryIndex + 1}`}
                    precision="day"
                    value={item.end_date}
                    onChange={(end_date) => commit((draft) => { draft.work_experience[entryIndex].end_date = end_date; })}
                  />
                </label>
              </div>
            )}
            narrative={narrativeFromBullets(item.bullets)}
            onDelete={() => commit((draft) => { draft.work_experience = draft.work_experience.filter((entry) => entry.id !== item.id); })}
            onChangeNarrative={(value) => commit((draft) => {
              draft.work_experience[entryIndex].bullets = bulletsFromNarrative(value, draft.work_experience[entryIndex].bullets);
            })}
          />
        ))}
      </EditorSection>

      <EditorSection
        title="项目经历"
        onAdd={() => commit((draft) => {
          draft.projects.push({
            id: newId(), name: "", role: "", start_date: "", end_date: "", bullets: [sourcedText("")],
          });
        })}
      >
        {resume.projects.map((item, entryIndex) => (
          <ExperienceCard
            key={item.id}
            title={`项目 ${entryIndex + 1}`}
            heading={(
              <div className="intake-grid">
                <label>项目名<input value={item.name} onChange={(event) => commit((draft) => { draft.projects[entryIndex].name = event.target.value; })} /></label>
                <label>角色<input value={item.role} onChange={(event) => commit((draft) => { draft.projects[entryIndex].role = event.target.value; })} /></label>
                <label>开始时间
                  <AppleDateParts
                    aria-label={`项目开始时间 ${entryIndex + 1}`}
                    precision="day"
                    value={item.start_date}
                    onChange={(start_date) => commit((draft) => { draft.projects[entryIndex].start_date = start_date; })}
                  />
                </label>
                <label>结束时间
                  <AppleDateParts
                    aria-label={`项目结束时间 ${entryIndex + 1}`}
                    precision="day"
                    value={item.end_date}
                    onChange={(end_date) => commit((draft) => { draft.projects[entryIndex].end_date = end_date; })}
                  />
                </label>
              </div>
            )}
            narrative={narrativeFromBullets(item.bullets)}
            onDelete={() => commit((draft) => { draft.projects = draft.projects.filter((entry) => entry.id !== item.id); })}
            onChangeNarrative={(value) => commit((draft) => {
              draft.projects[entryIndex].bullets = bulletsFromNarrative(value, draft.projects[entryIndex].bullets);
            })}
          />
        ))}
      </EditorSection>

      <div className="button-row">
        <button type="button" className="primary-button" disabled={busy} onClick={onSave}>保存素材库为新版本</button>
        <button type="button" className="secondary-button" onClick={onDiscard}>放弃未保存改动</button>
      </div>
    </section>
  );
}


function EditorSection({ title, onAdd, children }: { title: string; onAdd: () => void; children: ReactNode }) {
  return (
    <div className="editor-section">
      <div className="intake-section-head">
        <h3>{title}</h3>
        <button type="button" className="text-button" onClick={onAdd}>+ 添加</button>
      </div>
      {children}
    </div>
  );
}


function ExperienceCard({
  title,
  heading,
  narrative,
  onDelete,
  onChangeNarrative,
}: {
  title: string;
  heading: ReactNode;
  narrative: string;
  onDelete: () => void;
  onChangeNarrative: (value: string) => void;
}) {
  return (
    <div className="intake-card">
      <div className="intake-card-head">
        <strong>{title}</strong>
        <button type="button" className="text-button" onClick={onDelete}>删除</button>
      </div>
      {heading}
      <label className="intake-wide narrative-field">
        <span>经历描述</span>
        <textarea
          aria-label={`${title} 经历描述`}
          rows={6}
          value={narrative}
          onChange={(event) => onChangeNarrative(event.target.value)}
          onPaste={(event) => pasteTidied(event, narrative, onChangeNarrative)}
          placeholder="尽量详细写你做了什么、怎么做的、结果如何。后续 AI 会按 JD 筛选润色。"
        />
      </label>
    </div>
  );
}
