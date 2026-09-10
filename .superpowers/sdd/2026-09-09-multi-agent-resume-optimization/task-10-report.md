# Task 10 报告：快速/深度优化 UI

## 实现

- `OptimizationLauncher`：默认快速模式，说明深度最多两轮返工。
- `OptimizationProgress`：阶段中文标签、预算摘要、取消/继续；不展示思维链。
- `WorkspacePage`：`startOptimization` 替代直调 `suggestPatch`；ready 时一次性把 `run.patch` 交给 `PatchReview`；进行中冻结模板切换。
- 匹配分析「生成适配建议」进入建议确认页再选模式启动。

## 验证

- `vitest`：Launcher / Progress / Workspace flow / app → 7 passed。

## 文件

- `web/src/components/OptimizationLauncher.tsx`
- `web/src/components/OptimizationProgress.tsx`
- `web/src/components/OptimizationLauncher.test.tsx`
- `web/src/components/OptimizationProgress.test.tsx`
- `web/src/components/TemplatePicker.tsx`
- `web/src/pages/WorkspacePage.tsx`
- `web/src/pages/WorkspacePage.flow.test.ts`
- `web/src/styles.css`
