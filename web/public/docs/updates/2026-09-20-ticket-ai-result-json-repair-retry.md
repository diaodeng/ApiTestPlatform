# AI 分析结果解析失败修复（json-repair 兜底 + Agent 补救重试）

- 背景：工单 INC00002000624N（生产）AI 分析连续三次失败，错误码 `AI_WORKER_RESULT_INVALID`。排查确认根因：模型 deepseek-v4-flash-0731（openai_com 公网 Provider）无视提示词转义约束与 `--output-schema`，在分析结果字符串值内原样嵌入请求体 JSON 示例（如 `请求体为 {"yuuId": "934...", "venderId": "8", "storeId": "1647"}`），未转义的双引号使整体 JSON 非法；旧版 `_repair_unescaped_quotes` 单遍贪心扫描按"引号后紧跟 `, } ] :` 即为字符串结束符"判定，遇到内层 `"键":` 形态与真实结构无法区分，状态机错乱后修复放弃。
- 修复内容（按结果处理流程）：Codex Worker 退出码 0 → 读取 result.json → `json.loads` → 失败 → **回溯式 json-repair** → 仍失败 → **Agent 端自动补救重试（resume 会话纠错一轮）** → 仍失败才按 `AI_WORKER_RESULT_INVALID` 落库。
  - **新增 `client_new/utils/json_repair.py`**（纯标准库无依赖）：利用 JSON 语法把决策点压缩到极少数——键字符串内 `引号+冒号` 必为键结束；值字符串内 `引号+冒号` 必为值内字符（合法 JSON 值后不可能是冒号）；仅"值字符串内引号后跟 `, } ]`"是二义点，按"当前值字符串内未配对 `{` 数量"剪枝（处于嵌入 JSON 内优先按值内字符转义，否则优先按结束符），二叉回溯，分支间拷贝上下文避免污染；任一路径整体通过 `json.loads` 且为 dict 才算成功。用两个真实失败样本（task_2051964844727296 / task_2051995208293376，8KB 与 10KB，36 处转义引号）实测修复成功且语义正确，历史引号修复用例全部兼容。
  - **客户端解析链接入**：`_extract_json_from_text` 在围栏提取、启发式引号修复之后，最终兜底调用 `repair_json_text`，挽救旧算法无法处理的"字符串值内嵌 JSON 示例"形态。
  - **Agent 端补救重试 `_retry_worker_after_unparseable_result`**：Worker 正常退出但解析失败时触发（非取消、非异常退出；仅一轮不递归）：①转存首次现场为 `result.attempt1.json` / `worker.attempt1.stdout.txt` / `worker.attempt1.stderr.txt`，避免重试覆盖后丢失排查依据；②resume 同一会话（codex 复制 `.ai_home`，claude 复制 `.claude`），以纠错指令（重新输出合法 JSON、字符串内双引号转义）为 prompt 再执行一轮；③重试结果重新解析，成功则合并 token 后返回成功响应（响应携带 `repaired_retry: true`，消息注明"经自动补救重试成功"），仍失败返回 None 由调用方按原失败分支处理。重试结果同样先经过 json-repair，两道防线叠加。
  - **服务端顺手改进（无数据库结构变更，仅写任务表现有字段）**：`AI_WORKER_RESULT_INVALID` 时把客户端诊断明细（`AI_WORKER_RESULT_UNPARSEABLE` 的输出预览/违规摘要）汇总并入任务 `error_message`，此前诊断只进审计记录与事件流，任务列表页只能看到通用文案；新增 `_summarize_failure_diagnostics` 提取摘要（每条截断 160 字符、最多 3 条）。
- 已知边界：json-repair 只处理"结构可挽救"的非法 JSON（未转义引号、围栏包裹、收尾残缺），不处理逻辑性损坏（如 JSON 中途截断丢失大段内容）；补救重试额外消耗一轮模型调用（token 合并计入审计），仅解析层失败触发，Schema 违规与 Worker 异常退出不触发。
- 验证：client_new 全部 70 个测试通过（含新增 4 个补救重试用例与 5 个引号修复用例）；server ruff 通过；server 工单同步回归 15 个用例通过；两个真实失败样本经正式解析入口修复成功且业务字段语义正确。
- 用户说明同步：[工单深度AI分析说明](../ticket_ai_analysis.md)。
