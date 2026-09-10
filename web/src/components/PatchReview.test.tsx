import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import type { ResumePatch } from "../types";
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
  expect(screen.getByText((_, node) => node?.textContent === "1/2 已同意 · 2 / 2")).toBeInTheDocument();

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
  expect(screen.getByText((_, node) => node?.textContent === "1/2 已同意 · 2 / 2")).toBeInTheDocument();
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
  expect(screen.getByText((_, node) => node?.textContent === "1/2 已同意 · 2 / 2")).toBeInTheDocument();
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
