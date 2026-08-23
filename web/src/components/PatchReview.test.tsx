import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
      risk: "low",
    },
  ],
};


test("默认不接受 AI 修改，用户可以逐项勾选", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(<PatchReview patch={patch} onApply={onApply} />);

  const checkbox = screen.getByRole("checkbox", { name: /面向企业服务/ });
  expect(checkbox).not.toBeChecked();
  await user.click(checkbox);
  await user.click(screen.getByRole("button", { name: "应用已选修改" }));

  expect(onApply).toHaveBeenCalledWith(["op-summary"]);
});
