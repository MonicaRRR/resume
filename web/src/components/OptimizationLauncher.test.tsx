import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { OptimizationLauncher } from "./OptimizationLauncher";

test("defaults to quick and explains deep mode cost", () => {
  render(<OptimizationLauncher disabled={false} onStart={vi.fn()} />);
  expect(screen.getByRole("radio", { name: /快速优化/ })).toBeChecked();
  expect(screen.getByText(/最多两轮返工/)).toBeInTheDocument();
});

test("starts with the selected mode", async () => {
  const user = userEvent.setup();
  const onStart = vi.fn();
  render(<OptimizationLauncher disabled={false} onStart={onStart} />);
  await user.click(screen.getByRole("radio", { name: /深度优化/ }));
  await user.click(screen.getByRole("button", { name: "开始深度优化" }));
  expect(onStart).toHaveBeenCalledWith("deep");
});
