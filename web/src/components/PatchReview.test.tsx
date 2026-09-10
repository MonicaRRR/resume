import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";

import { blankResume, sourcedText } from "../resume";
import type { ResumeDocument, ResumePatch } from "../types";
import { PatchReview } from "./PatchReview";


vi.mock("./ResumePreview", () => ({
  ResumePreview: () => <div data-testid="resume-preview-mock">Word PDF preview</div>,
}));


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


function sampleResume(): ResumeDocument {
  const resume = blankResume();
  resume.basics.name = "测试同学";
  resume.basics.summary = sourcedText("产品经理");
  resume.basics.target_role = sourcedText("产品经理");
  return resume;
}


let host: HTMLDivElement;

beforeEach(() => {
  host = document.createElement("div");
  host.className = "annotation-preview-host";
  document.body.appendChild(host);
});

afterEach(() => {
  cleanup();
  host.remove();
});


function Review(props: {
  patch?: ResumePatch;
  onApply?: (ids: string[]) => void;
  onDiscuss?: Parameters<typeof PatchReview>[0]["onDiscuss"];
  onChange?: (patch: ResumePatch) => void;
}) {
  return (
    <PatchReview
      patch={props.patch ?? patch}
      resume={sampleResume()}
      templateId="classic-cn"
      projectId="project-1"
      applicationType="experienced"
      onApply={props.onApply ?? vi.fn()}
      onDiscuss={props.onDiscuss}
      onChange={props.onChange}
      previewHost={host}
    />
  );
}


test("右侧挂载点出现批注列表与同源预览", async () => {
  const user = userEvent.setup();
  const onApply = vi.fn();
  render(<Review onApply={onApply} />);

  expect(host.querySelector(".annotation-board")).not.toBeNull();
  expect(host.querySelectorAll(".annotation-card")).toHaveLength(2);
  expect(host.querySelector(".annotation-card-number")?.textContent).toBe("1");
  expect(host.querySelector(".annotation-card-location")?.textContent).toBe("个人概述");
  expect(screen.getByTestId("resume-preview-mock")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "同意" }));
  expect(screen.getByText("1/2 已同意")).toBeInTheDocument();

  await user.click(screen.getByRole("checkbox", { name: "我同意仅应用已勾选的建议" }));
  await user.click(screen.getByRole("button", { name: /应用已同意的修改/ }));
  expect(onApply).toHaveBeenCalledWith(["op-summary"]);
});


test("点击批注可切换当前项", async () => {
  const user = userEvent.setup();
  render(<Review />);
  const second = host.querySelectorAll(".annotation-card-hit")[1] as HTMLElement;
  await user.click(second);
  expect(screen.getByText("对齐职级表述")).toBeInTheDocument();
});
