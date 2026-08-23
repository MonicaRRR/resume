import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { api } from "../api/client";
import { SettingsPage } from "./SettingsPage";


test("保存连接后清空 API Key 输入框", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "getProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "http://127.0.0.1:8001/v1", model: "qwen",
    timeout: 90, temperature: 0.2, configured: false, codex_confirmed: false,
  });
  vi.spyOn(api, "saveProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "http://127.0.0.1:8001/v1", model: "qwen",
    timeout: 90, temperature: 0.2, configured: true, codex_confirmed: false,
  });
  vi.spyOn(api, "testProvider").mockResolvedValue({ status: "ok" });

  render(<SettingsPage />);
  const keyInput = await screen.findByLabelText("API Key");
  await user.type(keyInput, "secret");
  await user.click(screen.getByRole("button", { name: "保存并测试连接" }));

  expect(keyInput).toHaveValue("");
});
