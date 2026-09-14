import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";

import * as apiModule from "../api/client";
import type { OptimizationRun, ResumePatch } from "../types";
import { useOptimizationRun } from "./useOptimizationRun";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      ...actual.api,
      createOptimizationRun: vi.fn(),
      getOptimizationRun: vi.fn(),
      cancelOptimizationRun: vi.fn(),
      resumeOptimizationRun: vi.fn(),
    },
  };
});

const api = apiModule.api;

function patch(): ResumePatch {
  return {
    operations: [
      {
        id: "op-1",
        op: "replace",
        path: "/basics/summary",
        before: { value: "旧" },
        after: { value: "新" },
        reason: "对齐 JD",
        jd_requirement_ids: ["req-1"],
        source_fact_ids: ["fact-1"],
        layout_issue_ids: [],
        expected_layout_benefit: "",
        risk: "low",
      },
    ],
    experience_asks: [],
  };
}

function run(overrides: Partial<OptimizationRun> = {}): OptimizationRun {
  return {
    id: "run-1",
    project_id: "project-1",
    input_version_id: "version-1",
    template_id: "classic-cn",
    provider: "openai-compatible",
    model: "demo",
    prompt_version: "multi-agent-v1",
    mode: "deep",
    status: "queued",
    iteration: 0,
    max_refinements: 2,
    max_model_calls: 12,
    max_total_tokens: 120_000,
    call_count: 0,
    input_tokens: null,
    output_tokens: null,
    patch: null,
    baseline_layout_report: null,
    layout_report: null,
    review: null,
    quality: null,
    message: "",
    cancel_requested: false,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...overrides,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

test("polls an active run and stops when ready", async () => {
  vi.mocked(api.createOptimizationRun).mockResolvedValue(run({ status: "queued" }));
  vi.mocked(api.getOptimizationRun)
    .mockResolvedValueOnce(run({ status: "reviewing" }))
    .mockResolvedValueOnce(run({ status: "ready_for_user", patch: patch() }));

  const { result } = renderHook(() => useOptimizationRun("project-1"), { wrapper });
  await act(async () => {
    await result.current.start("deep", "openai-compatible");
  });
  await waitFor(() => expect(result.current.run?.status).toBe("ready_for_user"), {
    timeout: 4000,
  });
  expect(api.getOptimizationRun).toHaveBeenCalled();
  expect(result.current.run?.patch?.operations).toHaveLength(1);
});
