# Task 12 报告：评测夹具、端到端与文档

## 实现

- 三个虚构评测用例（校招通过 / 实习超页 / 社招不可追溯）+ `test_optimization_eval.py` 断言 `evaluate_quality` 与 `expected_quality` 一致。
- E2E Provider 支持 `OptimizationReview`：首轮 72、返工后 88；审查步骤短暂延迟以便 UI 轮询可见。
- Playwright：快速全流程 + 深度优化（审查返工后仍需用户确认）；launcher 用 label 点击避免 radio 被 `<strong>` 挡住。
- README：快速/深度差异、≤3 次 Writer、LibreOffice、429/取消/检查点/中断恢复、敏感字段排除、分数≠录取、必须用户确认。
- Playwright webServer 改用 `.venv/bin/uvicorn`；顺带修复阻塞 `pnpm build` 的既有 TS 问题（`match_report`、PDF 下载空 draft）。

## 验证

- `backend/.venv/bin/pytest tests/test_optimization_eval.py -v` → 3 passed
- 前端 `vitest --run` → 28 passed
- `pnpm build` → 通过
- `PLAYWRIGHT_BROWSERS_PATH=… make e2e` → 2 passed（约 23s）
- `git diff --check` → 无输出

## 基线观察（Task 12 收尾）

- 快速：一次生成即可进入审阅（e2e 约 9s 全旅程含后续步骤）。
- 深度：同输入约 5/12 次模型调用、1 轮返工后达标（表达分 88）；须用户「同意这项」才落版本。

## 文件

- `backend/tests/fixtures/optimization_eval_cases.json`
- `backend/tests/test_optimization_eval.py`
- `backend/resume_mvp/providers/e2e.py`
- `web/e2e/resume-flow.spec.ts`
- `web/playwright.config.ts`
- `web/src/pages/HomePage.test.tsx`
- `web/src/pages/WorkspacePage.tsx`
- `README.md`
