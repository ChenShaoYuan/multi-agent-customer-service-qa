 # 使用提供的Qwen兼容接口运行本地项目

配置目标为用户提供的 `https://maas.qianwenaiapi.com/compatible-mode/v1` 和 `qwen3.8-max`。这是本次指定的服务地址，不将其视为项目原默认阿里云地址；模型是否可用、是否支持结构化工具调用，以实际联调为准。

## 1. 填写项目根目录的.env

```dotenv
LLM_PROVIDER=openai_compatible
LLM_MODEL=qwen3.8-max
LLM_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
DASHSCOPE_API_KEY=在本地填写该接口服务的有效密钥
LLM_TIMEOUT_SECONDS=60
LLM_ENABLE_THINKING=false
```

不要把示例占位文字当成密钥。密钥留在本地，.env已被Git忽略。程序也兼容原有 `LLM_API_KEY`，两者同时存在时优先使用LLM_API_KEY；使用DASHSCOPE_API_KEY时请删除空的LLM_API_KEY行。操作系统环境变量通常优先于.env，遇到配置不生效应检查同名环境变量。

示例代码中的 `api\_key` 应写成 `api_key`；base_url需要纯网址字符串，不应包含Markdown的 `[网址](网址)`。`os.getenv()`只读进程环境，不自动读.env，本项目通过Settings加载.env。

## 2. 先检查普通对话接口

```powershell
Set-Location -LiteralPath 'D:\PTA\PTA1\multi-agent-customer-service-qa'
.\.venv\Scripts\python.exe scripts/check_llm.py
```

脚本用OpenAI SDK向配置的模型发送一句固定测试消息，不发送客户记录。退出码0=取得文本回复，2=未配置密钥，1=接口失败/没有文本。错误只打印异常类型和HTTP状态，不打印密钥或原始响应错误体。

## 3. 再运行真实三周工作流

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week3/examples/input.json --week 3 --output outputs/week3-live.json
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week3/examples/input.json --week 3 --format markdown --output outputs/week3-live.md
```

两条命令会分别执行一次完整审核、分别产生模型用量，并非第二条仅转换第一条结果。优先运行JSON命令检查status。input.json是合成会话，适合先联调。真实资料用自己的JSON替换路径。

完整工作流需要服务支持 `tools/tool_choice` 形式的结构化输出。普通Chat Completions成功不代表四个Agent一定成功。红线放行后才并发请求三个维度；正常状态应为dimensions_completed，partial、校验失败或模型错误可能转manual_review，应检查dimensions/errors和trace。

本次联调遇到HTTP 400：思考模式不允许强制指定tool_choice。为此增加 `LLM_ENABLE_THINKING=false`，经 `extra_body={"enable_thinking": false}` 传给红线和三维客户端。此开关默认不发送，避免影响其他兼容服务。思考模式与强制工具选择的限制参见 [Qwen工具调用文档](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-function-calling)；具体提供的服务仍以本次实测为准。

显式 `--week 3` 保留第三周原始分，总分仍为null。当前默认第四周可计算完整总分；资料不足或技术失败仍无总分，不能当成真实客服零分。

## 4. 不用密钥也能运行已有离线能力

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --week 3 --format markdown --output outputs/week3-demo.md
.\.venv\Scripts\python.exe -m customer_service_qa --sample-index 0 --preflight-only
```

--demo使用固定模型答案，不能用它证明远端模型连接成功。

## 5. 2026-09-30本地实测记录

- 普通Chat Completions请求成功。
- 完整三周真实流程成功：红线pass，三个维度completed，最终dimensions_completed。
- 本次合成输入得分：服务流程25/25、专业服务50/50、沟通规范25/25；第四周总分仍为null。
- 原始结果保存在本地 `outputs/week3-live.json`，同一结果的可读版为 `outputs/week3-live.md`；两者均被Git忽略。
- 配置别名、思考开关及真实输出边界回归后，86项测试通过，源码覆盖率94%。

SP-01模型认为简短问候配合解决方案可得5/5，固定演示预设为0/5。该差异需要人工确认业务标准，单次联调不是准确率评测。

本次还明确了满分项必须引用规则（例如PS-03默认满分仍引用PS-03），以及无转接的CM-05要引用被审核的上下文消息，避免空数组被评分校验拒绝。Prompt版本更新为0.2.0。

## 6. 第四周完整版本

当前 Prompt 版本为 `0.3.0`。在原配置中增加 `PROMPT_VERSION=0.3.0`；沿用同一个密钥、模型与思考开关，汇总Agent也使用结构化工具调用。

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week4/examples/input.json --week 4 --output outputs/week4-live.json
```

三维通过后执行 `inspect_audit → finalize_audit` 工具循环，Python完成去重校验、加权与评级。完整示例正常需要红线一次、三个维度各一次、汇总两轮模型请求，重试会增加用量。缺时间戳等不满足汇总条件的输入直接复核，不启动汇总模型。

HTTP MCP的两终端运行方式、100条历史数据及12条规则参考用例的实测结果见 [第四周交付](week4/README.md)。旧的第三周实测记录保留用于说明阶段变化，不代表最终版本的评测。
