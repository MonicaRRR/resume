import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ProjectForm } from "./ProjectForm";


test("经历库未就绪时不能创建项目", async () => {
  const onCreate = vi.fn();
  render(<MemoryRouter><ProjectForm onCreate={onCreate} profileReady={false} /></MemoryRouter>);

  expect(screen.getByText(/尚未完善经历库/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "创建项目并分析 JD" })).toBeDisabled();
  expect(onCreate).not.toHaveBeenCalled();
});


test("公司名称可以留空并保留求职类型", async () => {
  const user = userEvent.setup();
  const onCreate = vi.fn();
  render(<MemoryRouter><ProjectForm onCreate={onCreate} profileReady /></MemoryRouter>);

  await user.type(screen.getByLabelText("项目名称"), "后端工程师");
  await user.click(screen.getByRole("radio", { name: "校招" }));
  await user.type(screen.getByLabelText("职位描述"), "负责 Python API 开发");
  await user.click(screen.getByRole("button", { name: "创建项目并分析 JD" }));

  expect(onCreate).toHaveBeenCalledWith({
    title: "后端工程师",
    company_name: "",
    application_type: "campus",
    job_description: "负责 Python API 开发",
  });
});
