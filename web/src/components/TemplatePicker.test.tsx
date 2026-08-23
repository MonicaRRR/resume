import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { blankResume } from "../resume";
import { recommendTemplate } from "../templates/registry";
import { TemplatePicker } from "./TemplatePicker";


test("用户可以覆盖自动模板推荐", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();
  render(<TemplatePicker selected="clear-single" recommended="project-focus" onChange={onChange} />);

  expect(screen.getByText("推荐：项目聚焦")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "专业双栏" }));
  expect(onChange).toHaveBeenCalledWith("pro-double");
});


test("模板推荐根据简历证据密度选择且不改写内容", () => {
  const resume = blankResume();
  resume.basics.name = "张宁";
  resume.projects.push({
    id: "project-1", name: "订单平台", role: "负责人", start_date: "", end_date: "",
    bullets: [{ value: "完成接口重构", source_fact_ids: ["fact-1"], origin: "manual", confidence: 1 }],
  });

  const recommendation = recommendTemplate(resume, null);

  expect(recommendation.id).toBe("project-focus");
  expect(resume.basics.name).toBe("张宁");
});
