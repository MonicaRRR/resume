import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { OptimizationRun } from "../types";
import { OptimizationProgress } from "./OptimizationProgress";

function run(overrides: Partial<OptimizationRun> = {}): OptimizationRun {
  return {
    id: "run-1",
    project_id: "project-1",
    input_version_id: "version-1",
    template_id: "classic-cn",
    provider: "test",
    model: "demo",
    prompt_version: "multi-agent-v1",
    mode: "deep",
    status: "queued",
    iteration: 0,
    max_refinements: 2,
    max_model_calls: 12,
    max_total_tokens: 120_000,
    call_count: 1,
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

test("shows retry wait without model reasoning", () => {
  render(
    <OptimizationProgress run={run({ status: "retry_wait", message: "模型限流，稍后重试" })} />,
  );
  expect(screen.getByText("模型限流，稍后重试")).toBeInTheDocument();
  expect(screen.getByText("模型繁忙，等待重试")).toBeInTheDocument();
  expect(screen.queryByText(/chain of thought|思维链/i)).not.toBeInTheDocument();
});

test("offers resume for interrupted run", () => {
  render(
    <OptimizationProgress
      run={run({ status: "failed", message: "上次运行被中断，可点击继续" })}
      onResume={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "继续运行" })).toBeEnabled();
});
