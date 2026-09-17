# 中文 AI 简历证据工作台（MVP）

本地优先的中文简历创建与优化器。它围绕“岗位要求—个人事实—简历表述”建立可追溯关系，而不是单纯堆叠关键词。

当前版本支持：

- 创建校招、实习或社招项目，粘贴公司名称和职位描述（JD）；
- 上传 DOCX、PDF、TXT 简历，或通过结构化经历表单创建初稿；
- DOCX 优先提取原字体、颜色和布局线索，PDF 按文字块近似重建；
- 使用 OpenAI 兼容 API 或本机 Codex CLI 分析 JD、追问事实、生成修改建议；
- 支持**快速优化**与**深度优化**双模式多 Agent 闭环：生成 → 真实模板渲染检测 → 独立审查 → 有限返工；
- 每条 AI 修改都展示修改前后、JD 依据、事实依据与（深度模式下的）排版/质量摘要，默认不勾选；
- 四套内置模板：清晰单栏、专业双栏、项目聚焦、经历纵深；
- 校招/实习强制使用一页 A4：超页时优化不能标记完成、不能应用补丁，并暂停 PDF/DOCX/LaTeX 导出；
- 社招简历不限制页数，允许自然分页；
- 导出 PDF（系统打印）、可编辑 DOCX、JSON 和 Codex Markdown 上下文；
- 根据当前 JD 与简历进行中文模拟面试和笔试练习。

## 技术结构

- 后端：FastAPI、Pydantic、SQLAlchemy、SQLite；
- 前端：React、TypeScript、TanStack Query、Zustand、Vite；
- 文档解析与导出：python-docx、PyMuPDF；
- 测试：Pytest、Vitest、Testing Library、Playwright。

应用是单机单用户 MVP，不包含登录、云同步和多人协作。

## 环境要求

- Python 3.12 或更高版本；
- [uv](https://docs.astral.sh/uv/)；
- Node.js 20 或更高版本；
- [pnpm](https://pnpm.io/)；
- 真实 PDF 预览与深度优化排版检测需要本机可用的 [LibreOffice](https://www.libreoffice.org/)（`soffice`）；
- 使用 Codex 模式时，需要已安装并登录可用的 `codex` CLI。

## 安装与启动

```bash
make install
make dev
```

浏览器打开 <http://127.0.0.1:5173>。后端监听 <http://127.0.0.1:8000>，健康检查为 <http://127.0.0.1:8000/api/health>。

`make dev` 会同时启动前后端；按 `Ctrl+C` 会结束两个进程。

## 首次使用

1. 打开“模型设置”。
2. 选择一种连接方式：
   - OpenAI 兼容 API：填写 Base URL、模型名称和 API Key，点击“保存并测试连接”；
   - Codex CLI：阅读数据流向说明，勾选确认后测试 Codex。
3. 回到首页，新建求职项目并选择校招、实习或社招。
4. 上传已有简历，或选择“从经历开始”。
5. 分析 JD、回答缺失事实追问、查看匹配分析。
6. 进入「建议确认」，选择快速或深度优化；完成后逐项勾选需要接受的修改。应用或手动保存都会生成新版本。
7. 选择模板并导出，或进入面试/笔试训练。

### 浏览器一键填表（实验）

在招聘网站打开投递表单后，可用 Chrome/Edge 扩展把本机经历库填入**当前活动页**（缺项留空并提醒，不自动投递）。详见 [`extension/README.md`](extension/README.md)。

### 冒烟测试假经历库

本地可用虚构人物「林晓舟」填充经历库，并创建一个已带 JD 分析与匹配报告的求职项目「冒烟·后端平台研发」：

```bash
make seed-smoke
```

写入 `backend/.data/resume.db`：会覆盖当前经历库；同名冒烟项目会先删再建。内容全部虚构，勿当真投递。`make seed-smoke` 结束时会打印项目链接；也可只跑：

```bash
cd backend && .venv/bin/python scripts/seed_smoke_project.py
```

### 白盒沙箱（保留中间产物）

不调用真实 Codex/API，用假模型跑完整优化并落盘逐步检查点：

```bash
make whitebox          # 默认社招夹具
make whitebox-campus   # 校招夹具（含一页策略）
```

产物在 `backend/.data/whitebox/`（含 PDF、逐步 JSON、`README.md`）。

## 快速优化与深度优化

| | 快速优化 | 深度优化 |
|---|---|---|
| 默认 | 是 | 否，需主动选择 |
| 流程 | 一次生成候选补丁 | 初始生成 + 最多两轮返工（最多约三次 Writer 调用） |
| 排版 | 不做真实 PDF 几何返工 | 用当前模板导出 DOCX→PDF，检测页数/短尾行等 |
| 审查 | 跳过独立 Reviewer | 独立评分与返工指令；连续两轮无改善则停止 |
| 预算 | 计入同一任务的模型调用上限（默认 12 次 / 120k tokens） | 同左 |

共同点：

- 全部逻辑 Agent 使用你当前配置的同一个模型服务；
- 电话、邮箱、微信、住址、证件照不进入审查上下文；日志不写 API Key 与完整简历正文；
- 429 / 5xx / 网络 / 超时只重试失败步骤，并尊重 `Retry-After`；
- 运行可取消；进程中断后重启会把进行中的任务标为失败并可点「继续运行」；同输入在 24 小时内可复用成功步骤检查点；
- 质量分数是「本次简历相对该 JD 的内部优化指标」，**不代表录取概率**；
- 在你逐条确认之前，不会创建正式简历版本或覆盖当前草稿。

## 数据与隐私

默认情况下，项目、事实、简历版本和练习记录保存在 `backend/.data/resume.db`。这是本地 SQLite 文件，不会自动同步。

OpenAI 兼容 API 的密钥：

- 在 macOS 上保存到系统钥匙串，后端使用时载入进程内存；
- 不写入 SQLite、浏览器存储、日志、JSON、DOCX 或 Codex 上下文；
- 后端重启后自动恢复；首次升级到此版本需重新输入一次；
- 密钥按 API 地址的协议、主机和端口隔离；同一地址留空可复用，填入新值可替换；
- 设置页支持删除当前已保存密钥。切换服务不会删除旧服务的密钥；
- 钥匙串写入失败时会明确提示，仅在内存中保留本次密钥，不回退到明文文件；
- 前端提交连接设置后会立即清空密钥输入框。

钥匙串访问受 macOS 权限控制；首次访问可能出现系统授权提示。开发版通过 Python 访问钥匙串，同一 Python 可执行文件运行的其他程序可能共享其访问权限，详见 [keyring 安全说明](https://keyring.readthedocs.io/en/stable/#security-considerations)。目前仅 macOS 提供持久保存，其他平台仅保留在内存中。

使用外部 API 时，完成任务所需的 JD、简历内容与事实会发送给所配置的 API 服务。使用 Codex 时，会发送 JD 和去除电话、邮箱后的必要简历事实；每次请求使用临时只读目录，任务结束后删除。上传文件解析、版本管理和导出本身均在本机完成。

## 文件与模板规则

- 上传上限：10 MiB；
- 支持：UTF-8 TXT、DOCX、文字型 PDF；
- 暂不支持扫描 PDF 的 OCR；
- DOCX 可提取常见字体、字号和强调色；复杂浮动元素、文本框、页眉页脚可能无法完全复刻；
- PDF 没有可靠的可编辑模板结构，因此只做近似还原；
- 切换内置模板只改变呈现，不修改简历内容；
- 一页容量由前后端共享的确定性文本容量规则预判，最终仍建议在系统打印预览中检查。

## 测试与构建

```bash
make test
make build
```

首次运行浏览器测试前安装 Chromium：

```bash
cd web
pnpm exec playwright install chromium
cd ..
make e2e
```

端到端测试会设置 `RESUME_MVP_TEST_PROVIDER=1`，启用只返回固定结果的测试模型。正常运行没有这个环境变量，因此不能选择或调用 `test` 模型。

## 常用命令

```bash
make install   # 安装 Python 与前端依赖
make dev       # 同时启动前后端开发服务器
make seed-smoke # 写入冒烟测试用假经历库（覆盖当前经历库）
make whitebox-campus # 校招白盒沙箱（中间产物落盘）
make test      # 后端与前端单元/组件测试
make build     # 后端导入检查与前端生产构建
make e2e       # 完整浏览器用户旅程
```

## 已知限制与后续方向

- 当前界面和 AI 提示仅支持中文；
- 本地模型暂未接入。后续可在 `backend/resume_mvp/providers/` 增加 Qwen3.8 27B 适配器，并通过现有 `AIProvider.complete_json` 接口注册；
- 当前不包含 OCR、账号、云同步、招聘平台投递或实时语音面试；
- 模板库为项目内四套可维护模板，没有在线模板市场；
- Codex 集成通过本机 CLI 完成，不会直接控制或嵌入 Codex 桌面聊天页面；导出的 Markdown 上下文可粘贴到任意 Codex 聊天继续处理。
