# 第三周验证记录

验证日期：2026-09-27。Python 3.11.9，复用现有项目虚拟环境及锁定依赖，没有引入新的第三方依赖。

## 实际执行

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=customer_service_qa --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m customer_service_qa --demo --format markdown --output outputs/week3-demo.md
.\.venv\Scripts\python.exe scripts/generate_week3_examples.py
```

测试：78项通过；源码语句覆盖率93%。Ruff静态检查通过。演示和四类结果示例成功生成。

| 验证点 | 实际证据 |
| --- | --- |
| 兼容第二周 | 原有20项测试继续通过 |
| 确实并行 | 三路Barrier同时到达，汇合只执行一次 |
| 异常隔离 | 一路两次超时，另两路得分和全部轨迹保留 |
| 模型结构防御 | 缺项、重复项、虚构引用、未知条款、错误分母、越界等均拒绝 |
| 业务规则保真 | 全部22类原文条款解析、唯一ID与原文扣分一致 |
| 数据不足 | 缺时效转partial；未知父标签不调用专业模型 |
| 输入边界 | 重复ID、空内容、倒序/混合时区、未回复消息受控处理 |
| 模型适配 | 替身验证角色Prompt、规则注入、结构化输出及超时设置 |

未执行真实Qwen请求：本地缺少可用API Key。因此尚无真实模型的格式成功率、语义准确率、评分误差和时延数据。本周交付是可运行工程实现及离线验证，真实联调与业务效果评测需要随后完成。

## 2026-09-30后续联调

已补齐本地接口配置，并使用用户提供的qwen3.8-max服务完成一次完整真实调用：红线pass，三个维度completed，最终dimensions_completed。分数为25/25、50/50、25/25，total_score仍为null。

新增密钥别名、可配置思考开关和满分项证据/规则约束，现有测试86项通过，源码覆盖率94%。服务在思考模式拒绝强制工具选择，关闭思考后恢复结构化调用；输出缺失规则ID/证据的问题通过明确Prompt与Schema要求修复。

实际模型在SP-01给5/5，与固定演示0/5不同，需人工复核对“完整欢迎语”的解释。未修改业务校验或把真实输出替换为预设答案。此联调验证接口与流程，尚不能给出业务准确率或批量性能结论。详见 [模型连接与实测](../model-connection.md)。
