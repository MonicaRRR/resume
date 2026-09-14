import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { api, ApiError } from "../api/client";
import { SettingsPage } from "./SettingsPage";


function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}


test("保存连接后清空 API Key 输入框", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "getProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "http://127.0.0.1:8001/v1", model: "qwen",
    timeout: 90, temperature: 0.2, configured: false, codex_confirmed: false, key_storage: "none", key_saved: false,
  });
  vi.spyOn(api, "saveProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "http://127.0.0.1:8001/v1", model: "qwen",
    timeout: 90, temperature: 0.2, configured: true, codex_confirmed: false, key_storage: "keychain", key_saved: true,
  });
  vi.spyOn(api, "testProvider").mockResolvedValue({ status: "ok" });

  wrap(<SettingsPage />);
  const keyInput = await screen.findByLabelText("API Key");
  await user.type(keyInput, "secret");
  await user.click(screen.getByRole("button", { name: "保存并测试连接" }));

  expect(keyInput).toHaveValue("");
});


test("显示钥匙串状态并允许删除已保存密钥", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "getProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "https://api.example/v1", model: "demo",
    timeout: 90, temperature: 0.2, configured: true, codex_confirmed: false,
    key_storage: "keychain", key_saved: true,
  });
  vi.spyOn(api, "deleteProviderKey").mockResolvedValue({
    kind: "openai-compatible", base_url: "https://api.example/v1", model: "demo",
    timeout: 90, temperature: 0.2, configured: false, codex_confirmed: false,
    key_storage: "none", key_saved: false,
  });

  wrap(<SettingsPage />);

  expect(await screen.findByText(/已安全保存在 macOS 钥匙串/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "删除已保存密钥" }));
  expect(api.deleteProviderKey).toHaveBeenCalledOnce();
  expect(await screen.findByText("已从 macOS 钥匙串删除 API Key。")).toBeInTheDocument();
});

test("连接测试返回 429 时仍显示已保存密钥并允许留空重试", async () => {
  const user = userEvent.setup();
  const initial = {
    kind: "openai-compatible", base_url: "https://api.example/v1", model: "demo",
    timeout: 90, temperature: 0.2, configured: false, codex_confirmed: false,
    key_storage: "none" as const, key_saved: false,
  };
  vi.spyOn(api, "getProviderSettings").mockResolvedValue(initial);
  vi.spyOn(api, "saveProviderSettings").mockResolvedValue({
    ...initial, configured: true, key_storage: "keychain", key_saved: true,
  });
  vi.spyOn(api, "testProvider").mockRejectedValue(new ApiError("PROVIDER_RATE_LIMITED", "模型服务返回错误状态 429", 429));
  wrap(<SettingsPage />);
  const keyInput = await screen.findByLabelText("API Key");
  await user.type(keyInput, "secret");
  await user.click(screen.getByRole("button", { name: "保存并测试连接" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("429");
  expect(screen.getByRole("button", { name: "删除已保存密钥" })).toBeInTheDocument();
  expect(keyInput).not.toBeRequired();
  expect(keyInput).toHaveValue("");
});


test("Codex 先检测再以下拉选择模型", async () => {
  const user = userEvent.setup();
  vi.spyOn(api, "getProviderSettings").mockResolvedValue({
    kind: "openai-compatible", base_url: "http://127.0.0.1:8001/v1", model: "",
    timeout: 90, temperature: 0.2, configured: false, codex_confirmed: false, key_storage: "none", key_saved: false,
  });
  vi.spyOn(api, "detectCodex").mockResolvedValue({
    installed: true,
    authenticated: true,
    available: true,
    version: "0.1.0",
    default_model: "gpt-b",
    binary_path: "/usr/bin/codex",
    models: [
      { slug: "gpt-a", display_name: "Model A", description: "A" },
      { slug: "gpt-b", display_name: "Model B", description: "B" },
    ],
    message: "已检测到 Codex",
  });
  vi.spyOn(api, "saveProviderSettings").mockResolvedValue({
    kind: "codex", base_url: "", model: "gpt-b",
    timeout: 90, temperature: 0.2, configured: true, codex_confirmed: true, key_storage: "none", key_saved: false,
  });
  vi.spyOn(api, "testProvider").mockResolvedValue({ status: "ok" });

  wrap(<SettingsPage />);
  expect(await screen.findByText("尚未检测")).toBeInTheDocument();
  expect(screen.queryByLabelText("Codex 模型")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "检测本机 Codex" }));
  const modelSelect = await screen.findByLabelText("Codex 模型");
  expect(modelSelect.tagName).toBe("BUTTON");
  expect(modelSelect).toHaveTextContent(/Model B/);
  expect(screen.getByRole("button", { name: "确认并测试 Codex" })).toBeDisabled();

  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "确认并测试 Codex" }));
  expect(api.saveProviderSettings).toHaveBeenCalledWith(expect.objectContaining({
    kind: "codex",
    model: "gpt-b",
    codex_confirmed: true,
  }));
});
