import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { api } from "../api/client";
import { blankResume } from "../resume";
import { ProfilePage } from "./ProfilePage";


function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}


test("导入后草稿含姓名", async () => {
  const user = userEvent.setup();
  const empty = blankResume();
  vi.spyOn(api, "getProfile").mockResolvedValue({
    resume: empty,
    facts: [],
    ready: false,
  });
  const imported = blankResume();
  imported.basics.name = "张宁";
  vi.spyOn(api, "importProfileResume").mockResolvedValue({
    resume: imported,
    facts: [],
    layout_profile: imported.layout_profile,
    quality_score: 0.8,
    warnings: ["部分段落可能需要人工核对"],
  });
  vi.spyOn(api, "saveProfile");

  wrap(<ProfilePage />);
  const nameInput = await screen.findByLabelText("姓名");
  expect(nameInput).toHaveValue("");

  const file = new File(["张宁\n教育背景\n示例大学"], "resume.txt", { type: "text/plain" });
  await user.upload(screen.getByLabelText("上传已有简历"), file);

  await waitFor(() => expect(screen.getByLabelText("姓名")).toHaveValue("张宁"));
  expect(screen.getByText(/请核对后点击保存/)).toBeInTheDocument();
  expect(screen.getByText(/解析质量分/)).toBeInTheDocument();
  expect(api.saveProfile).not.toHaveBeenCalled();
});
