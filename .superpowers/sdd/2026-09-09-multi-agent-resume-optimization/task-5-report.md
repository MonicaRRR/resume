# Task 5 报告：有界 Provider 重试与可选用量统计

## 实现

- 新增 `ProviderNetworkError`、带状态码的 `ProviderServerError`、带可选 `Retry-After` 秒数的 `ProviderRateLimitError`，并保留认证、超时和 JSON 格式错误的既有分类。
- 新增 `RetryingProvider`、`RetryPolicy` 和 `ProviderCallStats`。默认最多尝试 3 次；仅网络、5xx、429 和超时会重试，认证与格式失败立即返回给上层既有的一次 JSON 修复流程。
- 延迟采用有上限的指数退避；数值 `Retry-After` 优先，sleep 和 jitter 均可注入以支持确定性测试。
- 每次实际底层 provider 调用都会计数。OpenAI-compatible 响应会读取 `usage.prompt_tokens` 与 `usage.completion_tokens`；没有 usage 的 provider（包括 Codex）保持为 `None`，不虚构零 token。
- OpenAI-compatible provider 将 429、5xx、HTTP 传输错误分别映射为限流、服务端和网络错误，未改变认证、超时、端点、结构化 JSON 验证或 workflow 中的一次 JSON 修复行为。

## TDD 与验证

- RED：先新增 provider retry 和 OpenAI 状态测试，运行 `uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py -v`，预期因 `resume_mvp.provider_retry` 和新错误分类不存在而收集失败。
- GREEN：完成最小实现后，同一测试集为 19 passed。
- 简报要求回归：`cd backend && uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py tests/test_provider_api.py -v`：29 passed，6 个现有依赖弃用警告。
- `git diff --check`：通过，无空白错误。

## 文件与提交

- `backend/resume_mvp/providers/base.py`
- `backend/resume_mvp/providers/openai_compatible.py`
- `backend/resume_mvp/provider_retry.py`
- `backend/tests/test_provider_retry.py`
- `backend/tests/test_openai_provider.py`
- `.superpowers/sdd/2026-09-09-multi-agent-resume-optimization/task-5-report.md`
- Commit：`feat: add bounded provider retry handling`（哈希见交接信息）。

## Concerns

- `ProviderCallStats.usage` 仅累加 provider 实际返回的 token 字段；缺失字段保持不可用，避免将未知消耗误报为零。
