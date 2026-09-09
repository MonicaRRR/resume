import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ResumeIntake } from "./ResumeIntake";


test("从经历开始使用分字段表单并支持大段经历描述", async () => {
  const user = userEvent.setup();
  const onCreate = vi.fn();
  render(<ResumeIntake onUpload={vi.fn()} onCreate={onCreate} />);

  await user.click(screen.getByRole("button", { name: /从经历开始/ }));

  expect(screen.getByLabelText("姓名")).toBeInTheDocument();
  expect(screen.getByLabelText("期望职位")).toBeInTheDocument();
  expect(screen.getByLabelText("学校名称 1")).toBeInTheDocument();
  expect(screen.getByLabelText("学历 1")).toBeInTheDocument();
  expect(screen.getByLabelText("公司名称 1")).toBeInTheDocument();
  expect(screen.getByLabelText("工作经历描述 1")).toBeInTheDocument();
  expect(screen.getByLabelText("入学时间 1 年")).toBeInTheDocument();
  expect(screen.getByLabelText("工作开始时间 1 日")).toBeInTheDocument();

  await user.type(screen.getByLabelText("姓名"), "李明");
  await user.type(screen.getByLabelText("期望职位"), "后端工程师");
  await user.type(screen.getByLabelText("学校名称 1"), "示例大学");
  await user.type(screen.getByLabelText("专业 1"), "软件工程");
  await user.type(screen.getByLabelText("公司名称 1"), "示例科技");
  await user.type(screen.getByLabelText("职位名称 1"), "实习生");
  await user.type(screen.getByLabelText("工作经历描述 1"), "负责接口开发");
  await user.type(screen.getByLabelText("添加专业技能"), "Python");
  await user.click(screen.getByRole("button", { name: "添加" }));
  await user.click(screen.getByRole("button", { name: "保存事实并生成初稿" }));

  expect(onCreate).toHaveBeenCalledOnce();
  const [resume, facts] = onCreate.mock.calls[0];
  expect(resume.basics.name).toBe("李明");
  expect(resume.education[0].institution).toBe("示例大学");
  expect(resume.education[0].field).toBe("软件工程");
  expect(resume.work_experience[0].company).toBe("示例科技");
  expect(resume.work_experience[0].bullets[0].value).toBe("负责接口开发");
  expect(resume.skills[0].items.map((item: { value: string }) => item.value)).toContain("Python");
  expect(facts.length).toBeGreaterThan(0);
});
