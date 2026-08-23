import { render, screen } from "@testing-library/react";

import { blankResume } from "../resume";
import { ResumePreview } from "./ResumePreview";


test("校招简历溢出一页时阻止导出但不截断内容", () => {
  const resume = blankResume();
  resume.basics.name = "张宁";
  const finalCompany = "最后一段经历仍然可见";
  resume.work_experience = [
    {
      id: "work-1", company: finalCompany, title: "后端工程师", start_date: "", end_date: "",
      bullets: [{ value: "负责接口设计、稳定性治理与性能优化。".repeat(180), source_fact_ids: [], origin: "manual", confidence: 1 }],
    },
  ];

  render(<ResumePreview resume={resume} templateId="clear-single" applicationType="campus" />);

  expect(screen.getByText("当前内容超过一页")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "打印或保存 PDF" })).toBeDisabled();
  expect(screen.getByText(finalCompany)).toBeVisible();
});


test("社招简历允许自然分页", () => {
  const resume = blankResume();
  resume.basics.name = "张宁";
  resume.basics.summary.value = "长期从事企业系统研发".repeat(400);

  render(<ResumePreview resume={resume} templateId="career-depth" applicationType="experienced" />);

  expect(screen.queryByText("当前内容超过一页")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "打印或保存 PDF" })).toBeEnabled();
});


test("上传模板的有效字体、强调色与双栏结构优先用于预览", () => {
  const resume = blankResume();
  resume.layout_profile = {
    source_kind: "docx", imported: true, font_family: "FangSong", heading_font_family: "STSong",
    accent_color: "#7A3E8E", base_font_size: 11, line_height: 1.5, columns: 2,
  };

  const { container } = render(<ResumePreview resume={resume} templateId="clear-single" applicationType="experienced" />);
  const sheet = container.querySelector<HTMLElement>(".resume-sheet")!;

  expect(sheet).toHaveClass("template-pro-double");
  expect(sheet).toHaveStyle({ fontFamily: "FangSong", fontSize: "11px", lineHeight: "1.5" });
  expect(sheet.style.getPropertyValue("--resume-accent")).toBe("#7A3E8E");
});
