# 工单日志查看器文件范围搜索与选中文案高亮

## 背景

日志查看器原有关键字搜索只支持在当前工单日志目录内全局搜索。排查时常见流程是先全局找到关键字，再回到某个具体日志文件内继续缩小范围；同时，日志详细信息块里需要对选中的重复文案做临时高亮，便于翻看上一段、下一段时保持关注点。

## 本次调整

1. `POST /ticket/logs/search` 新增可选 `file` 字段，为空时保持全局搜索；传入相对日志文件路径时，只在该文件中搜索。
2. 前端日志查看器顶部新增“全局搜索/文件范围”下拉；搜索结果表新增“在此文件搜索”操作，可先全局命中，再一键收敛到目标文件。
3. 换行开关移动到“日志详细信息”标题区，因为它只控制下方详细日志块的换行显示，不再放在全局搜索控制栏。
4. 在日志详细信息块中选中文本后，会把相同文案高亮显示；翻到上一段、下一段后，高亮关键字保持不变，直到点击“清除高亮”或关闭查看器。
5. 修复打开某条日志拉取记录后搜索结果为空的问题：查看器现在先清理旧搜索状态，再写入当前 `recordId`，避免准备目录是 `record_{recordId}` 但搜索请求回落到工单级目录。

## 性能说明

高亮只处理当前上下文块的行数据，默认上下文 20 行，最大也受页面输入的上下文行数限制；不会对整份日志做 DOM 高亮。指定文件搜索在后端复用现有日志目录和相对路径校验，`rg` 与 Python 降级搜索都支持同一参数。

## 排查结论

归档地址记录的是历史机器上的本地路径时，只要重新下载/解压已经落在当前机器目录，查看器仍应按当前日志拉取记录的 `recordId` 搜索 `data/logs/ticket_{ticketId}/record_{recordId}/extract`。若前端搜索请求缺少 `recordId`，后端会查 `data/logs/ticket_{ticketId}/extract`，表现为接口 200 但结果为空。

## 相关文件

- `server/modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `server/modules/ticket/controller/ticket_log_pull_controller.py`
- `server/modules/ticket/service/log_pull/ticket_log_service.py`
- `server/tests/test_ticket_log_service.py`
- `web/src/views/ticket/hooks/useLogViewer.js`
- `web/src/views/ticket/index.vue`
