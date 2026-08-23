# 中文 AI 简历证据工作台（MVP）

本地优先的中文简历创建与优化器。它围绕“岗位要求—个人事实—简历表述”建立可追溯关系，而不是单纯堆叠关键词。

当前版本支持：

- 创建校招、实习或社招项目，粘贴公司名称和职位描述（JD）；
- 上传 DOCX、PDF、TXT 简历，或通过结构化经历表单创建初稿；
- DOCX 优先提取原字体、颜色和布局线索，PDF 按文字块近似重建；
- 使用 OpenAI 兼容 API 或本机 Codex CLI 分析 JD、追问事实、生成修改建议；
- 每条 AI 修改都展示修改前后、JD 依据和事实依据，默认不勾选；
- 四套内置模板：清晰单栏、专业双栏、项目聚焦、经历纵深；
- 校招/实习使用紧凑的一页 A4 策略，超页时保留全部内容并暂停 PDF/DOCX 导出；
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
6. 逐项勾选需要接受的 AI 修改；每次应用或手动保存都会生成新版本。
7. 选择模板并导出，或进入面试/笔试训练。

## 数据与隐私

默认情况下，项目、事实、简历版本和练习记录保存在 `backend/.data/resume.db`。这是本地 SQLite 文件，不会自动同步。

OpenAI 兼容 API 的密钥：

- 仅保存在运行中的后端进程内存；
- 不写入 SQLite、浏览器存储、日志、JSON、DOCX 或 Codex 上下文；
- 后端重启后需要重新输入；
- 前端提交连接设置后会立即清空密钥输入框。

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
