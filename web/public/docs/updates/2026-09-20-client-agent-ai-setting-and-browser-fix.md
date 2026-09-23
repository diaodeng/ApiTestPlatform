# 桌面客户端 Agent 页补齐 AI 设置与浏览器设置遗漏项

- 背景：PySide6 → pywebview 迁移（`baf2c365`）时，旧版 Agent 页面顶部的「AI 配置区」两个输入框没有迁移到新前端，浏览器设置弹窗也有小幅缩水。经静态比对旧版 `ui/pages/agent_page.py`、`ui/dialogs/agent_browser_setting_dialog.py` 与新版 `ui_web/static/js/pages/agent.js` 确认遗漏清单（`ticket_ai_local_repo_path` 旧版 UI 同样只保存不消费，属于存量摆设字段，一并补齐展示）。
- 新增「AI 设置」弹窗（`agent.js`）：
  - **AI 工作区根目录**（`ticket_ai_workspace_root`）：工单 AI 分析克隆仓库、派生 worktree 的存放根目录，留空使用客户端默认目录 `storage/ticket_ai_analysis`；后端消费点 `ticket_ai_analysis_service._resolve_ai_repo_runtime_settings`。
  - **AI 本地仓库路径**（`ticket_ai_local_repo_path`）：优先使用的本地已有仓库，留空回退到工单映射配置；当前 client_new 后端暂无直接消费点（服务层从任务 mapping 的 `localRepoPath` 读取），仅恢复配置入口避免断档。
  - **Codex CLI 路径**（`ticket_ai_codex_cli_path`）：AI 分析执行 Codex 命令行的可执行文件，用于避免误用 Codex 桌面应用；旧版 UI 从未暴露但服务层有消费（`_resolve_worker_command_parts`），本次顺带补上入口。支持 .exe/.cmd/.bat 过滤。
  - 三项均支持直接输入或「浏览」按钮（复用 `choose_dir`/`choose_file` 桥接）；保存走既有 `agent.save_config` 全量校验链路，已保存过的历史值不受本次改动影响。
- 浏览器设置弹窗补齐：
  - 手动下载从 3 种内核恢复为 5 种：chromium/firefox/webkit/**chrome/msedge**（后端 `playwright_browser_runtime` 本就支持全部五种，迁移时前端缩水）。
  - chromium/firefox/webkit 三个手动路径补「浏览」按钮（`choose_file`，可执行文件过滤），此前只能手输；安装目录「浏览」逻辑合并为统一的 `pathRow` 工厂（目录/文件两种类型），选择结果通过 `dispatchEvent(new Event("change"))` 同步回 `config.browser`，保证手动下载前 `collectData()` 拿到最新值。
- 文档：`web/public/docs/client/agent.md` 同步更新（布局描述、地址下拉框语义、浏览器设置/手动下载、新增 AI 设置说明表）；`agent.md` 此前"地址可直接输入"的描述与新版纯 select 行为不符，一并修正。
- 无后端改动、无配置结构变更、无数据库变更。
