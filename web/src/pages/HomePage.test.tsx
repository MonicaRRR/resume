import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { api } from "../api/client";
import { HomePage } from "./HomePage";


test("展示本地项目及其求职类型", async () => {
  vi.spyOn(api, "listProjects").mockResolvedValue([
    {
      id: "project-1",
      title: "后端工程师",
      company_name: "示例科技",
      application_type: "campus",
      job_description: "负责 Python API",
      job_analysis: null,
      active_resume_version_id: null,
      selected_template_id: "clear-single",
      created_at: "2026-08-23T00:00:00Z",
      updated_at: "2026-08-23T00:00:00Z",
    },
  ]);
  vi.spyOn(api, "getProfile").mockResolvedValue({
    resume: {
      basics: {
        name: "张宁", gender: "", birthday: "", email: "", phone: "", location: "",
        wechat: "", political_status: "", photo_data_url: "",
        target_role: { value: "", source_fact_ids: [], origin: "manual", confidence: 1 },
        summary: { value: "", source_fact_ids: [], origin: "manual", confidence: 1 },
      },
      education: [], work_experience: [], projects: [], skills: [],
      certificates: [], awards: [], custom_sections: [],
      section_order: [],
      layout_profile: {
        source_kind: "builtin", font_family: "", heading_font_family: "", accent_color: "",
        base_font_size: null, line_height: null, columns: 1, imported: false,
      },
    },
    facts: [{ id: "f1", category: "基本信息", statement: "姓名：张宁", source_type: "manual", source_location: "", user_confirmed: true }],
    ready: true,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "后端工程师" })).toBeInTheDocument();
  expect(screen.getByText("示例科技")).toBeInTheDocument();
  expect(screen.getByText("校招 · 一页")).toBeInTheDocument();
});
