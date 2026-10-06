# 项目验收与复现

## 五项第四周任务的验收证据

| 验收点 | 证据 |
| --- | --- |
| 权重20/40/40与0～100总分 | calculate_total、权重单测、完整演示96分 |
| ReAct聚合而非模型自由写分 | 实际inspect_audit→finalize_audit记录、工具顺序/自由文本拒绝测试 |
| 60/90阈值与反馈 | 边界测试、summary.yaml模板、结果feedback |
| 去重可解释 | 单元测试相同证据合并、不同问题/复合条款拒绝、duplicate_resolutions |
| 异常边界完整 | 缺预检/维度、超时、空响应、资料不足、MCP故障、汇总失败用例 |
| 统一最终输出 | 每条结果通过FinalAudit，包括blocked/manual_review |
| MCP通过HTTP工作 | 实际客户端握手与工具测试、真实运行transport=mcp |
| 历史数据效果 | 100条真实模型跑批结果，详见效果报告 |
| 参考集效果与局限 | 12条规则参考答案一致率，明确尚未人工复核 |

## 安装与命令

Python 3.11，现有环境可直接运行；新环境先 `python -m pip install -e ".[dev]"`。requirements.lock记录本次Windows环境依赖，跨平台优先从pyproject安装。

```powershell
# 工程测试（含真实本机MCP HTTP集成测试，不请求模型）
.\.venv\Scripts\python.exe -m pytest --cov=customer_service_qa --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts

# 完整离线演示
.\.venv\Scripts\python.exe -m customer_service_qa --demo --format markdown --output outputs/week4-demo.md

# 原有第二周和第三周仍可单独运行
.\.venv\Scripts\python.exe -m customer_service_qa --sample-index 0 --preflight-only
.\.venv\Scripts\python.exe -m customer_service_qa --demo --week 3

# 真实历史跑批；先启动MCP服务，本地.env填模型参数
.\.venv\Scripts\python.exe -m customer_service_qa.evaluation --rules-transport mcp --workers 2 --output outputs/week4-history

# 同一代码/配置/输入下从已有结果续跑
.\.venv\Scripts\python.exe -m customer_service_qa.evaluation --rules-transport mcp --workers 2 --output outputs/week4-history --resume

# 规则参考集
.\.venv\Scripts\python.exe -m customer_service_qa.evaluation --dataset data/evaluation/reference-cases.json --rules-transport mcp --workers 2 --output outputs/week4-reference
```

断点续跑会核验每条输入哈希与代码/配置指纹，不混用不同版本。历史结果有原文，默认留在被忽略的outputs内；仓库交付聚合指标和合成示例。外部个人学习指南继续位于项目上一级，不上传Git。

## 交付边界

实现与实测覆盖项目四周要求。真实大模型仍可能误解标准或拒绝规范输出；本次没有导师审核过的金标，业务准确率不能宣称达标。参考集和失败案例用于导师复核、继续标注和调优，不把格式稳定性充作业务准确率。
