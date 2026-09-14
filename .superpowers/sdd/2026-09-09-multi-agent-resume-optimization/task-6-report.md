# Task 6 报告：布局感知 Writer 与独立 Reviewer

## 实现

- 新增 `generate_optimization_patch`：把 JD 分析、匹配报告、事实、可选排版问题与上一轮审查反馈组成最小上下文，生成局部 `ResumePatch`。
- Writer 约束强调保留数字/技术/JD 词、优先删除低信息措辞、禁止无意义扩写；版面触发时必须引用真实 `layout_issue_ids`。
- 生成后先走既有 `_ground_patch_operations` 事实落地，再丢弃引用未知 layout id 的操作。
- 新增 `review_optimization_candidate`：独立审查候选简历，提示明确要求“不能直接生成替换文本”，只返回评分、驳回与返工指令。
- `_safe_resume` 额外清空 `location`（住址），审查与生成提示都不发送电话、邮箱、微信、住址和证件照原图。

## TDD 与验证

- RED：新增 `tests/test_optimization_agents.py`，收集阶段因缺少 `optimization_agents` 失败。
- GREEN：`pytest tests/test_optimization_agents.py tests/test_ai_workflows.py tests/test_evidence_match.py -v` → 19 passed。

## 文件

- `backend/resume_mvp/optimization_agents.py`
- `backend/resume_mvp/ai_workflows.py`
- `backend/tests/test_optimization_agents.py`
