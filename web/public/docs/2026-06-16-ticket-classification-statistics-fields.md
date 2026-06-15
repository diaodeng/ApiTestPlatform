# 工单分类统计独立字段与可视化枚举配置

## 背景

工单统计原先容易把流程状态、问题类型、是否真实问题、业务域和关闭结果混在一个分类文案里。现在按独立维度落库和展示，避免把“非问题”“已修复”等性质或结果写进流程状态。

## 字段模型

- 流程状态：继续使用 `status`，由工单工作流配置维护。
- 业务域：继续使用 `module_id/module_name`，不新增业务域字段。
- 工单类型：新增 `issue_type_id/issue_type_name`。
- 是否真实问题：继续使用 `is_problem`。
- 根因分类：新增 `root_cause_type`。
- 解决方式：新增 `solution_type`。
- 关闭结果：新增 `resolution_code/resolution_name`。

## 配置入口

`工单同步自动化` 页面新增“统计枚举配置”，通过系统参数 `ticket.sync.automation.statClassification` 保存：

- `issueTypes`：工单类型，可配置是否默认属于真实问题。
- `rootCauseTypes`：根因分类。
- `solutionTypes`：解决方式。
- `resolutions`：关闭结果，可配置是否默认属于真实问题。

默认枚举按本次设计初始化；保存时会去除空编码、按编码去重，避免空行覆盖默认配置。

## 使用范围

- 工单列表/表单：支持工单类型、是否真实问题筛选和展示；新增/编辑时选择工单类型可自动回填 `issue_type_name` 和 `is_problem`。
- 工单列表中的工单类型只展示 `issue_type_name` 或已命中配置枚举的 `issue_type_id`，不再回退旧 `category_name`，避免旧问题分类或模块文案被误显示成工单类型。
- 编辑工单时，模块名称继续以 `module_id` 为准回填；前端编辑弹窗不会因项目回填误清空模块，提交前也会按当前模块选项补齐 `module_name`。
- 当历史或外部同步模块不在当前项目模块选项中时，编辑弹窗会原样显示 `module_name` 文案并允许直接保存；只有用户手动选择现有模块时才写入标准 `module_id/module_name`。
- `1线人员` 与 `内部负责人` 在编辑弹窗中合并为单个人员选择控件；若历史名称无法匹配现有用户，控件内显示原始名称且保存时保留名称，用户改选后再写入标准用户 ID 与名称。
- 状态流转：可同步维护 `is_problem/root_cause_type/solution_type/resolution_code/resolution_name`，关闭结果会自动回填名称和问题性质。
- RCA：根因分类下拉复用同一套配置，保存后同步写入工单主表 `root_cause_type`。
- 统计页：新增工单类型、是否真实问题、根因分类、解决方式、关闭结果统计，同时保留旧 `categoryCounts/rootCauseCounts` 兼容视图。
- 外部同步/内网拉取：入库 payload 会保留并写入上述独立字段，不影响原有 `category_name` 与模块识别逻辑。

## 数据库变更

启动迁移已在 `server/config/get_db.py` 中补齐旧表字段。手工 SQL 见：

`server/sql/20260616_ticket_classification_statistics_columns.sql`
