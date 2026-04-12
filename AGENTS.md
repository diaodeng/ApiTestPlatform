# AGENTS.md - api-test-platform 项目提示词

## 项目结构
- `server/`: FastAPI 后端、调度与 Agent 相关服务。
- `web/`: Vue3 + Vite 前端。
- `client/`: Flet 客户端（旧版）。
- `client_new/`: PySide6 客户端（新版）。

## 工作原则
- 默认使用中文，先结论后细节。
- 仅做与当前需求相关的最小改动，不做顺手重构。
- 优先修复根因，避免用大范围兜底逻辑掩盖问题。
- 未经明确授权，不执行高风险操作（如批量删除、强制重置）。

## 目录边界
- 后端接口、任务调度、服务逻辑优先改 `server/`。
- 前端页面与组件优先改 `web/src/`。
- Flet 客户端逻辑优先改 `client/src/`。
- PySide 客户端逻辑优先改 `client_new/`。
- `web/dist/` 视为构建产物，除非明确要求发布构建，不直接手工修改。

## 常用命令
- 前端开发：
- `cd web`
- `npm run dev`
- `npm run build:prod`
- 后端开发：
- `cd server`
- `uv sync`
- `uv run python app.py --env=dev`
- `uv run ruff check .`
- 旧客户端：
- `cd client`
- `uv run flet run`
- 新客户端：
- `cd client_new`
- `uv sync`
- `uv run python main.py`

## 验证要求
- 修改后至少执行与改动直接相关的检查或运行步骤。
- 若无法在本地完成验证，必须说明：
- 已执行的验证；
- 未执行项及原因；
- 剩余风险。

## 交付格式
- 最终输出按以下顺序：
- 结论；
- 变更文件；
- 变更原因；
- 验证结果；
- 剩余风险或下一步建议。
