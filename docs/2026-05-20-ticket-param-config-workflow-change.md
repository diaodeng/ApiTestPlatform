# 2026-05-20 工单参数配置与流转处理人改造记录

## 变更目标
- 将工单日志拉取相关地址、Cookie、归档配置收口到参数配置管理。
- 将工单归属维度从“商户/模块”切换为测试管理中的“项目/模块”。
- 让工单不同状态流转后可以自动落到不同处理人，并预留通知入口。

## 变更内容
- 工单新增/编辑、列表查询、导入模板与导入解析统一改为项目/模块语义：
  - 前端工单页面改用测试管理项目、模块下拉选项。
  - 后端新增工单项目/模块选项接口，并校验模块必须属于所选项目。
  - 工单侧项目/模块选项复用 HRM 公共项目管理，按正常状态值 `2` 过滤有效数据。
  - 历史 `merchant_name` 字段继续保留，用于兼容旧数据和前端旧字段 `merchantName`。
- 日志拉取配置迁移到参数配置管理：
  - `ticket.logPull.external` 保存外部提交地址、分页地址、Cookie 和请求头。
  - `ticket.logPull.storage` 保存本地/FTP 归档与轮询参数。
  - 工单详情页不再内联编辑配置，只保留参数配置入口。
- 工作流流转规则扩展默认处理人与通知预留：
  - 每条流转规则可配置默认处理人。
  - 状态流转成功后自动回填工单当前处理人，并写入指派历史/事件。
  - 若开启通知预留，则写入 `NOTIFY_PENDING` 事件，后续可在此接入具体通知渠道。

## 验证记录
- `cd server && uv run python -m compileall modules/ticket module_admin module_hrm server.py`：通过
- `cd server && uv run ruff check modules/ticket/controller/ticket_controller.py modules/ticket/dao/ticket_dao.py modules/ticket/dao/ticket_log_pull_dao.py modules/ticket/entity/vo/ticket_vo.py modules/ticket/enums/ticket_enums.py modules/ticket/service/ticket_import_service.py modules/ticket/service/ticket_log_pull_service.py modules/ticket/service/ticket_service.py server.py`：通过
- `cd web && npm run build:prod`：通过

## 风险与后续
- 当前日志拉取归档实现仍是本地/FTP，不包含独立 SFTP 协议支持；若后续要对齐 SFTP，可复用 `module_hrm/utils/desktop_asset_storage.py` 的实现模式。
- 老工单的 `merchant_name` 仍作为兼容展示字段存在，后续若要彻底去商户语义，需要补数据库迁移方案。
- 通知目前只保留事件入口和规则字段，尚未接入站内信、企微、邮件等真实通知通道。
