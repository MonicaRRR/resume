import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import type { ProviderSettings } from "../types";


const DEFAULTS: ProviderSettings = {
  kind: "openai-compatible",
  base_url: "https://api.openai.com/v1",
  model: "",
  timeout: 90,
  temperature: 0.2,
  configured: false,
  codex_confirmed: false,
};


export function SettingsPage() {
  const [settings, setSettings] = useState(DEFAULTS);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    api.getProviderSettings()
      .then((value) => mounted && setSettings(value))
      .catch(() => mounted && setError("无法读取本地模型设置"))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  async function saveApi(event: FormEvent) {
    event.preventDefault();
    const transientKey = apiKey;
    setApiKey("");
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.saveProviderSettings({ ...settings, kind: "openai-compatible", api_key: transientKey });
      await api.testProvider("openai-compatible");
      setSettings(saved);
      setMessage("API 连接测试成功。密钥仅保存在后端进程内存中，重启后需重新输入。");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "连接测试失败，请检查地址、模型与密钥");
    } finally {
      setBusy(false);
    }
  }

  async function saveCodex(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.saveProviderSettings({
        ...settings,
        kind: "codex",
        base_url: "",
        api_key: "",
        codex_confirmed: settings.codex_confirmed,
      });
      await api.testProvider("codex");
      setSettings(saved);
      setMessage("Codex CLI 已可用。每次任务使用临时、只读的工作目录。");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Codex 连接测试失败，请确认本机已登录 Codex CLI");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="page-placeholder"><h1>模型设置</h1><p>正在读取仅存于本机的连接信息……</p></main>;

  return (
    <main className="settings-page">
      <header className="settings-hero"><div><span className="eyebrow">LOCAL MODEL CONNECTIONS</span><h1>选择简历助手的推理入口</h1><p>当前 MVP 支持 OpenAI 兼容 API 与本机 Codex CLI。本地 Qwen 适配接口已预留，本期暂不启用。</p></div><a href="/">完成设置</a></header>
      {message && <div className="settings-message success" role="status">{message}</div>}
      {error && <div className="settings-message error" role="alert">{error}</div>}
      <div className="provider-cards">
        <form className={`provider-card ${settings.kind === "openai-compatible" && settings.configured ? "connected" : ""}`} onSubmit={saveApi}>
          <header><span>01 / API</span><div className="provider-icon">↗</div><h2>OpenAI 兼容 API</h2><p>适用于 OpenAI、兼容网关与提供相同 Chat Completions 协议的服务。</p></header>
          <label>Base URL<input required type="url" value={settings.base_url} onChange={(event) => setSettings({ ...settings, base_url: event.target.value })} /></label>
          <label>模型名称<input required value={settings.model} placeholder="例如 gpt-5-mini" onChange={(event) => setSettings({ ...settings, model: event.target.value })} /></label>
          <label>API Key<input required type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} /></label>
          <div className="provider-row"><label>超时（秒）<input type="number" min="5" max="600" value={settings.timeout} onChange={(event) => setSettings({ ...settings, timeout: Number(event.target.value) })} /></label><label>Temperature<input type="number" min="0" max="2" step="0.1" value={settings.temperature} onChange={(event) => setSettings({ ...settings, temperature: Number(event.target.value) })} /></label></div>
          <p className="privacy-note">密钥不会写入浏览器存储、数据库、日志或导出文件。</p>
          <button className="primary-button" disabled={busy}>{busy ? "正在测试…" : "保存并测试连接"}</button>
        </form>

        <form className={`provider-card codex-card ${settings.kind === "codex" && settings.configured ? "connected" : ""}`} onSubmit={saveCodex}>
          <header><span>02 / CODEX</span><div className="provider-icon">⌘</div><h2>Codex CLI</h2><p>复用本机 Codex 登录状态，由后端启动一次性只读聊天任务并解析结构化结果。</p></header>
          <label>Codex 模型（可选）<input value={settings.kind === "codex" ? settings.model : ""} placeholder="留空则使用 CLI 默认模型" onChange={(event) => setSettings({ ...settings, model: event.target.value })} /></label>
          <label className="privacy-confirm"><input type="checkbox" checked={settings.codex_confirmed} onChange={(event) => setSettings({ ...settings, codex_confirmed: event.target.checked })} /><span><strong>我理解数据流向</strong>JD 与去除邮箱、电话后的简历事实会发送给 Codex；任务目录不可写且用后即删。</span></label>
          <div className="codex-flow"><span>本地应用</span><i>→</i><span>临时只读任务</span><i>→</i><span>结构化结果</span></div>
          <button className="primary-button" disabled={busy || !settings.codex_confirmed}>{busy ? "正在测试…" : "确认并测试 Codex"}</button>
        </form>
      </div>
    </main>
  );
}
