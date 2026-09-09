import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { blankResume } from "../resume";
import { ResumeEditor } from "./ResumeEditor";


test("编辑教育经历时年份范围从 1960 到当前年份", () => {
  const resume = blankResume();
  resume.education.push({
    id: "education-1",
    institution: "示例大学",
    degree: "本科",
    field: "计算机科学",
    start_date: "1958-09",
    end_date: "2024-06",
    highlights: [],
  });

  render(<ResumeEditor resume={resume} onChange={vi.fn()} onSave={vi.fn()} onDiscard={vi.fn()} />);

  const range = `1960-${new Date().getFullYear()}`;
  expect(screen.getByLabelText("入学时间 1 年")).toHaveAttribute("placeholder", range);
  expect(screen.getByLabelText("毕业时间 1 年")).toHaveAttribute("placeholder", range);
  expect(screen.getByLabelText("入学时间 1 年")).toHaveValue("1958");
});
