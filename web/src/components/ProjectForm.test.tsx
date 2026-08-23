import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ProjectForm } from "./ProjectForm";


test("JD 为空时不创建项目并给出中文提示", async () => {
  const user = userEvent.setup();
  const onCreate = vi.fn();
  render(<ProjectForm onCreate={onCreate} />);

  await user.type(screen.getByLabelText("项目名称"), "后端工程师");
  await user.click(screen.getByRole("button", { name: "创建求职项目" }));

  expect(screen.getByText("请先粘贴职位描述")).toBeInTheDocument();
  expect(onCreate).not.toHaveBeenCalled();
});


test("公司名称可以留空并保留求职类型", async () => {
  const user = userEvent.setup();
  const onCreate = vi.fn();
  render(<ProjectForm onCreate={onCreate} />);

  await user.type(screen.getByLabelText("项目名称"), "后端工程师");
  await user.click(screen.getByRole("radio", { name: "校招" }));
  await user.type(screen.getByLabelText("职位描述"), "负责 Python API 开发");
  await user.click(screen.getByRole("button", { name: "创建求职项目" }));

  expect(onCreate).toHaveBeenCalledWith({
    title: "后端工程师",
    company_name: "",
    application_type: "campus",
    job_description: "负责 Python API 开发",
  });
});
