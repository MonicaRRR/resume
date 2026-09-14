import { useState } from "react";

import type { OptimizationMode } from "../types";

export function OptimizationLauncher({
  disabled = false,
  busy = false,
  onStart,
}: {
  disabled?: boolean;
  busy?: boolean;
  onStart: (mode: OptimizationMode) => void;
}) {
  const [mode, setMode] = useState<OptimizationMode>("quick");

  return (
    <section className="optimization-launcher" aria-labelledby="optimization-launcher-title">
      <div className="panel-heading">
        <div>
          <span className="panel-index">04</span>
          <h2 id="optimization-launcher-title">简历优化</h2>
        </div>
        <span>默认快速</span>
      </div>
      <p className="panel-note">
        快速优化适合先出一版可审阅建议；深度优化会做真实排版检测与独立审查，并允许最多两轮返工。
      </p>
      <fieldset className="optimization-mode-selector">
        <legend>优化模式</legend>
        <label className={mode === "quick" ? "active" : ""}>
          <input
            type="radio"
            name="optimization-mode"
            value="quick"
            checked={mode === "quick"}
            disabled={disabled || busy}
            onChange={() => setMode("quick")}
          />
          <strong>快速优化</strong>
          <small>一次生成，直接进入逐条确认</small>
        </label>
        <label className={mode === "deep" ? "active" : ""}>
          <input
            type="radio"
            name="optimization-mode"
            value="deep"
            checked={mode === "deep"}
            disabled={disabled || busy}
            onChange={() => setMode("deep")}
          />
          <strong>深度优化</strong>
          <small>排版检测与独立审查，适合精修投递稿</small>
        </label>
      </fieldset>
      <div className="button-row">
        <button
          type="button"
          className="primary-button"
          disabled={disabled || busy}
          onClick={() => onStart(mode)}
        >
          {busy ? "正在启动…" : mode === "quick" ? "开始快速优化" : "开始深度优化"}
        </button>
      </div>
    </section>
  );
}
