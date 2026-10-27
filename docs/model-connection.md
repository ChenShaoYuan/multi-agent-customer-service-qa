# 配置模型连接并运行项目

项目通过 OpenAI 兼容接口调用模型。实际服务地址、模型标识和密钥只填写在本地 `.env` 或环境变量中；仓库中的 `.env.example` 是不含密钥的通用模板，不记录个人服务配置。

## 1. 本地配置

首次配置时，在项目根目录执行：

```powershell
Copy-Item .env.example .env
```

已有 `.env` 时保留原文件，直接编辑。根据服务提供方说明填写：

| 配置项 | 用途 |
| --- | --- |
| `LLM_MODEL` | 服务实际支持的模型名称 |
| `LLM_BASE_URL` | 服务提供方给出的兼容接口根地址 |
| `LLM_API_KEY` | 该服务的有效密钥，仅保存在本地 |
| `LLM_TIMEOUT_SECONDS` | 单次模型请求超时，默认30秒，范围大于0且不超过120秒 |
| `LLM_ENABLE_THINKING` | 可选的供应商扩展参数；未配置时不发送 |
| `PROMPT_VERSION` | 当前完整流程为 `0.3.0` |

也可以使用 `DASHSCOPE_API_KEY` 作为密钥变量名；此时删除空的 `LLM_API_KEY` 行，避免优先级冲突。两个变量同时存在时优先使用 `LLM_API_KEY`。同名环境变量通常覆盖 `.env` 中的值。

`LLM_BASE_URL` 应为纯地址字符串，不要粘贴 Markdown 链接。模板中的公开服务默认值只用于说明配置方式，不表示任意账号都可以直接使用。请勿把本地 `.env`、请求头、密钥或个人服务连接记录提交到仓库。

## 2. 验证基础连接

```powershell
.\.venv\Scripts\python.exe scripts/check_llm.py
```

脚本发送固定测试消息，不发送客户会话。退出码0表示取得文本回复，2表示未配置密钥，1表示接口失败或没有文本输出。错误输出只包含异常类型和HTTP状态，不打印密钥或供应商原始异常体。

基础文本请求通过后，还需要验证结构化工具调用。红线和评分节点使用 function calling，汇总节点要求工具调用；服务必须支持相应的 `tools/tool_choice` 行为。某些模型的思考模式与强制工具选择存在兼容限制，必要时根据供应商文档设置 `LLM_ENABLE_THINKING=false`；不要把这一参数当作所有服务通用的开关。

## 3. 运行默认的第四周完整流程

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week4/examples/input.json --output outputs/week4-live.json
```

该输入是合成示例。真实模型运行会产生服务用量；红线放行后执行三维评分，结果完整时再执行汇总工具循环，由Python完成去重校验、加权和评级。输入不足或调用失败时保留复核结果，不发布业务总分。

同一次结果需要转换成Markdown时使用 `reporting.render_markdown()`，避免为了更换展示格式再次请求模型。分别执行JSON和Markdown命令会各运行一次流程。

`--week 2` 和 `--week 3` 保留阶段入口，其中第三周只输出三维原始结果，不计算第四周总分。默认第四周行为与各阶段输出状态不能混用。

## 4. 不连接模型也能学习和验证

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --rules-transport local --format markdown --output outputs/week4-demo.md
.\.venv\Scripts\python.exe -m customer_service_qa --sample-index 0 --preflight-only
```

demo使用固定替身，仅验证工程流程，不代表真实模型效果。预检只做适配和确定性计算。

## 5. 验证范围与运行记录

项目的合成示例、聚合评测和验收说明保留在 `docs/week4/`，详见 [完整交付说明](week4/README.md) 与 [评测报告](week4/evaluation-report.md)。个人连接参数、逐条本地实跑产物和事件日志不纳入版本控制。

没有独立人工金标时，不把接口成功、格式通过或合成参考一致率当作真实业务准确率。欢迎语等细则的解释差异需要按业务口径复核。
