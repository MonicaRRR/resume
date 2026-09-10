import type { OptimizationRun, OptimizationStatus } from "../types";

export const optimizationStageLabels = {
  queued: "等待开始",
  analyzing: "分析事实与岗位",
  waiting_for_user: "等待补充事实",
  optimizing: "生成修改方案",
  rendering: "检查真实模板排版",
  reviewing: "独立质量审查",
  retry_wait: "模型繁忙，等待重试",
  ready_for_user: "可以逐条审阅",
  failed: "优化未完成",
  cancelled: "已取消",
} as const satisfies Record<OptimizationStatus, string>;

export function OptimizationProgress({
  run,
  onCancel,
  onResume,
}: {
  run: OptimizationRun;
  onCancel?: () => void;
  onResume?: () => void;
}) {
  const stage = optimizationStageLabels[run.status];
  const canCancel = !["ready_for_user", "failed", "cancelled", "waiting_for_user"].includes(run.status);
  const canResume = run.status === "failed" || run.status === "waiting_for_user";

  return (
    <section className="optimization-progress" aria-live="polite">
      <div className="panel-heading">
        <div>
          <span className="panel-index">RUN</span>
          <h2>{stage}</h2>
        </div>
        <span>{run.mode === "deep" ? "深度优化" : "快速优化"}</span>
      </div>
      {run.message && <p className="optimization-progress-message">{run.message}</p>}
      <dl className="optimization-progress-meta">
        <div>
          <dt>轮次</dt>
          <dd>{run.iteration}</dd>
        </div>
        <div>
          <dt>模型调用</dt>
          <dd>
            {run.call_count}/{run.max_model_calls}
          </dd>
        </div>
        {run.quality && (
          <div>
            <dt>质量</dt>
            <dd>{run.quality.passed ? "已达标" : run.quality.reasons[0] || "未达标"}</dd>
          </div>
        )}
      </dl>
      <div className="button-row">
        {canCancel && onCancel && (
          <button type="button" className="secondary-button" onClick={onCancel}>
            取消
          </button>
        )}
        {canResume && onResume && (
          <button type="button" className="primary-button" onClick={onResume}>
            继续运行
          </button>
        )}
      </div>
    </section>
  );
}
