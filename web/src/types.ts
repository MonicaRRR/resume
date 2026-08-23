import { z } from "zod";

export const ApplicationTypeSchema = z.enum(["campus", "internship", "experienced"]);
export type ApplicationType = z.infer<typeof ApplicationTypeSchema>;

export const SourcedTextSchema = z.object({
  value: z.string(),
  source_fact_ids: z.array(z.string()),
  origin: z.enum(["upload", "questionnaire", "manual", "ai_rewrite"]),
  confidence: z.number(),
});
export type SourcedText = z.infer<typeof SourcedTextSchema>;

const EducationSchema = z.object({
  id: z.string(), institution: z.string(), degree: z.string(), field: z.string(),
  start_date: z.string(), end_date: z.string(), highlights: z.array(SourcedTextSchema),
});
const WorkSchema = z.object({
  id: z.string(), company: z.string(), title: z.string(), start_date: z.string(), end_date: z.string(),
  bullets: z.array(SourcedTextSchema),
});
const ProjectEntrySchema = z.object({
  id: z.string(), name: z.string(), role: z.string(), start_date: z.string(), end_date: z.string(),
  bullets: z.array(SourcedTextSchema),
});
const SkillGroupSchema = z.object({ id: z.string(), name: z.string(), items: z.array(SourcedTextSchema) });
const NamedEntrySchema = z.object({ id: z.string(), name: z.string(), detail: SourcedTextSchema, date: z.string() });
const CustomSectionSchema = z.object({ id: z.string(), title: z.string(), items: z.array(SourcedTextSchema) });

export const ResumeSchema = z.object({
  basics: z.object({
    name: z.string(), email: z.string(), phone: z.string(), location: z.string(),
    target_role: SourcedTextSchema, summary: SourcedTextSchema,
  }),
  education: z.array(EducationSchema),
  work_experience: z.array(WorkSchema),
  projects: z.array(ProjectEntrySchema),
  skills: z.array(SkillGroupSchema),
  certificates: z.array(NamedEntrySchema),
  awards: z.array(NamedEntrySchema),
  custom_sections: z.array(CustomSectionSchema),
  section_order: z.array(z.string()),
  layout_profile: z.object({
    source_kind: z.enum(["builtin", "docx", "pdf", "txt"]),
    font_family: z.string(), heading_font_family: z.string(), accent_color: z.string(),
    base_font_size: z.number().nullable(), line_height: z.number().nullable(),
    columns: z.number(), imported: z.boolean(),
  }),
});
export type ResumeDocument = z.infer<typeof ResumeSchema>;

export const FactSchema = z.object({
  id: z.string(), category: z.string(), statement: z.string(),
  source_type: z.enum(["upload", "questionnaire", "manual"]),
  source_location: z.string(), user_confirmed: z.boolean(),
});
export type Fact = z.infer<typeof FactSchema>;

const RequirementSchema = z.object({
  id: z.string(), text: z.string(), evidence_quote: z.string(), weight: z.number(), inferred: z.boolean(),
});
export const JobAnalysisSchema = z.object({
  role_title: z.string(), seniority: z.string(), responsibilities: z.array(z.string()),
  requirements: z.array(RequirementSchema), bonus_skills: z.array(z.string()), keywords: z.array(z.string()),
  interview_topics: z.array(z.string()), written_topics: z.array(z.string()),
});
export type JobAnalysis = z.infer<typeof JobAnalysisSchema>;

export const ProjectSchema = z.object({
  id: z.string(), title: z.string(), company_name: z.string(), application_type: ApplicationTypeSchema,
  job_description: z.string(), job_analysis: JobAnalysisSchema.nullable(),
  active_resume_version_id: z.string().nullable(), selected_template_id: z.string(),
  created_at: z.string(), updated_at: z.string(),
});
export type Project = z.infer<typeof ProjectSchema>;
export const ProjectListSchema = z.array(ProjectSchema);

export const ResumeVersionSchema = z.object({
  id: z.string(), project_id: z.string(), resume: ResumeSchema, facts: z.array(FactSchema),
  reason: z.string(), created_at: z.string(),
});
export type ResumeVersion = z.infer<typeof ResumeVersionSchema>;

export const ImportResultSchema = z.object({
  resume: ResumeSchema, facts: z.array(FactSchema), layout_profile: ResumeSchema.shape.layout_profile,
  quality_score: z.number(), warnings: z.array(z.string()), version_id: z.string(),
});

export const PatchOperationSchema = z.object({
  id: z.string(), op: z.enum(["replace", "reorder"]), path: z.string(), before: z.unknown(), after: z.unknown(),
  reason: z.string(), jd_requirement_ids: z.array(z.string()), source_fact_ids: z.array(z.string()),
  risk: z.enum(["low", "medium", "high"]),
});
export const ResumePatchSchema = z.object({ operations: z.array(PatchOperationSchema) });
export type ResumePatch = z.infer<typeof ResumePatchSchema>;

export const MatchReportSchema = z.object({
  coverage: z.number(),
  items: z.array(z.object({
    requirement_id: z.string(), requirement: z.string(), status: z.enum(["已有证据", "证据较弱", "没有证据"]),
    fact_ids: z.array(z.string()), excerpts: z.array(z.string()), weight: z.number(),
  })),
});
export type MatchReport = z.infer<typeof MatchReportSchema>;

export const FollowupQuestionSchema = z.object({
  id: z.string(), question: z.string(), topic: z.string(), requirement_id: z.string(),
  rationale: z.string(), skippable: z.boolean(),
});

export const ProviderSettingsSchema = z.object({
  kind: z.string(), base_url: z.string(), model: z.string(), timeout: z.number(), temperature: z.number(),
  configured: z.boolean(), codex_confirmed: z.boolean(),
});
export type ProviderSettings = z.infer<typeof ProviderSettingsSchema>;

const PracticeQuestionSchema = z.object({
  id: z.string(), category: z.string(), prompt: z.string(), hint: z.string(), explanation: z.string().nullable(),
  requirement_ids: z.array(z.string()), fact_ids: z.array(z.string()),
});
const PracticeFeedbackSchema = z.object({
  dimensions: z.record(z.string(), z.string()), summary: z.string(), improved_answer: z.string(),
  weaknesses: z.array(z.string()), percentage_score: z.null(),
});
export const PracticeSessionSchema = z.object({
  id: z.string(), project_id: z.string(), kind: z.enum(["interview", "written"]),
  status: z.enum(["active", "completed"]), current_question: PracticeQuestionSchema.nullable(),
  turns: z.array(z.object({
    id: z.string(), question: PracticeQuestionSchema, answer: z.string(), feedback: PracticeFeedbackSchema,
    explanation: z.string(), follow_up: z.string(), answered_at: z.string(),
  })),
  weaknesses: z.array(z.string()), created_at: z.string(), updated_at: z.string(),
});
export type PracticeSession = z.infer<typeof PracticeSessionSchema>;

export type ProjectCreateInput = {
  title: string;
  company_name: string;
  application_type: ApplicationType;
  job_description: string;
};
