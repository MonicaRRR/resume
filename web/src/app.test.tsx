import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { App } from "./app";
import { api } from "./api/client";


test("显示产品身份和隐私说明", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "简历证据工作台" })).toBeInTheDocument();
  expect(screen.getByText("简历默认只保存在本机")).toBeInTheDocument();
});

test("经历库未完善时在导航显示红点提醒", async () => {
  vi.spyOn(api, "getProfile").mockResolvedValue({
    resume: {} as never,
    facts: [],
    ready: false,
  });
  render(<App />);

  expect(await screen.findByRole("status", { name: "经历库有待完善内容" })).toBeInTheDocument();
});

test("经历库已可创建项目但缺少教育经历时仍显示红点", async () => {
  vi.spyOn(api, "getProfile").mockResolvedValue({
    resume: { education: [] } as never,
    facts: [],
    ready: true,
  });
  render(<App />);

  expect(await screen.findByRole("status", { name: "经历库有待完善内容" })).toBeInTheDocument();
});
