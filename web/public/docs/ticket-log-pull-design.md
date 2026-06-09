# 工单日志拉取设计

## 目标
- 在工单详情页直接提交日志/DB 拉取申请，替代人工访问外部平台手动拉取。
- 全流程记录状态、异常信息、原始压缩包地址、归档地址和解析后的日志文本。
- 支持本地目录或 FTP 目录归档，并可在页面查看解析后的日志内容。
- 外部地址、Cookie、归档与轮询参数统一收口到系统参数配置管理，不再在工单详情页内联维护。

## 落点
- 后端模块：`server/modules/ticket`
- 前端页面：`web/src/views/ticket/index.vue`
- 全局启动恢复：`server/server.py`

## 数据结构
- `ticket_log_pull_record`
  - 记录工单ID、vendor/store/pos、commandContent、日志时间范围。
  - 记录外部命令ID、外部状态、压缩包地址、归档地址。
  - 记录内部状态、错误信息、异常堆栈、日志摘要、压缩入库文本。
- `ticket_log_pull_store_config`
  - 独立保存门店配置大表，覆盖 `group_no`、`vender_no`、`region_no`、`org_no`、`org_name`、`sap_org_no`、`platform_no`、`parent_org_no`、`perm_node_id`、`org_type`、`company_no`、`city_no`、`biz_type_no`、`status`、`created`、`modifid`、`open_date`、`language_desc` 等字段。
  - 仅将门店配置从 `ticket.logPull.external` 中拆分出来，不再把一万多条基础数据塞进参数配置。
- `ticket_log_pull_project_vendor_map`
  - 保存当前系统项目 ID 与商户编号 `vender_no` 的映射，供日志拉取弹窗自动回填商家编号。

## 状态流转
- `created`：任务已创建，等待后台执行。
- `submitting`：正在调用外部提交接口。
- `polling`：外部申请成功，正在轮询列表接口。
- `downloading`：外部已生成压缩包，正在下载归档。
- `processing`：正在解析 ZIP 内日志并压缩入库。
- `success`：流程成功结束。
- `failed`：外部平台返回失败或轮询超时。
- `exception`：程序自身执行异常。

## 后台处理流程
1. 页面提交 `vendorId/storeId/posNo/commandDataType/modifyTime/path` 等参数。
2. 后端写入 `ticket_log_pull_record`，并启动线程池后台任务。
3. 后端先调用外部 `page` 接口查询服务端已有列表，按 vendor/store/pos/dataType/commandContent 匹配本次申请，匹配时只比较 `modifyTime/path`，且双方这两个参数的可用个数必须一致；同时忽略内部自动化字段 `_automation`，避免自动 AI 配置干扰命中。
4. 如果列表里已经能匹配到且压缩包可下载，直接进入下载、归档和解析流程。
5. 如果列表里还没有可下载结果，再调用外部 `insert` 接口提交拉取申请。
6. 提交成功后继续轮询外部 `page` 接口，直到命中可下载结果或超时。
7. 外部状态成功后下载 ZIP，归档到本地或 FTP。
8. 若配置了时间范围，则仅遍历 ZIP 中命名符合 `*_pos.log*` 的文件，按时间戳规则提取指定时间段日志并压缩入库。
9. 若未配置时间范围，则只下载和归档整包压缩文件，不写入日志正文，供后续 AI 分析在工作区内基于 `commandResultUrl` 自行下载并解压整包使用。
10. 写入工单事件，保留时间线痕迹。
11. 页面查看日志时可按当前记录的时间范围或调整后的时间范围，基于归档 ZIP 实时重新截取，不影响已入库的原始解析结果。

## 日志解析规则
- 日志时间范围可空，支持三种提交方式：
  - 直接范围：`logBeginTime + logEndTime`
  - 时间点范围：`logPointTime + rangeBeforeMinutes + rangeAfterMinutes`
  - 空范围：只下载整包压缩文件，不截取正文入库
- 日志行首按 `YYYY-MM-DD HH:mm:ss,SSS` 识别时间戳。
- 非时间戳行视为上一条有时间戳日志的堆栈/补充内容。
- 仅将命中时间范围的日志块写入结果，并原样保存日志文本，不再附加文件名前缀。
- 仅解析文件名包含 `_pos.log` 的日志文件，其他文件直接跳过。
- 跨文件拼接时按日志归档文件尾号逆序处理，保证尾号更小、时间更靠近当前的文件拼在后面。
- 日志按时间范围完整入库，不再静默截断；如果命中内容超过 `maxContentChars`，任务直接失败并提示缩小时间范围。

## 配置项
- 配置键：
  - `ticket.logPull.external`
  - `ticket.logPull.storage`
- `ticket.logPull.external` 支持项：
  - `insertUrl`
  - `pageUrl`
  - `headers.cookie`
  - `headers.origin`
  - `vendors[]`
    - `vendorId`：商家ID，日志拉取请求使用该值
    - `vendorCode`：商家编码，供页面展示与搜索
    - `vendorName`：商家名称，供页面展示与搜索
    - `stores[]`
      - `storeId`：门店ID，日志拉取请求使用该值
      - `storeCode`：门店编码，供页面展示与搜索
      - `storeName`：门店名称，供页面展示与搜索
- `ticket.logPull.storage` 支持项：
  - `mode`：`local` 或 `ftp`
  - `localDirectory`
  - `ftp.host/port/username/password/baseDir/passive/timeoutSec/encoding`
  - `pollIntervalSec`
  - `pollTimeoutSec`
  - `downloadTimeoutSec`
  - `maxContentChars`：入库上限，超出则失败并提示
- 启动时会自动补齐上述两个参数键，便于直接在“参数配置管理”中维护。

## 页面交互
- 工单主列表新增“日志拉取”状态列，展示最近一次任务状态。
- 工单详情新增“日志拉取”标签页：
  - 提交拉取任务改为弹窗，进入标签页后默认只展示拉取记录列表。
  - 顶部提供“拉取日志”按钮打开提交弹窗。
  - 商家、门店选项改为读取服务端参数配置；商家和门店联动，必须先选择商家才能选择门店。
  - 商家下拉展示名称/编码/ID；门店下拉展示名称/`org_no`/`sap_org_no`，并支持按 `org_no`、`sap_org_no`、名称模糊搜索。
  - 门店下拉的实际回填值使用 `org_no` 字符串，日志提交和外部请求都按该值传递，不再使用旧的数值门店主键。
  - 日志时间范围可空，填写时支持“开始/结束时间”或“时间点前后时长”二选一输入；空时只下载整包压缩文件，供 AI 分析解压使用。
  - 参数配置入口改为通用提示按钮，点击后展示参数说明与系统参数键。
  - 下方查看记录列表和异常信息。
  - 日志文本改为点击记录后弹窗查看，默认展示入库内容；切换到“原始文档”后才会按弹窗里的时间范围实时重截 ZIP。
  - 后端只传压缩结果，前端通过 `decompressText` 解压后展示。
  - 弹窗内展示“本次截取范围”，并允许在原始文档模式下调整后重新查看。
  - 日志内容默认不换行，支持通过开关切换换行显示。
  - 任务运行中自动轮询刷新列表状态。
- 日志拉取管理页新增“门店配置”入口：
  - 可按 `group_no`、`vender_no`、`org_no`、`sap_org_no`、关键字搜索。
  - 支持下载 Excel 模板、选择 xlsx 文件导入。
  - 导入方式分为增量导入和覆盖导入。
  - 增量导入时按 `vender_no + org_no + sap_org_no` 三字段联合唯一键查重，三者同时相同才视为重复；命中则覆盖更新，未命中则新增。
  - 导入过程先批量读取已有配置，再在内存中完成 upsert，避免逐行查库和重复 flush。
  - 覆盖导入会先清空门店配置表再写入新数据。
- 工单详情页新增项目到 `vender_no` 的映射维护能力，日志拉取提交前会按当前项目自动带出商家编号，减少人工填写。
- 日志拉取弹窗中的门店下拉会在商家 ID 变化后重新查询对应门店，仅展示当前商家下的门店，避免跨商家误选。
- 全链路新增步骤日志，记录跳过原因、执行节点和失败原因，方便排查工单号在“提交、轮询、下载、解析、导入”中的实际进度。

## 当前限制
- 解析文本仅对 `commandDataType=1` 的日志包生效；DB 包当前只归档，不做文本展开。
- 后台任务当前使用进程内线程池，适合当前单实例运行方式；如果后续部署为多实例，建议迁移到统一任务队列。
- “自动把日志和工单描述送模型分析”本次未接入，只保留了时间线与日志内容沉淀，后续可在此基础上追加模型调用链路。
