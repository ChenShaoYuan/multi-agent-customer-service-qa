# Multi-Agent Customer Service Quality Audit

基于 LangGraph 的多 Agent 客服质检项目，已实现四周工程任务：输入适配、确定性预检、红线门控、三维并行评分、ReAct 汇总、加权评级、反馈、异常降级、HTTP MCP 规则服务与真实数据评测。

模型理解语义，Python 校验证据并计算分数。最终结果分为 `completed`、`blocked`、`manual_review`；资料不足和技术失败不会被当成客服零分。

## 运行完整流程

使用 Python 3.11，在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env  # 仅首次配置，已有.env不要覆盖
.\.venv\Scripts\python.exe -m customer_service_qa --demo --format markdown --output outputs/week4-demo.md
```

离线演示使用固定答案，得分96，评级优秀。真实运行先填写 `.env`，参见 [模型连接](docs/model-connection.md)，再执行：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week4/examples/input.json --output outputs/week4-live.json --log-output logs/audit-events.jsonl
```

默认执行第四周完整工作流；`--week 2`、`--week 3` 保留阶段入口。`--preflight-only` 只做确定性预检。JSON 和 Markdown 分别运行会分别调用模型；同一次结果的排版转换使用 `reporting.render_markdown()`。

## HTTP MCP 与批量评测

终端一启动本机规则服务：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa.mcp_server
```

终端二执行真实历史会话评测，成功记录可断点续跑：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa.evaluation --rules-transport mcp --output outputs/week4/history --workers 2 --resume
```

已保存的评测要求源码、配置、输入及运行模式一致；修改后应使用新的输出目录。详见 [MCP 服务](docs/week4/mcp-service.md) 与 [真实评测报告](docs/week4/evaluation-report.md)。

## 四周交付

| 周次 | 已完成内容 | 文档 |
| --- | --- | --- |
| 第一周 | 规则映射、预检清单、State、图设计、技术方案 | [设计与验收](docs/week1/acceptance-checklist.md) |
| 第二周 | 输入适配、14项预检、红线Agent、条件路由、轨迹 | [第二周](docs/week2/README.md) |
| 第三周 | 三维Agent、22类专业规则、评分证据校验、并行与隔离 | [第三周](docs/week3/README.md) |
| 第四周 | ReAct汇总、去重、评级反馈、降级告警、MCP、真实跑批 | [第四周及总验收](docs/week4/README.md) |

总分 = 服务流程原始分/25×20 + 专业服务原始分/50×40 + 沟通规范原始分/25×40。跨维度同一问题先按可审计策略去重，再计算总分。≥90优秀，60～<90合格，<60严重问题；红线独立判为严重不合格。

## 目录与数据边界

- `src/customer_service_qa/`：运行代码；`configs/`：评分、预检和汇总策略。
- `data/raw/`：原始100条历史样本与22类专业规则；`data/evaluation/`：12条规则参考用例。
- `docs/week1/`～`docs/week4/`：阶段设计、实现、示例及验收证据。
- `scripts/`：接口检查、参考用例及示例生成；`tests/`：离线与真实本地HTTP测试。
- `.env`、`outputs/`、`logs/`：本地密钥、逐条评测结果、事件日志，均不提交Git。

原始历史数据没有明确角色与时间戳。角色采用标注过的推断，缺失时效信息会转人工复核。参考用例是根据规则编写的合成预期，未经人工独立标注，参考一致率与格式通过率均不代表真实业务准确率。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=customer_service_qa --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/generate_week4_examples.py
```

依赖范围见 `pyproject.toml`；`requirements.lock` 为本次 Windows/Python 3.11 环境快照，含 Windows 专用依赖，其他系统优先按 pyproject 安装。部署范围是本地命令行与本机 MCP 服务，尚未提供公网鉴权、人工审核界面或生产数据库。
