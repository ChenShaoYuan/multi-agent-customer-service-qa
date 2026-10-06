# 第四周真实评测与最终验证

报告日期：2026-10-05。所有数字由本地已保存的真实记录汇总；原始客户逐条结果留在被Git忽略的 `outputs/week4/`，仓库提供聚合指标和合成示例。

## 评测设置与复现范围

- 模型：`qwen3.8-max`，本地已配置的OpenAI兼容服务，temperature=0、请求超时60秒、关闭thinking以兼容强制工具调用。
- Prompt版本0.3.0，第四周完整LangGraph图，规则通过真实HTTP MCP获取，SDK版本1.30.0。
- 数据：原始100条历史comments；另有12条按规则编写的合成参考用例，未做独立人工金标审核。
- 批次并发workers=2。历史批次恢复了21条已有记录，本次执行79条；参考集复用了已实跑的12条。源代码/配置/输入指纹一致。
- 本报告合并已有实跑与本次续跑记录。单条耗时包含请求、工具和重试；不是同一连续时段压测，不把续跑墙钟时间当作完整112条总耗时。未采集完整token费用，不报告虚构成本。
- 指纹：`9e8a905696ee71de39cd8257ff06cf561cd8dae333ede4f183219680d69b5f7b`。`generated_at`是聚合时间，不是每条首次请求时间；原始trace保留各节点时间。

## 运行稳定性与状态

| 指标 | 100条历史数据 | 12条规则参考用例 |
| --- | --- | --- |
| 记录数 | 100 | 12 |
| 最终契约合法数 | 100 | 12 |
| 最终契约通过率 | 100% | 100% |
| 最终状态分布 | manual_review=100 | completed=6、blocked=3、manual_review=3 |
| 有技术错误记录的工单数 | 23 | 0 |
| 平均耗时（秒/工单） | 17.781 | 10.307 |
| p50（秒/工单） | 16.073 | 12.887 |
| p95（秒/工单） | 26.427 | 16.091 |

格式通过率包含明确的人工复核或红线拦截结果，**不是模型评分成功率，也不是业务准确率**。历史样本没有可靠时间戳，无法验证首响90秒和后续回复300秒，不能产生可比较的完整总分；还需核验从comments推断的角色。

历史维度分布：

| 维度与状态 | 数量 |
| --- | --- |
| communication:partial | 100 |
| professional_service:completed | 91 |
| professional_service:technical_error | 9 |
| service_process:completed | 94 |
| service_process:technical_error | 6 |

## 参考用例对照

- 门控一致率：100%；等级一致率：100%。
- 红线参考precision=100%、recall=100%；仅基于本次小规模合成集。
- 双方都有总分的配对数：6；平均绝对分差MAE=0.0。
- 参考集覆盖：完整服务、问候扣分、辱骂/隐私泄露/未经授权承诺、用户辱骂免责、两类时效、缺时间、未知类别、空输入、用户指令注入。

标签状态是 `rule_authored_not_human_reviewed`。参考集由项目实现者依据规则编写，存在口径与实现同源的偏差；12条一次运行一致，不能外推真实业务准确率、置信区间或跨次稳定性。两组 `business_accuracy` 均为null。

另一个真实合成烟测成功输出：总分100.0、等级优秀，ReAct依次调用inspect_audit、finalize_audit。固定离线demo为96分，差异是模型对简短欢迎语的解释；这种业务口径应由导师确认，不能篡改真实结果来匹配演示。

## 异常与失败分析

历史技术错误按节点和异常类型统计（同一工单多次尝试会累计）：

| 节点 | 异常类型 | 次数 |
| --- | --- | --- |
| professional_service | ValueError | 21 |
| service_process | ValueError | 19 |

含技术错误的历史记录索引（从0开始）：`[1, 11, 25, 26, 27, 28, 32, 34, 50, 51, 56, 63, 65, 66, 69, 74, 78, 82, 83, 84, 85, 94, 99]`。可在本地 `outputs/week4/history/records/索引补足四位.json` 定位，不把客户原文提交仓库。技术错误可能是结构/证据校验拒绝，不能仅按异常类型推断供应商停机或客服违规。

历史复核原因分布（同一工单可有多个原因）：

| 原因 | 记录数 |
| --- | --- |
| communication: CM-03: 缺少有效时间戳或人工接入事件，无法评估。 | 100 |
| communication: CM-04: 缺少有效时间戳或人工接入事件，无法评估。 | 100 |
| professional_service: 重试耗尽，请人工复核。 | 9 |
| service_process: 重试耗尽，请人工复核。 | 6 |

MCP规则调用轨迹统计：`{'mcp': 100}`。未知类别属于资料限制，网络不可用属于技术失败；均不以本地查表静默覆盖。本次历史数据若未进入可汇总状态，就不会请求ReAct；ReAct真实调用由带完整信息的参考用例与烟测覆盖。

## 工程测试与输出示例

- `pytest --cov=customer_service_qa`：122项通过，源码语句覆盖率87.93%（终端四舍五入88%）。
- `ruff check .` 与 `ruff format --check src tests scripts`：通过。
- MCP集成测试启动独立本机HTTP服务，验证协议初始化、规则原文、22类别、未知类别和完整图接入。服务子进程未计入主进程覆盖率，不能将其0%解读为没做MCP测试。
- 权重、评级60/90阈值、危险去重拒绝、红线短路、缺预检、缺时效、专业失败隔离、ReAct工具顺序/耗尽、断点恢复均有测试。
- [完整96分](examples/completed.md)、[缺时间复核](examples/partial.md)、[技术故障隔离](examples/technical-error.md)、[红线拦截](examples/blocked.md) 是可重生成的离线合成示例。

## 可审阅证据与下一步

[历史聚合指标](results/history-metrics.json)、[参考集指标与逐例对照](results/reference-metrics.json)、[验证摘要](results/validation-summary.json)、[真实合成烟测](results/live-smoke.json)。重跑命令见 [验收说明](acceptance.md)，参考输入见 `data/evaluation/reference-cases.json`。

四周要求的工程能力、HTTP服务化及历史数据端到端测试已经交付。业务效果还需导师独立标注真实会话、补齐可信角色与接入/回复时间，并确认欢迎语和去重口径；之后用独立留出集计算红线precision/recall、子项准确率、总分MAE和稳定性。当前完成的是可运行、可解释、可验证的本地项目，不能据此宣称已通过生产准确率验收。
