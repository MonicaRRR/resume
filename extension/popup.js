const tabMeta = document.getElementById("tab-meta");
const fillBtn = document.getElementById("fill-btn");
const resultEl = document.getElementById("result");

async function showActiveTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) {
      tabMeta.textContent = "未找到活动标签页";
      return;
    }
    tabMeta.textContent = tab.title || tab.url || "当前活动页";
  } catch {
    tabMeta.textContent = "无法读取当前标签页";
  }
}

function renderResult(payload) {
  resultEl.hidden = false;
  if (!payload.ok) {
    resultEl.innerHTML = `<h2 class="error">填写失败</h2><p class="error"></p>`;
    resultEl.querySelector("p").textContent = payload.error || "未知错误";
    return;
  }
  const { plan, applied, tabTitle } = payload.result;
  const reminders = plan.empty_reminders || [];
  const warnings = plan.warnings || [];
  const unmatched = plan.unmatched_fields || [];
  const reminderItems = reminders
    .map((item) => `<li>${escapeHtml(item.label || item.field_id)}：${escapeHtml(item.reason)}</li>`)
    .join("");
  const warningItems = warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  resultEl.innerHTML = `
    <h2 class="ok">已写入 ${applied} 项（模式：${escapeHtml(plan.mode)}）</h2>
    <p class="meta">${escapeHtml(tabTitle || "")}</p>
    ${
      reminders.length
        ? `<h2 class="warn">以下项经历库没有，已留空</h2><ul class="warn">${reminderItems}</ul>`
        : `<p class="ok">没有缺项提醒。</p>`
    }
    ${warnings.length ? `<h2 class="warn">警告</h2><ul class="warn">${warningItems}</ul>` : ""}
    ${
      unmatched.length
        ? `<p class="meta">仍未匹配字段：${unmatched.length} 个（请人工核对页面）。</p>`
        : ""
    }
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

fillBtn.addEventListener("click", async () => {
  fillBtn.disabled = true;
  fillBtn.textContent = "正在填写…";
  resultEl.hidden = true;
  try {
    const payload = await chrome.runtime.sendMessage({ type: "FILL_ACTIVE_TAB" });
    renderResult(payload);
  } catch (error) {
    renderResult({ ok: false, error: error?.message || String(error) });
  } finally {
    fillBtn.disabled = false;
    fillBtn.textContent = "填写当前页";
  }
});

showActiveTab();
