# 第三周：三维度并行质检

已完成第三周工程实现和离线验证，并于2026-09-30使用qwen3.8-max完成一次真实API全流程联调。人工标注集评分效果和批量时延尚未验证，不能把单次连接成功或测试通过率当作模型准确率。配置与实测记录见 [模型连接](../model-connection.md)。

## 原始四项任务与交付物

| 原始任务 | 设计/说明文档 | 对应实现 |
| --- | --- | --- |
| 三个评分 Agent 与对应工具 | [Agent设计与工具映射](agent-design.md) | `agents/dimensions.py`、`agents/dimension_prompts.py`、`tools/professional_rules.py`、`configs/dimension-rubrics.yaml` |
| LangGraph并行执行 | [并行工作流方案](parallel-workflow.md) | `graph/builder.py`、`graph/dimension_nodes.py`、`schemas/state.py` |
| X/N分数解析、校验和异常兜底 | [解析与容错](score-validation.md) | `schemas/scoring.py`、`agents/dimensions.py` |
| 可解释评分与原文证据 | [结果示例说明](explainable-examples.md) | `reporting.py`、`examples/`、`scripts/generate_week3_examples.py` |

## 运行

在项目根目录运行，无需密钥：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --week 3
.\.venv\Scripts\python.exe -m customer_service_qa --demo --week 3 --format markdown --output outputs/week3-demo.md
.\.venv\Scripts\python.exe -m pytest --cov=customer_service_qa --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check src tests scripts
```

`--demo` 只使用固定合成会话和固定响应，不调用模型。不能同时指定自己的 `--input`，以免误当真实评分。

填写本地 `.env` 的 `LLM_API_KEY` 后，可执行真实三维流程：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week3/examples/input.json --week 3 --output outputs/live-week3.json
```

此命令会向配置的模型服务发送对话并产生API用量；`input.json` 是合成学习数据。第二周图仍可用 `--week 2` 运行。当前默认第四周；复现本周须显式加 `--week 3`。

无密钥时真实流程在红线节点降级为 `manual_review`。原始100条样本缺少时间戳，因此即使模型成功也不能把两个时效项视为满分。

## 本周验收

- 三维原始满分为25、50、25；模型逐项输出，分数由程序相加。
- 门控通过才并行调用；红线或主控异常不调用三个维度。
- 三分支独立写结果，共享轨迹和错误通过reducer拼接，汇合仅执行一次。
- 精确父标签检索全部22类规则；未知标签停止专业模型调用并转复核。
- 分数、条款、消息ID和原文引用均经校验；模型/校验失败最多尝试2次。
- 技术失败使用 `fallback_score=0`，业务 `raw_score=null`，保留成功的兄弟分支。
- 缺时效数据为 `partial`；只展示已评部分，不换算成完整维度满分。
- 实测结果见 [validation.md](validation.md)。

## 第四周边界

`collect_dimensions` 只收齐结果；`total_score=null`，`grade=待第四周汇总`。这些是第三周阶段边界；权重换算、最终评级、去重、MCP和真实评测已在 [第四周](../week4/README.md) 实现。
