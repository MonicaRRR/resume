# Task 11 报告：补丁卡片展示布局与质量证据

## 实现

- `PatchReview` 接收可选 `optimization`：展示 JD 覆盖、页数/密度变化、表达分，并标注“不代表录取概率”。
- 单条建议展示 `expected_layout_benefit`，并解析 `layout_issue_ids` 对应问题文案。
- 未达标却停止返工时用 `role="alert"` 提示「已达到自动返工上限」。
- 同意集合仍默认空；通过质量门槛不会自动勾选。

## 验证

- `vitest` PatchReview / Workspace flow / ResumePreview → 10 passed。

## 文件

- `web/src/components/PatchReview.tsx`
- `web/src/components/PatchReview.test.tsx`
- `web/src/pages/WorkspacePage.tsx`
- `web/src/styles.css`
