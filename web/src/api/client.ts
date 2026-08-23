import { z } from "zod";

import {
  FollowupQuestionSchema,
  ImportResultSchema,
  JobAnalysisSchema,
  MatchReportSchema,
  PracticeSessionSchema,
  ProjectListSchema,
  ProjectSchema,
  ProviderSettingsSchema,
  ResumePatchSchema,
  ResumeVersionSchema,
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
  getVersions: (id: string) => request(`/api/projects/${id}/versions`, z.array(ResumeVersionSchema)),
  activateVersion: (projectId: string, versionId: string) => request(`/api/projects/${projectId}/versions/${versionId}/activate`, ProjectSchema, { method: "POST" }),
  importResume: async (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request(`/api/projects/${id}/resume/import`, ImportResultSchema, { method: "POST", body });
  },
  saveResume: (id: string, resume: ResumeDocument, facts: Fact[], reason = "手动保存") =>
    request(`/api/projects/${id}/resume`, ResumeVersionSchema, json("PUT", { resume, facts, reason })),
  analyzeJob: (id: string, provider: string) => request(`/api/projects/${id}/analyze-jd`, JobAnalysisSchema, json("POST", { provider })),
  getMatch: (id: string) => request(`/api/projects/${id}/match`, MatchReportSchema),
  getQuestions: (id: string, provider: string) => request(`/api/projects/${id}/questions`, z.array(FollowupQuestionSchema), json("POST", { provider })),
  addFact: (id: string, statement: string, category = "补充回答") => request(`/api/projects/${id}/facts`, ResumeVersionSchema, json("POST", { statement, category, source_type: "questionnaire", user_confirmed: true })),
  suggestPatch: (id: string, provider: string) => request(`/api/projects/${id}/resume/suggest`, ResumePatchSchema, json("POST", { provider })),
  applyPatch: (id: string, patch: ResumePatch, accepted: string[]) => request(`/api/projects/${id}/resume/apply-patch`, ResumeVersionSchema, json("POST", { patch, accepted_operation_ids: accepted })),
  getProviderSettings: () => request("/api/settings/providers", ProviderSettingsSchema),
  saveProviderSettings: (input: Record<string, unknown>) => request("/api/settings/providers", ProviderSettingsSchema, json("PATCH", input)),
  testProvider: (provider: string) => request("/api/settings/providers/test", z.object({ status: z.string() }), json("POST", { provider })),
  createPractice: (projectId: string, kind: "interview" | "written", provider: string) => request(`/api/projects/${projectId}/practice/sessions`, PracticeSessionSchema, json("POST", { kind, provider })),
  getPractice: (sessionId: string) => request(`/api/practice/sessions/${sessionId}`, PracticeSessionSchema),
  answerPractice: (sessionId: string, answer: string, provider: string) => request(`/api/practice/sessions/${sessionId}/answer`, PracticeSessionSchema, json("POST", { answer, provider })),
  getCodexHandoff: (id: string) => request(`/api/projects/${id}/codex-handoff`, z.object({ markdown: z.string() }), { method: "POST" }),
};

export async function downloadFile(path: string, filename: string, method = "GET"): Promise<void> {
  const response = await fetch(path, { method });
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
