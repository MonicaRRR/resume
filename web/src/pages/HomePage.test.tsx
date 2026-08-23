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
