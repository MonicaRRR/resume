import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import type { OptimizationRun, ResumePatch } from "../types";
import { PatchReview } from "./PatchReview";


const patch: ResumePatch = {
  operations: [
    {
      id: "op-summary",
      op: "replace",
      path: "/basics/summary",
      before: { value: "产品经理" },
      after: { value: "面向企业服务的产品经理" },
      reason: "突出岗位相关领域",
      jd_requirement_ids: ["req-1"],
      source_fact_ids: ["fact-1"],
      layout_issue_ids: [],
      expected_layout_benefit: "",
      risk: "low",
    },
    {
      id: "op-role",
      op: "replace",
      path: "/basics/target_role",
      before: { value: "产品经理" },
      after: { value: "高级产品经理" },
      reason: "对齐职级表述",
      jd_requirement_ids: ["req-1"],
      source_fact_ids: ["fact-1"],
      layout_issue_ids: [],
      expected_layout_benefit: "",
      risk: "medium",
    },
  ],
  experience_asks: [],
};


function baseRun(overrides: Partial<OptimizationRun> = {}): OptimizationRun {
  return {
    id: "run-1",
    project_id: "project-1",
    input_version_id: "version-1",
    template_id: "classic-cn",
    provider: "test",
    model: "demo",
    prompt_version: "multi-agent-v1",
    mode: "deep",
    status: "ready_for_user",
    iteration: 1,
    max_refinements: 2,
    max_model_calls: 12,
    max_total_tokens: 120_000,
    call_count: 4,
    input_tokens: null,
    output_tokens: null,
    patch: null,
    baseline_layout_report: {
      page_count: 2,
      density_by_page: [0.7, 0.2],
      issues: [
        {
          id: "layout-1",
          kind: "short_tail",
          severity: "warning",
          message: "最后一行过短",
          page: 1,
          target_path: "/basics/summary",
          text_excerpt: "产品经理",
          measured_ratio: 0.12,
        },
      ],
      severe_issue_count: 0,
    },
    layout_report: {
      page_count: 1,
      density_by_page: [0.82],
      issues: [],
      severe_issue_count: 0,
    },
    review: {
      factuality_passed: true,
      expression_score: 88,
      requires_user_input: false,
      questions: [],
      rejection_reasons: [],
      refinement_instructions: [],
    },
    quality: {
      passed: true,
      factuality_passed: true,
      traceability: 1,
      jd_coverage: 0.86,
      expression_score: 88,
      page_policy_passed: true,
      severe_layout_issues: 0,
      reasons: [],
    },
    message: "",
    cancel_requested: false,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...overrides,
  };
}


function layoutPatch(): ResumePatch {
  return {
    operations: [
      {
        id: "op-layout",
        op: "replace",
        path: "/basics/summary",
        before: { value: "产品经理" },
        after: { value: "面向企业服务的产品经理，覆盖核心岗位关键词" },
        reason: "压缩短尾行",
        jd_requirement_ids: ["req-1"],
        source_fact_ids: ["fact-1"],
        layout_issue_ids: ["layout-1"],
        expected_layout_benefit: "消除 3 字尾行",
        risk: "low",
      },
    ],
    experience_asks: [],
  };
}


function passingRun(): OptimizationRun {
  return baseRun();
}


function runWithWarnings(): OptimizationRun {
  return baseRun({
    quality: {
      passed: false,
      factuality_passed: true,
      traceability: 1,
      jd_coverage: 0.7,
      expression_score: 72,
      page_policy_passed: true,
      severe_layout_issues: 0,
      reasons: ["综合表达评分不足 80 分"],
    },
    message: "已停止自动返工：综合表达评分不足 80 分",
  });
}


test("逐条展示建议，同意后进入下一项，确认后才可应用", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(<PatchReview patch={patch} onApply={onApply} />);

  expect(screen.getByText("建议 1 / 2")).toBeInTheDocument();
  expect(screen.getByText("突出岗位相关领域")).toBeInTheDocument();
  expect(screen.queryByText("对齐职级表述")).not.toBeInTheDocument();

  expect(screen.getByRole("button", { name: /应用已同意的修改/ })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "同意这项" }));

  expect(screen.getByText("建议 2 / 2")).toBeInTheDocument();
  expect(screen.getByText("对齐职级表述")).toBeInTheDocument();
  expect(screen.getByText("1/2 已同意")).toBeInTheDocument();

  await user.click(screen.getByRole("checkbox", { name: "我同意仅应用已勾选的建议" }));
  await user.click(screen.getByRole("button", { name: /应用已同意的修改/ }));

  expect(onApply).toHaveBeenCalledWith(["op-summary"]);
});


test("讨论不自动改稿，确认采用后才更新；且不重置已同意状态", async () => {
  const user = userEvent.setup();
  const onDiscuss = vi.fn().mockResolvedValue({
    reply: "可以，我准备了一版更克制的写法。",
    proposes_change: true,
    draft_operation: {
      ...patch.operations[1],
      reason: "已按讨论意见弱化职级措辞",
      after: { value: "产品经理（偏资深）" },
    },
  });

  function Harness() {
    const [current, setCurrent] = useState(patch);
    return (
      <PatchReview
        patch={current}
        onApply={vi.fn()}
        onChange={setCurrent}
        onDiscuss={onDiscuss}
      />
    );
  }

  render(<Harness />);

  await user.click(screen.getByRole("button", { name: "同意这项" }));
  expect(screen.getByText("1/2 已同意")).toBeInTheDocument();
  expect(screen.getByText("对齐职级表述")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "与 AI 讨论" }));
  await user.type(screen.getByLabelText("对 AI 的讨论内容"), "弱化职级");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(onDiscuss).toHaveBeenCalledWith("op-role", "弱化职级", []);
  expect(await screen.findByText("可以，我准备了一版更克制的写法。")).toBeInTheDocument();
  expect(screen.getByText(/产品经理（偏资深）/)).toBeInTheDocument();
  expect(screen.getByText("对齐职级表述")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "采用此改写" }));
  expect(await screen.findByText("已按讨论意见弱化职级措辞")).toBeInTheDocument();
  expect(screen.getByText("1/2 已同意")).toBeInTheDocument();
  expect(screen.getByText("建议 2 / 2")).toBeInTheDocument();
});


test("AI 反驳时不出现采用改写", async () => {
  const user = userEvent.setup();
  const onDiscuss = vi.fn().mockResolvedValue({
    reply: "建议先保持原样，当前写法已对齐岗位关键词。",
    proposes_change: false,
    draft_operation: null,
  });
  render(<PatchReview patch={patch} onApply={vi.fn()} onDiscuss={onDiscuss} />);

  await user.click(screen.getByRole("button", { name: "与 AI 讨论" }));
  await user.type(screen.getByLabelText("对 AI 的讨论内容"), "不要改");
  await user.click(screen.getByRole("button", { name: "发送" }));

  expect(await screen.findByText(/建议先保持原样/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "采用此改写" })).not.toBeInTheDocument();
});


test("shows layout benefit without auto-selecting", () => {
  render(<PatchReview patch={layoutPatch()} optimization={passingRun()} onApply={vi.fn()} />);
  expect(screen.getByText("消除 3 字尾行")).toBeInTheDocument();
  expect(screen.getByText(/JD 覆盖 86%/)).toBeInTheDocument();
  expect(screen.getByText(/实际 1 页/)).toBeInTheDocument();
  expect(screen.getByText("0/1 已同意")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /应用已同意/ })).toBeDisabled();
  expect(screen.getByText(/不代表录取概率/)).toBeInTheDocument();
});


test("labels a below-threshold stopped run", () => {
  render(<PatchReview patch={patch} optimization={runWithWarnings()} onApply={vi.fn()} />);
  expect(screen.getByRole("alert")).toHaveTextContent("已达到自动返工上限");
});
