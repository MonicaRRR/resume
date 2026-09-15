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
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
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

test("资料刷新时不会覆盖正在编辑的教育经历", async () => {
  const user = userEvent.setup();
  const saved = blankResume();
  saved.basics.name = "李明";
  saved.education = [{
    id: "edu-1",
    institution: "示例大学",
    degree: "本科",
    field: "软件工程",
    start_date: "2022-09",
    end_date: "2026-06",
    highlights: [],
  }];
  const getProfile = vi.spyOn(api, "getProfile")
    .mockResolvedValueOnce({ resume: saved, facts: [], ready: true })
    .mockResolvedValueOnce({ resume: blankResume(), facts: [], ready: false });
  const { client } = wrap(<ProfilePage />);

  const institution = await screen.findByDisplayValue("示例大学");
  await user.clear(institution);
  await user.type(institution, "示例大学（已修改）");

  await client.invalidateQueries({ queryKey: ["profile"] });
  await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(2));
  expect(screen.getByDisplayValue("示例大学（已修改）")).toBeInTheDocument();
});
