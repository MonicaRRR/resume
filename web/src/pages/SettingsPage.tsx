import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import { AppleSelect } from "../components/ui/AppleSelect";
import type { CodexDetectResult, ProviderSettings } from "../types";


const DEFAULTS: ProviderSettings = {
  kind: "openai-compatible",
  base_url: "https://api.openai.com/v1",
  model: "",
  timeout: 90,
  temperature: 0.2,
  configured: false,
  codex_confirmed: false,
  key_storage: "none",
  key_saved: false,
  capabilities: [],
};


export function SettingsPage() {
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState(DEFAULTS);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [codexDetect, setCodexDetect] = useState<CodexDetectResult | null>(null);
  const [codexModel, setCodexModel] = useState("");

  function syncProviderCache(value: ProviderSettings) {
    queryClient.setQueryData(["provider-settings"], value);
  }

  useEffect(() => {
    let mounted = true;
    api.getProviderSettings()
      .then(async (value) => {
        if (!mounted) return;
        setSettings(value.kind ? value : { ...DEFAULTS, ...value, kind: value.kind || DEFAULTS.kind });
        syncProviderCache(value);
        if (value.kind === "codex") {
          setCodexModel(value.model);
          // Already enabled: keep usable without forcing a fresh detect click.
          if (value.configured && value.codex_confirmed) {
            setCodexDetect({
              installed: true,
              authenticated: true,
              available: true,
              version: "",
              default_model: value.model,
              binary_path: "",
              models: value.model
                ? [{ slug: value.model, display_name: value.model, description: "上次使用的模型" }]
                : [],
              message: "已从本地恢复 Codex 配置，可直接使用；需要换模型时再重新检测。",
            });
            setMessage("已恢复上次的 Codex 配置。");
          }
        }
      })
      .catch(() => mounted && setError("无法读取本地模型设置"))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, [queryClient]);

  async function saveApi(event: FormEvent) {
    event.preventDefault();
    const transientKey = apiKey;
    setApiKey("");
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.saveProviderSettings({ ...settings, kind: "openai-compatible", api_key: transientKey });
      setSettings(saved);
      syncProviderCache(saved);
      await api.testProvider("openai-compatible");
      if (saved.key_storage === "keychain") {
        setMessage("API 连接测试成功，API Key 已安全保存在 macOS 钥匙串。");
      } else {
        setMessage("API 连接测试成功。");
        setError("无法写入 macOS 钥匙串；密钥本次仅保存在内存，重启后需重新输入。");
      }
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "连接测试失败，请检查地址、模型与密钥");
      await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
    } finally {
      setBusy(false);
    }
  }

  async function deleteApiKey() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.deleteProviderKey();
      setApiKey("");
      setSettings(saved);
      syncProviderCache(saved);
      setMessage("已从 macOS 钥匙串删除 API Key。");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "删除 API Key 失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function detectCodex() {
    setDetecting(true);
    setError("");
    setMessage("");
    try {
      const result = await api.detectCodex();
      setCodexDetect(result);
      if (result.available) {
        const preferred = (settings.kind === "codex" && (codexModel || settings.model))
          ? (codexModel || settings.model)
          : result.default_model;
        const hasPreferred = preferred && result.models.some((item) => item.slug === preferred);
        setCodexModel(hasPreferred ? preferred : (result.models[0]?.slug ?? preferred ?? ""));
        setMessage(result.message);
      } else {
        setError(result.message);
      }
    } catch (reason) {
      setCodexDetect(null);
      setError(reason instanceof ApiError ? reason.message : "检测 Codex CLI 失败");
    } finally {
      setDetecting(false);
    }
  }

  async function saveCodex(event: FormEvent) {
    event.preventDefault();
    const alreadyEnabled = settings.kind === "codex" && settings.configured && settings.codex_confirmed;
    if (!codexDetect?.available && !alreadyEnabled) {
      setError("请先检测本机 Codex CLI");
      return;
    }
    if ((codexDetect?.models.length ?? 0) > 0 && !codexModel) {
      setError("请从列表中选择 Codex 模型");
      return;
    }
    const confirmed = settings.codex_confirmed || alreadyEnabled;
    if (!confirmed) {
      setError("请先确认数据流向");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("正在测试 Codex 连通性，通常需要 15–45 秒…");
    try {
      const saved = await api.saveProviderSettings({
        ...settings,
        kind: "codex",
        base_url: "",
        api_key: "",
        model: codexModel,
        codex_confirmed: true,
      });
      await api.testProvider("codex");
      setSettings(saved);
      syncProviderCache(saved);
      setMessage("Codex CLI 已可用，配置已保存在本机。重启后无需重新检测。");
    } catch (reason) {
      setMessage("");
      setError(reason instanceof ApiError ? reason.message : "Codex 连接测试失败，请确认本机已登录 Codex CLI");
      await queryClient.invalidateQueries({ queryKey: ["provider-settings"] });
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="page-placeholder"><h1>模型设置</h1><p>正在读取仅存于本机的连接信息……</p></main>;

  const alreadyEnabled = settings.kind === "codex" && settings.configured && settings.codex_confirmed;
  const codexFormVisible = Boolean(codexDetect?.available) || alreadyEnabled;
  const statusLabel = alreadyEnabled && !codexDetect
    ? "已恢复"
    : !codexDetect
      ? "尚未检测"
      : !codexDetect.installed
        ? "未安装"
        : !codexDetect.authenticated
          ? "未登录"
          : alreadyEnabled
            ? "已启用"
            : "已就绪";

  const modelOptions = (() => {
    if (codexDetect && codexDetect.models.length > 0) {
      return codexDetect.models.map((item) => ({
        value: item.slug,
        label: `${item.display_name}${item.slug === codexDetect.default_model ? "（当前默认）" : ""}`,
      }));
    }
    if (codexModel) {
      return [{ value: codexModel, label: codexModel }];
    }
    return [{ value: "", label: "使用 CLI 默认模型" }];
  })();

  return (
    <main className="settings-page">
      <header className="settings-hero"><div><span className="eyebrow">LOCAL MODEL CONNECTIONS</span><h1>选择简历助手的推理入口</h1><p>当前 MVP 支持 OpenAI 兼容 API 与本机 Codex CLI。本地 Qwen 适配接口已预留，本期暂不启用。</p></div><a href="/">完成设置</a></header>
      {message && <div className="settings-message success" role="status">{message}</div>}
      {error && <div className="settings-message error" role="alert">{error}</div>}
      {(settings.capabilities ?? []).length > 0 && <div className="settings-message" role="status">当前入口能力：{(settings.capabilities ?? []).map((item) => item === "local" ? "本地执行" : item === "json" ? "结构化输出" : item).join(" · ")}</div>}
      <div className="provider-cards">
        <form className={`provider-card ${settings.kind === "openai-compatible" && settings.configured ? "connected" : ""}`} onSubmit={saveApi}>
          <header><span>01 / API</span><div className="provider-icon">↗</div><h2>OpenAI 兼容 API</h2><p>适用于 OpenAI、兼容网关与提供相同 Chat Completions 协议的服务。</p></header>
          <label>Base URL<input required type="url" value={settings.base_url} onChange={(event) => setSettings({ ...settings, base_url: event.target.value })} /></label>
          <label>模型名称<input required value={settings.model} placeholder="例如 gpt-5-mini" onChange={(event) => setSettings({ ...settings, model: event.target.value })} /></label>
          <label>API Key<input type="password" autoComplete="off" value={apiKey} placeholder="首次使用请填写；留空读取此地址的密钥" onChange={(event) => setApiKey(event.target.value)} /></label>
          <div className="provider-row"><label>超时（秒）<input type="number" min="5" max="600" value={settings.timeout} onChange={(event) => setSettings({ ...settings, timeout: Number(event.target.value) })} /></label><label>Temperature<input type="number" min="0" max="2" step="0.1" value={settings.temperature} onChange={(event) => setSettings({ ...settings, temperature: Number(event.target.value) })} /></label></div>
          <p className="privacy-note">
            {settings.key_storage === "keychain"
              ? "API Key 已安全保存在 macOS 钥匙串；留空可继续使用，填写新值会替换。"
              : settings.key_storage === "memory"
                ? "钥匙串写入失败，密钥目前仅在内存中；重启后需重新输入。"
                : "密钥不会写入浏览器存储、数据库、日志或导出文件；保存后将进入 macOS 钥匙串。"}
          </p>
          {settings.storage_warning && <p className="privacy-note" role="alert">{settings.storage_warning}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "正在测试…" : "保存并测试连接"}</button>
          {settings.key_saved || settings.key_storage === "memory" || settings.storage_warning ? (
            <button type="button" className="secondary-button" disabled={busy} onClick={deleteApiKey}>删除已保存密钥</button>
          ) : null}
        </form>

        <form className={`provider-card codex-card ${alreadyEnabled ? "connected" : ""}`} onSubmit={saveCodex}>
          <header><span>02 / CODEX</span><div className="provider-icon">⌘</div><h2>Codex CLI</h2><p>首次启用需检测本机 Codex；之后配置会保存在本机，重启无需重测。</p></header>

          <div className="codex-detect-row">
            <div>
              <strong>检测状态</strong>
              <span className={`codex-status status-${statusLabel}`}>{statusLabel}</span>
              {codexDetect?.version ? <small>版本 {codexDetect.version}</small> : null}
            </div>
            <button type="button" className="secondary-button" disabled={detecting || busy} onClick={detectCodex}>
              {detecting ? "正在检测…" : codexDetect || alreadyEnabled ? "重新检测" : "检测本机 Codex"}
            </button>
          </div>

          {codexFormVisible ? (
            <>
              <label>
                Codex 模型
                <AppleSelect
                  aria-label="Codex 模型"
                  required={(codexDetect?.models.length ?? 0) > 0}
                  value={codexModel}
                  placeholder="请选择模型"
                  options={modelOptions}
                  onChange={setCodexModel}
                />
              </label>
              {codexModel && (
                <p className="privacy-note">
                  {codexDetect?.models.find((item) => item.slug === codexModel)?.description || `将使用模型 ${codexModel}`}
                </p>
              )}
              <label className="privacy-confirm">
                <input
                  type="checkbox"
                  checked={settings.codex_confirmed || alreadyEnabled}
                  onChange={(event) => setSettings({ ...settings, codex_confirmed: event.target.checked })}
                />
                <span><strong>我理解数据流向</strong>JD 与去除邮箱、电话后的简历事实会发送给 Codex；任务目录不可写且用后即删。</span>
              </label>
              <div className="codex-flow"><span>本地应用</span><i>→</i><span>临时只读任务</span><i>→</i><span>结构化结果</span></div>
              <button
                className="primary-button"
                disabled={
                  busy
                  || !(settings.codex_confirmed || alreadyEnabled)
                  || ((codexDetect?.models.length ?? 0) > 0 && !codexModel)
                }
              >
                {busy ? "测试中（约 15–45 秒）…" : alreadyEnabled ? "重新测试 Codex" : "确认并测试 Codex"}
              </button>
            </>
          ) : (
            <p className="privacy-note">请先完成检测。未安装或未登录时，无法选择模型或启用 Codex。</p>
          )}
        </form>
      </div>
    </main>
  );
}
