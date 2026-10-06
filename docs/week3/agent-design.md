# 三个评分Agent与工具映射

三者共用 `LiveDimensionEvaluator` 调用类，但各有角色Prompt、子项规则、模型请求、图节点和State输出。共用解析与重试逻辑，避免三套校验产生分歧。

| Agent / 图节点 | 子项与原始满分 | 提供给模型的工具/事实 | 结果字段 |
| --- | --- | --- | --- |
| `service_process` | SP-01～05，每项5，总25 | 预检问候、结束语、标签提示；会话；SP详细规则 | `service_process_result` |
| `professional_service` | PS-01=30、PS-02=10、PS-03=10，总50 | `get_professional_rules(parent_tag)` 业务规则和免责；会话 | `professional_service_result` |
| `communication` | CM-01～05，每项5，总25 | 预检时间、重复回复、转接事实；原文；CM详细规则 | `communication_result` |

由程序确定何时预检和查询规则，再注入上下文；模型不自行选择或循环调用工具。规则查询目前是本地Python函数，第四周再暴露为MCP工具。

## 输入与输出

`build_dimension_context()` 生成 `DimensionContext`：维度名、标准会话、预检、当前细则、专业规则。

`LiveDimensionEvaluator.__call__()` 调用配置的Qwen模型，使用 `with_structured_output(DimensionAssessment, method="function_calling")` 返回结构化结果。这不等于实现了MCP。

输出逐项包含 `item_id/status/score/reason/rule_ids/evidence`。单次超时默认30秒、SDK重试关闭，外层最多2次；不是整图的严格总时限。

## 专业规则可追溯性

规则源 `data/raw/professional-rules.json` 原文不变，每类分为A问题分析、S服务意识、E免责。

ID为 `PS-<父标签SHA256前8位>-A01/S01/E01`。类别排序变化不影响ID；类别内部调整条款顺序可能改变序号，所以结果同时保留正文和源文件内容哈希版本，不能只凭编号复盘。

PS-01扣分从原文“扣N分”提取，原文件包含5、10、15、20分等情况。PS-02按业务条款扣分，另支持原Prompt中“反复要求用户重新描述”扣5分；PS-03默认10分。

未知父标签转复核，不猜分类。规则返回深拷贝，避免缓存被调用方修改。更改规则后需重启进程刷新缓存。

## 模型与程序的分工

模型判断需求、语义、条件和免责；程序检查分值、条款归属、原文引用和时间矛盾。引用存在不等于模型理解正确，后者需人工金标和真实联调。

仅“您好”不等于SP-01满分；没有正式标签目录时SP-04仅做语义一致性判断。当前角色仅有用户、人工客服、系统，生产混合机器人记录需额外角色适配。

维度内部不重复扣分原则写入Prompt；跨维度统一去重留给第四周，目前保留依据，不承诺已经消除跨维度重复扣分。
