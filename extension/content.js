(() => {
  if (window.__resumeAutofillLoaded) return;
  window.__resumeAutofillLoaded = true;

  const SKIP_TYPES = new Set([
    "password",
    "file",
    "hidden",
    "checkbox",
    "radio",
    "button",
    "submit",
    "reset",
    "image",
  ]);

  function visible(el) {
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function labelFor(el) {
    if (el.id) {
      const byFor = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (byFor?.textContent) return byFor.textContent.trim();
    }
    const parentLabel = el.closest("label");
    if (parentLabel?.textContent) {
      return parentLabel.textContent.replace(el.value || "", "").trim().slice(0, 80);
    }
    const labelled = el.getAttribute("aria-labelledby");
    if (labelled) {
      return labelled
        .split(/\s+/)
        .map((id) => document.getElementById(id)?.textContent?.trim() || "")
        .filter(Boolean)
        .join(" ");
    }
    return "";
  }

  function nearbyText(el) {
    const prev = el.previousElementSibling;
    if (prev && /^(LABEL|SPAN|DIV|P|TD|TH)$/i.test(prev.tagName)) {
      return (prev.textContent || "").trim().slice(0, 80);
    }
    const parent = el.parentElement;
    if (!parent) return "";
    const clone = parent.cloneNode(true);
    clone.querySelectorAll("input, textarea, select, button").forEach((node) => node.remove());
    return (clone.textContent || "").trim().slice(0, 80);
  }

  function collectFields() {
    const nodes = [
      ...document.querySelectorAll("input, textarea, select"),
    ];
    const fields = [];
    nodes.forEach((el, index) => {
      const tag = el.tagName.toLowerCase();
      const type = (el.getAttribute("type") || (tag === "textarea" ? "textarea" : tag === "select" ? "select" : "text")).toLowerCase();
      if (SKIP_TYPES.has(type)) return;
      if (el.disabled || el.readOnly) return;
      if (!visible(el)) return;
      const id = el.dataset.resumeAutofillId || `raf-${index}-${tag}-${type}`;
      el.dataset.resumeAutofillId = id;
      const options =
        tag === "select"
          ? [...el.options].map((opt) => (opt.textContent || opt.value || "").trim()).filter(Boolean)
          : [];
      fields.push({
        id,
        tag,
        type,
        name: el.getAttribute("name") || "",
        label: labelFor(el),
        placeholder: el.getAttribute("placeholder") || "",
        aria_label: el.getAttribute("aria-label") || "",
        nearby_text: nearbyText(el),
        options,
      });
    });
    return fields;
  }

  function setNativeValue(el, value) {
    const proto =
      el.tagName.toLowerCase() === "textarea"
        ? window.HTMLTextAreaElement.prototype
        : el.tagName.toLowerCase() === "select"
          ? window.HTMLSelectElement.prototype
          : window.HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor?.set) descriptor.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function applyActions(actions) {
    let applied = 0;
    for (const action of actions || []) {
      const el = document.querySelector(`[data-resume-autofill-id="${CSS.escape(action.field_id)}"]`);
      if (!el) continue;
      if (el.tagName.toLowerCase() === "select") {
        const match = [...el.options].find(
          (opt) =>
            opt.value === action.value ||
            (opt.textContent || "").trim() === action.value ||
            (opt.textContent || "").includes(action.value),
        );
        if (match) {
          setNativeValue(el, match.value);
          applied += 1;
        }
        continue;
      }
      setNativeValue(el, action.value);
      applied += 1;
    }
    return { applied };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "COLLECT_FIELDS") {
      sendResponse({ ok: true, fields: collectFields(), title: document.title, url: location.href });
      return true;
    }
    if (message?.type === "APPLY_ACTIONS") {
      sendResponse({ ok: true, ...applyActions(message.actions) });
      return true;
    }
    return false;
  });
})();
