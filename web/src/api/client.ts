import { z } from "zod";

import {
  FollowupQuestionSchema,
  ImportResultSchema,
  JobAnalysisSchema,
  MatchReportSchema,
  OptimizationRunSchema,
  PracticeSessionSchema,
  ProjectListSchema,
  ProjectSchema,
  ProviderSettingsSchema,
  CodexDetectSchema,
  ResumePatchSchema,
  PatchDiscussionResultSchema,
  ResumeSchema,
  FactSchema,
  ResumeVersionSchema,
  type OptimizationMode,
  type ProjectCreateInput,
  type ResumeDocument,
  type Fact,
  type ResumePatch,
} from "../types";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(detail?.code ?? "REQUEST_FAILED", detail?.message ?? "本地服务请求失败", response.status);
  }
  return schema.parse(payload);
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const api = {
  listProjects: () => request("/api/projects", ProjectListSchema),
  getProject: (id: string) => request(`/api/projects/${id}`, ProjectSchema),
  createProject: (input: ProjectCreateInput) => request("/api/projects", ProjectSchema, json("POST", input)),
  updateProject: (id: string, input: Record<string, unknown>) => request(`/api/projects/${id}`, ProjectSchema, json("PATCH", input)),
  deleteProject: async (id: string) => {
    const response = await fetch(`/api/projects/${id}`, { method: "DELETE" });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const detail = payload?.detail;
      throw new ApiError(detail?.code ?? "REQUEST_FAILED", detail?.message ?? "删除项目失败", response.status);
    }
  },
  getVersions: (id: string) => request(`/api/projects/${id}/versions`, z.array(ResumeVersionSchema)),
  activateVersion: (projectId: string, versionId: string) => request(`/api/projects/${projectId}/versions/${versionId}/activate`, ProjectSchema, { method: "POST" }),
  importResume: async (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request(`/api/projects/${id}/resume/import`, ImportResultSchema, { method: "POST", body });
  },
  saveResume: (id: string, resume: ResumeDocument, facts: Fact[], reason = "手动保存") =>
    request(`/api/projects/${id}/resume`, ResumeVersionSchema, json("PUT", { resume, facts, reason })),
  restoreFromProfile: (id: string) =>
    request(`/api/projects/${id}/resume/restore-from-profile`, ResumeVersionSchema, { method: "POST" }),
  analyzeJob: (id: string, provider: string) => request(`/api/projects/${id}/analyze-jd`, JobAnalysisSchema, json("POST", { provider })),
  getMatch: (id: string) => request(`/api/projects/${id}/match`, MatchReportSchema),
  refreshMatch: (id: string, provider: string) => request(`/api/projects/${id}/match`, MatchReportSchema, json("POST", { provider })),
  getQuestions: (id: string, provider: string) => request(`/api/projects/${id}/questions`, z.array(FollowupQuestionSchema), json("POST", { provider })),
  addFact: (id: string, statement: string, category = "补充回答") => request(`/api/projects/${id}/facts`, ResumeVersionSchema, json("POST", { statement, category, source_type: "questionnaire", user_confirmed: true })),
  suggestPatch: (id: string, provider: string) => request(`/api/projects/${id}/resume/suggest`, ResumePatchSchema, json("POST", { provider })),
  createOptimizationRun: (projectId: string, mode: OptimizationMode, provider: string) => request(
    `/api/projects/${projectId}/optimization-runs`,
    OptimizationRunSchema,
    json("POST", { mode, provider }),
  ),
  getOptimizationRun: (projectId: string, runId: string) => request(
    `/api/projects/${projectId}/optimization-runs/${runId}`,
    OptimizationRunSchema,
  ),
  cancelOptimizationRun: (projectId: string, runId: string) => request(
    `/api/projects/${projectId}/optimization-runs/${runId}/cancel`,
    OptimizationRunSchema,
    { method: "POST" },
  ),
  resumeOptimizationRun: (projectId: string, runId: string) => request(
    `/api/projects/${projectId}/optimization-runs/${runId}/resume`,
    OptimizationRunSchema,
    { method: "POST" },
  ),
  applyPatch: (id: string, patch: ResumePatch, accepted: string[]) => request(`/api/projects/${id}/resume/apply-patch`, ResumeVersionSchema, json("POST", { patch, accepted_operation_ids: accepted })),
  refinePatchOperation: (
    id: string,
    provider: string,
    patch: ResumePatch,
    operationId: string,
    message: string,
    history: Array<{ role: string; content: string }> = [],
  ) => request(
    `/api/projects/${id}/resume/refine-operation`,
    PatchDiscussionResultSchema,
    json("POST", {
      provider,
      patch,
      operation_id: operationId,
      message,
      history,
    }),
  ),
  getProviderSettings: () => request("/api/settings/providers", ProviderSettingsSchema),
  saveProviderSettings: (input: Record<string, unknown>) => request("/api/settings/providers", ProviderSettingsSchema, json("PATCH", input)),
  testProvider: (provider: string) => request("/api/settings/providers/test", z.object({ status: z.string() }), json("POST", { provider })),
  detectCodex: () => request("/api/settings/providers/codex/detect", CodexDetectSchema, { method: "POST" }),
  getProfile: () => request("/api/profile", z.object({
    resume: ResumeSchema,
    facts: z.array(FactSchema),
    ready: z.boolean(),
  })),
  saveProfile: (resume: ResumeDocument) => request("/api/profile", z.object({
    resume: ResumeSchema,
    facts: z.array(FactSchema),
    ready: z.boolean(),
  }), json("PUT", { resume })),
  createPractice: (projectId: string, kind: "interview" | "written", provider: string) => request(`/api/projects/${projectId}/practice/sessions`, PracticeSessionSchema, json("POST", { kind, provider })),
  getPractice: (sessionId: string) => request(`/api/practice/sessions/${sessionId}`, PracticeSessionSchema),
  answerPractice: (sessionId: string, answer: string, provider: string) => request(`/api/practice/sessions/${sessionId}/answer`, PracticeSessionSchema, json("POST", { answer, provider })),
  getCodexHandoff: (id: string) => request(`/api/projects/${id}/codex-handoff`, z.object({ markdown: z.string() }), { method: "POST" }),
  previewPages: (
    id: string,
    resume: ResumeDocument,
    templateId: string,
    signal?: AbortSignal,
  ) => request(
    `/api/projects/${id}/preview/pages`,
    z.object({
      page_count: z.number().int().positive(),
      pages: z.array(z.string().min(1)),
    }),
    { ...json("POST", { resume, template_id: templateId }), signal },
  ),
  previewPdf: async (
    id: string,
    resume: ResumeDocument,
    templateId: string,
    signal?: AbortSignal,
  ): Promise<{ blob: Blob; pages: number }> => {
    const response = await fetch(`/api/projects/${id}/preview/pdf`, {
      ...json("POST", { resume, template_id: templateId }),
      signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(
        payload?.detail?.code ?? "PREVIEW_FAILED",
        payload?.detail?.message ?? "预览生成失败",
        response.status,
      );
    }
    const parsed = Number(response.headers.get("X-Resume-Page-Count") || "1");
    const pages = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
    return { blob: await response.blob(), pages };
  },
};

export async function downloadFile(
  path: string,
  filename: string,
  method = "GET",
  body?: unknown,
): Promise<void> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(path, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail?.code ?? "EXPORT_FAILED", payload?.detail?.message ?? "导出失败", response.status);
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadDraftDocx(
  projectId: string,
  resume: ResumeDocument,
  templateId: string,
  filename: string,
): Promise<void> {
  await downloadFile(
    `/api/projects/${projectId}/export/docx`,
    filename,
    "POST",
    { resume, template_id: templateId },
  );
}

export async function downloadPreviewPdf(
  projectId: string,
  resume: ResumeDocument,
  templateId: string,
  filename: string,
): Promise<void> {
  const { blob } = await api.previewPdf(projectId, resume, templateId);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
