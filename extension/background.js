const API_BASE = "http://127.0.0.1:8000";

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  if (!tab?.id) throw new Error("未找到当前活动标签页");
  return tab;
}

async function ensureContentScript(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["content.js"],
  });
}

function sendTabMessage(tabId, message) {
  return chrome.tabs.sendMessage(tabId, message);
}

async function fetchPlan(payload) {
  let response;
  try {
    response = await fetch(`${API_BASE}/api/autofill/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("无法连接本机后端（http://127.0.0.1:8000）。请先运行 make dev。");
  }
  if (!response.ok) {
    let detail = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      detail = body?.detail?.message || body?.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : "生成填表计划失败");
  }
  return response.json();
}

async function resolveProvider() {
  try {
    const response = await fetch(`${API_BASE}/api/settings/providers`);
    if (!response.ok) return null;
    const state = await response.json();
    if (state.configured && state.kind) return state.kind;
  } catch {
    /* rules-only */
  }
  return null;
}

async function fillActiveTab() {
  const tab = await getActiveTab();
  if (!tab.url || tab.url.startsWith("chrome://") || tab.url.startsWith("chrome-extension://")) {
    throw new Error("当前页无法注入脚本，请打开招聘网站的投递表单页再试。");
  }
  await ensureContentScript(tab.id);
  const collected = await sendTabMessage(tab.id, { type: "COLLECT_FIELDS" });
  if (!collected?.ok) throw new Error("采集表单字段失败");

  const provider = await resolveProvider();
  const plan = await fetchPlan({
    fields: collected.fields,
    page_url: collected.url || tab.url || "",
    page_title: collected.title || tab.title || "",
    provider,
  });

  const applied = await sendTabMessage(tab.id, {
    type: "APPLY_ACTIONS",
    actions: plan.actions || [],
  });

  return {
    tabTitle: collected.title || tab.title || "",
    tabUrl: collected.url || tab.url || "",
    plan,
    applied: applied?.applied ?? 0,
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "FILL_ACTIVE_TAB") return false;
  fillActiveTab()
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: error?.message || String(error) }));
  return true;
});
