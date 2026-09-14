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

## Fix round 1

- `ProviderServerError` 现在只在状态码为 5xx 时重试；404 等非 5xx 立即抛出，且只记录一次底层调用。
- jitter 应用后再强制 `max_delay_seconds`，确保传给 sleep 的最终延迟绝不超过上限。
- 每次 facade 调用无论成功、可重试失败或格式失败，都会在 `finally` 中采集该次 usage。OpenAI 已在结构化 JSON 验证前写入本次响应 usage，因此 workflow 随后的单次 JSON repair 不会漏记首个已计费响应。
- 用量聚合改为保守规则：任一次调用缺少某个 token 分量，该总分量即保持未知；不会以早先的部分和伪装成完整总量。
- Codex 与 OpenAI provider 暴露可选累计 `actual_call_count`。包装器优先使用本次调用前后的增量；不提供该字段的普通 `AIProvider` 仍按一次 facade 调用计数。覆盖了 Codex schema fallback 成功及 fallback 格式失败时均为两次 runner 调用的路径。
- RED：新增上述回归后，`uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py -v` 为 7 failed / 19 passed，失败与五项评审问题逐项对应。
- GREEN：同一聚焦集为 26 passed；`uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py tests/test_provider_api.py tests/test_codex_provider.py -v` 为 45 passed，6 个既有依赖弃用警告；`git diff --check` 通过。

## Final verification

- 2026-09-10：在 `codex/multi-agent-resume-optimization` tip 复跑 `tests/test_provider_retry.py tests/test_openai_provider.py tests/test_provider_api.py tests/test_codex_provider.py`，结果 45 passed。Task 5 关闭。
