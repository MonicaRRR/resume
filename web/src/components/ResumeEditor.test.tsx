import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { blankResume, sourcedText } from "../resume";
import { ResumeEditor } from "./ResumeEditor";


test("日期不显示数字范围，错误年份标红且预计毕业最多到今年加十年", () => {
  const resume = blankResume();
  const maxGraduationYear = new Date().getFullYear() + 10;
  resume.education.push({
    id: "education-1",
    institution: "示例大学",
    degree: "本科",
    field: "计算机科学",
    start_date: "1958-09",
    end_date: `${maxGraduationYear}-06`,
    highlights: [],
  });

  render(<ResumeEditor resume={resume} onChange={vi.fn()} onSave={vi.fn()} onDiscard={vi.fn()} />);

  expect(screen.getByLabelText("入学时间 1 年")).toHaveAttribute("placeholder", "YYYY");
  expect(screen.getByLabelText("入学时间 1 月")).toHaveAttribute("placeholder", "MM");
  expect(screen.getByLabelText("毕业或预计毕业时间 1 年")).toHaveValue(String(maxGraduationYear));
  expect(screen.getByLabelText("入学时间 1 年")).toHaveValue("1958");
  expect(screen.getByLabelText("入学时间 1 年")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByRole("button", { name: "保存素材库为新版本" })).toBeDisabled();
});


test("显示全部技能分组、证书、奖项和自定义栏目", () => {
  const resume = blankResume();
  resume.skills = [
    { id: "skill-1", name: "编程语言", items: [sourcedText("Python")] },
    { id: "skill-2", name: "测试与质量", items: [sourcedText("Pytest")] },
  ];
  resume.certificates = [
    { id: "cert-1", name: "大学英语六级", detail: sourcedText("512 分"), date: "2020-06" },
  ];
  resume.awards = [
    { id: "award-1", name: "校级一等奖", detail: sourcedText("程序设计竞赛"), date: "2021-05" },
  ];
  resume.custom_sections = [
    { id: "custom-1", title: "开源与分享", items: [sourcedText("团队技术分享")] },
  ];

  render(<ResumeEditor resume={resume} onChange={vi.fn()} onSave={vi.fn()} onDiscard={vi.fn()} />);

  expect(screen.getByLabelText("技能分组名称 1")).toHaveValue("编程语言");
  expect(screen.getByLabelText("技能分组名称 2")).toHaveValue("测试与质量");
  expect(screen.getByLabelText("证书名称 1")).toHaveValue("大学英语六级");
  expect(screen.getByLabelText("奖项名称 1")).toHaveValue("校级一等奖");
  expect(screen.getByLabelText("自定义栏目名称 1")).toHaveValue("开源与分享");
});


test("开始时间晚于结束时间时标红并阻止保存", () => {
  const resume = blankResume();
  resume.work_experience = [{
    id: "work-1",
    company: "示例公司",
    title: "实习生",
    start_date: "2026-08-01",
    end_date: "2026-07-01",
    bullets: [sourcedText("测试")],
  }];

  render(<ResumeEditor resume={resume} onChange={vi.fn()} onSave={vi.fn()} onDiscard={vi.fn()} />);

  expect(screen.getByLabelText("工作开始时间 1")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText("结束时间不能早于开始时间")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存素材库为新版本" })).toBeDisabled();
});
