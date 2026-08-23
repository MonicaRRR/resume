import { render, screen } from "@testing-library/react";

import { App } from "./app";


test("显示产品身份和隐私说明", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "简历证据工作台" })).toBeInTheDocument();
  expect(screen.getByText("简历默认只保存在本机")).toBeInTheDocument();
});
