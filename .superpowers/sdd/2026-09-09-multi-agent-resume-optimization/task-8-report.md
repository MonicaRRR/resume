# Task 8 报告：优化任务 HTTP API

## 实现

- 新增 `/api/projects/{project_id}/optimization-runs`：创建（202 + 后台 execute）、查询、取消、恢复。
- 校验项目、活跃简历版本、provider，以及 run 归属（跨项目返回 404）。
- `prepare_resume`：`waiting_for_user` 可采纳新版本；中断 `failed` 保持冻结输入。
- 启动时 `fail_stale_optimization_runs`，将 in-flight 状态标为 failed（“上次运行被中断，可点击继续”），不自动外呼模型。
- 保留既有 `/resume/suggest` 兼容路径。

## 验证

- `pytest tests/test_optimization_api.py tests/test_optimization_orchestrator.py tests/test_project_api.py tests/test_health.py -v` → 18 passed。

## 文件

- `backend/resume_mvp/api/optimization.py`
- `backend/resume_mvp/main.py`
- `backend/resume_mvp/repositories.py`
- `backend/resume_mvp/optimization_orchestrator.py`
- `backend/tests/test_optimization_api.py`
