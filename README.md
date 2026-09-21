# Multi-Agent Customer Service Quality Audit

基于 LangGraph 的多 Agent 客服质检项目。

## Current status

当前完成 **Week 2：确定性预检与主控红线拦截**。

已完成：

- 客服质检规则映射；
- 红线和确定性预检边界；
- LangGraph 节点、条件路由与并行拓扑；
- 全链路 State Schema；
- 评分、评级和预检配置草案；
- 后续三周目录和工作边界。
- 正式消息与历史 `comments` 输入适配；
- 14项确定性预检；
- 结构化红线 Agent、重试和人工复核降级；
- `pass/blocked/review` LangGraph 条件路由；
- 节点轨迹和技术错误记录。

## Project layout

```text
multi-agent-customer-service-qa/
├── configs/                 # 第一周确定的评分和预检配置草案
├── data/raw/                # 原始样例和专业规则，只读基线
├── docs/
│   ├── project-roadmap.md   # 四周整体工作内容
│   ├── week1/               # 第一周全部交付物
│   ├── week2/               # 后续：预检与红线开发
│   ├── week3/               # 后续：三维 Agent 开发
│   └── week4/               # 后续：汇总、MCP 与评测
├── reference/               # 原始 Prompt，仅作参考
├── src/                     # 第二周开始编写代码
└── tests/                   # 第二周开始增加测试
```

## Week 1 deliverables

1. [技术方案](docs/week1/technical-plan.md)
2. [客服质检规则映射表](docs/week1/rule-mapping.md)
3. [预检规则清单与触发条件](docs/week1/preflight-rules.md)
4. [LangGraph 工作流拓扑](docs/week1/workflow-design.md)
5. [State 数据结构规范](docs/week1/state-schema.md)
6. [第一周验收清单](docs/week1/acceptance-checklist.md)

## Data notes

- `sample-conversations.json` 包含100条样例。
- 原始样例的 `messages` 为空，实际对话保存在 `comments`。
- 样例没有消息角色和时间戳，只能用于流程开发，不能直接验证接入和回复时效。
- `professional-rules.json` 包含22个父业务分类的专业规则。

## Next step

第三周将从 `ready_for_dimension_audit` 分支接入服务流程、专业服务和沟通规范三个并行评分 Agent。当前代码已经完成输入、预检和红线门控，尚未计算三维得分。

## Week 2 demo

无需模型密钥即可查看确定性预检：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --sample-index 0 --preflight-only
```

在 `.env` 中填写 `LLM_API_KEY` 后可以运行完整红线门控：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --sample-index 0
```

完整实现与边界见 [Week 2 implementation](docs/week2/README.md)。

## Local development

项目使用 Python 3.11，通过 `pyproject.toml` 管理运行和开发依赖。

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

复制 `.env.example` 为 `.env` 后填写本地模型密钥。不要提交 `.env`。完整说明见 [Local setup](docs/local-setup.md)。
