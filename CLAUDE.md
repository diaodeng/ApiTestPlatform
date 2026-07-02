# CLAUDE.md - api-test-platform

## 项目结构
- `server/`: FastAPI 后端、调度与 Agent 相关服务
- `web/`: Vue3 + Vite 前端
- `client/`: Flet 客户端（旧版）
- `client_new/`: PySide6 客户端（新版）
- `wiki/`: LLM Wiki 知识库
- `web/public/docs/`: 变更说明文档

## 工作原则
- 默认使用中文，先结论后细节。
- **做任何事情前优先从知识库获取信息**：修改代码前先查阅 `wiki/` 目录，通过 `wiki/index.md` 定位相关实体/流程文档，了解现有架构和约束后再动手。
- 仅做与当前需求相关的最小改动，不做顺手重构。
- 优先修复根因，避免用大范围兜底逻辑掩盖问题。
- **每次代码变更后自动更新 wiki**：改动完成后执行 llm-wiki skill 的 INGEST-CODE 流程，更新受影响的实体页面并在 `wiki/log.md` 追加操作记录。
- **每次变更后记录到 `web/public/docs/`**：创建或更新对应的说明文档，供后续复盘。
- 方法注释用中文，实现过程注释清楚。
- 日志格式化统一使用 f-string 方式（loguru 不支持 %s）。
- FastAPI 接口不要在异步接口中直接使用同步方法导致阻塞，使用 `run_in_threadpool`。
- 未经明确授权，不执行高风险操作（如批量删除、强制重置）。

## 目录边界
- 后端接口、任务调度、服务逻辑 → `server/`
- 前端页面与组件 → `web/src/`
- `web/dist/` 视为构建产物，不直接手工修改

## 常用命令
- 前端开发：`cd web && npm run dev`
- 前端构建：`cd web && npm run build:prod`
- 后端开发：`cd server && uv sync && uv run python app.py --env=dev`
- 后端检查：`cd server && uv run ruff check .`

## 验证要求
- 修改后至少执行与改动直接相关的检查。
- 若无法在本地完成验证，必须说明：已执行的验证、未执行项及原因、剩余风险。
