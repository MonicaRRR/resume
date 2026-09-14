# Task 7 报告：持久化优化编排器

## 实现

- 新增 `OptimizationOrchestrator`：`create_run` / `execute` / `cancel` / `resume`。
- 深度模式：analysis → baseline_render → (writer → render → review → quality) 有界返工；快速模式跳过 reviewer。
- 步骤按 input hash 复用 24h 内成功 checkpoint；恢复时若活跃版本变化则 `adopt_optimization_input_version`，分析可复用、下游因 hash 变化失效。
- `requires_user_input` 优先进入 `waiting_for_user`；步骤间观察 `cancel_requested`。
- 模型调用预算 `max_model_calls`；同 provider 使用 `asyncio.Semaphore(1)`。
- `AppServices` 增加 `optimization`；`create_app` 先构造 repository/providers，再注入 orchestrator。

## TDD 与验证

- RED/GREEN：`tests/test_optimization_orchestrator.py` 5 passed。
- 回归：`tests/test_patches.py` passed。
- `tests/test_export_api.py` 因既有 `PROVIDER_REQUIRED` 创建项目门槛失败（与本任务无关，pre-existing）。

## 文件

- `backend/resume_mvp/optimization_orchestrator.py`
- `backend/resume_mvp/api/dependencies.py`
- `backend/resume_mvp/main.py`
- `backend/resume_mvp/repositories.py`（`adopt_optimization_input_version`）
- `backend/tests/test_optimization_orchestrator.py`
