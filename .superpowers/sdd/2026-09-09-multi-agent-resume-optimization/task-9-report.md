# Task 9 报告：前端优化 run 合约与轮询

## 实现

- `types.ts`：新增 OptimizationMode/Status、LayoutReport、Review、Quality、OptimizationRun 的 Zod 合约；补丁操作默认 `layout_issue_ids` / `expected_layout_benefit`。
- `api/client.ts`：create / get / cancel / resume 四个方法。
- `useOptimizationRun`：创建后按 1s 轮询，终端态（ready/failed/cancelled/waiting_for_user）停止。

## 验证

- `pnpm exec vitest run src/hooks/useOptimizationRun.test.tsx src/components/PatchReview.test.tsx` → 4 passed。

## 文件

- `web/src/types.ts`
- `web/src/api/client.ts`
- `web/src/hooks/useOptimizationRun.ts`
- `web/src/hooks/useOptimizationRun.test.tsx`
