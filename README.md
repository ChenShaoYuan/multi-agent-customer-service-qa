# Multi-Agent Customer Service Quality Audit

基于 LangGraph 的多 Agent 客服质检项目。

## Current status

当前完成 **Week 1：业务规则梳理与工作流设计**，尚未进入业务代码开发。

已完成：

- 客服质检规则映射；
- 红线和确定性预检边界；
- LangGraph 节点、条件路由与并行拓扑；
- 全链路 State Schema；
- 评分、评级和预检配置草案；
- 后续三周目录和工作边界。

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

第二周从输入和 Schema 开始：创建 Python 项目配置，实现输入适配器、确定性预检、红线主控和条件路由。当前 `src/` 与 `tests/` 仅保留边界说明，不提前实现后续周内容。

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
