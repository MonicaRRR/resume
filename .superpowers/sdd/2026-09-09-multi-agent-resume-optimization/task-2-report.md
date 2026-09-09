# Task 2 报告：确定性优化质量门槛

## 实现

- 新增 `backend/resume_mvp/optimization_quality.py`。
- `evaluate_quality` 对每个 patch operation 强制校验已知事实来源；空 patch 视为完全可追溯。
- 固化 JD 覆盖率 80%、表达评分 80、校招/实习单页、严重排版问题和事实性门槛，并返回全部失败原因。
- `should_refine` 在质量通过、达到 `max_refinements` 或连续两次质量向量无改善时停止；质量向量为事实性、页策略、严重问题数（负值）、JD 覆盖率、表达评分。
- 新增 `backend/tests/test_optimization_quality.py`，测试使用自包含的 Pydantic 对象构造，不依赖未定义 fixture。

## TDD / 测试

- RED：`uv run pytest tests/test_optimization_quality.py -v`；因 `resume_mvp.optimization_quality` 不存在而收集失败（预期缺少实现）。
- GREEN：`uv run pytest tests/test_optimization_quality.py tests/test_matching.py tests/test_patches.py -v`；23 passed。
- 完整后端：`uv run pytest -q`；110 passed，8 failed，6 warnings。失败集中在既有 export/practice/preview API 测试的项目创建响应缺少 `id`，与本次文件无关。

## 文件与提交

- 文件：`backend/resume_mvp/optimization_quality.py`、`backend/tests/test_optimization_quality.py`
- Commit：本次最终提交（哈希在交接信息中给出）。

## 自查

- `git diff --check` 通过；提交后工作树干净。
- 未添加模型调用；相关 matching/patch 回归通过。

## Concerns

- 完整后端测试仍有 8 个既有 API 测试失败，建议后续排查项目创建端点返回错误的问题。

## 修复轮 1

- RED：新增 `test_stops_at_hard_iteration_two_even_if_budget_is_larger` 后，旧实现运行 `uv run pytest tests/test_optimization_quality.py -v` 为 1 failed / 8 passed；失败为 `iteration=2,max_refinements=3` 得到 `True`。
- 同时将连续无改善测试改为 `iteration=1,max_refinements=2`，确保预算未耗尽时实际执行无改善停止分支。
- GREEN：将 `should_refine` 的预算限制改为 `min(max_refinements, 2)`，并运行 `uv run pytest tests/test_optimization_quality.py tests/test_matching.py tests/test_patches.py -v`，24 passed。
- 修复文件：`backend/resume_mvp/optimization_quality.py`、`backend/tests/test_optimization_quality.py`。
