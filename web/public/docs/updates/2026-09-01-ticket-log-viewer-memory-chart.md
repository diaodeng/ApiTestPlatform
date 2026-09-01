# 更新记录：日志查看器支持内存分析图表

- 日期：2026-09-01
- 类型：功能新增
- 模块：工单管理 → 日志拉取记录 → 查看日志

## 变更内容

日志查看器弹窗新增"内存分析"能力：点击搜索栏的"内存分析"按钮，直接在查看日志界面展示日志中的进程资源监控曲线，无需再拉取日志后本地运行 `plot_memory.py` 之类的脚本生成图片。

- 新增内存（Mb / %）、CPU（%）、线程（活跃数 / 上限）三张 ECharts 曲线图，支持缩放、悬停取值。
- 面板顶部展示数据点数、时间范围、内存/CPU/线程极值汇总；数据点超过上限时自动等距降采样并标记"已降采样"。
- 无数据时给出明确提示（日志未准备、无监控行、文件超限等）。

## 技术说明

- 后端新增接口 `POST /ticket/logs/memory-metrics`（权限 `ticket:logpull:query`），入参为 Pydantic 模型 `TicketLogMemoryMetricsRequestModel`，返回 `TicketLogMemoryMetricsModel`。
- 新增纯解析工具 `server/modules/ticket/util/ticket_log_memory_metrics_util.py`，负责监控行正则提取、合并去重、等距降采样与汇总计算。
- 新增子服务 `server/modules/ticket/service/log_pull/ticket_log_memory_metrics_service.py`，负责解压目录定位、文件筛选（含数量保护）与业务编排，目录规则与日志查看器一致。
- 前端新增图表组件 `web/src/components/ticket/LogMemoryChartPanel.vue`，并在 `web/src/components/ticket/LogViewerDialog.vue` 工具栏与面板区域接入。
- 追加流式进度能力：新增 `GET /ticket/logs/memory-metrics/stream`（NDJSON 事件流 start/progress/result/error），解析工具改为生成器逐块产出数据点与进度信号，前端实时展示进度条、当前文件、已提取点数、已耗时与预计剩余时间（ETA 线性估算）；关闭面板或刷新会中止进行中的分析请求。原 POST 接口保留，复用同一套解析逻辑。

## 涉及文件

- `server/modules/ticket/controller/ticket_log_pull_controller.py`
- `server/modules/ticket/service/log_pull/ticket_log_memory_metrics_service.py`
- `server/modules/ticket/util/ticket_log_memory_metrics_util.py`
- `server/modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `web/src/api/ticket/ticket.js`
- `web/src/components/ticket/LogMemoryChartPanel.vue`
- `web/src/components/ticket/LogViewerDialog.vue`
- `web/public/docs/ticket_log_viewer.md`
- 缺陷修复（同日）：手写 fetch 拼接 baseURL 产生 `//ticket/...` 双斜杠，网关按路径转发返回 404；修复为先去掉 base 尾部斜杠再拼接（日志内容流式接口同类隐患一并修复），并增加流式 404 时自动降级为一次性 POST 接口的兜底逻辑。
