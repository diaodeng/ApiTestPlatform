# 2026-09-15 日志拉取管理页自动拉取记录整行错位修复

## 问题现象

prod 环境日志拉取管理页（工单管理 → 日志拉取管理）中，**自动拉取**的记录整行数据从"拉取人"列开始向左错位一格：拉取人列显示"日志"（数据类型的值）、数据类型列显示 vendor/store/pos、保存方式列显示拉取参数……且相邻单元格文字互相重叠，"自动"标记完全消失。人工拉取的记录显示正常。

## 根因

提交 `ac45a758`（fix: 手动拉取日志的复用）为列表新增"拉取人"列时引入了函数名不一致：

- 模板 `web/src/views/ticket/logPullRecord/index.vue` 中"拉取人"列的自动拉取分支（`pullSource === 'automation'`）调用的是 `getPullSourceSceneLabel(scope.row.pullSourceScene)`；
- 而 `<script setup>` 实际从 `constants.js` 导入的函数名是 `getLogPullSourceSceneLabel`。

由于模板调用了未定义的函数，凡是自动拉取记录渲染"拉取人"单元格的 `el-tooltip` 分支时，行渲染函数抛出 `TypeError: getPullSourceSceneLabel is not a function`：

- 生产构建下表现为该行"拉取人"的 `<td>` 被渲染成注释占位节点（`<!---->`），后续单元格整体左移一格，且因列宽按 colgroup 固定分配、无裁剪的内容溢出到相邻单元格，形成截图中的"错位 + 文字重叠"；
- 开发构建下表现为整行渲染失败、自动拉取记录直接不显示。

人工记录走 `v-else` 分支，不调用该函数，因此显示正常——这也解释了"只有自动拉取记录错位"的现象。

该问题与后端无关：后端 `_to_record_list_item` 已按 `pullSource` 正确填充 `puller`（自动化记录为"自动拉取"），数据库也已执行 `pull_source` 迁移 SQL。

## 变更内容

- `web/src/views/ticket/logPullRecord/index.vue`：模板中"拉取人"列 tooltip 内容的函数调用由 `getPullSourceSceneLabel(...)` 修正为与导入一致的 `getLogPullSourceSceneLabel(...)`，一行修复，无其他逻辑改动。

## 验证过程

1. **DOM 复现**：用真实构建产物 + 模拟后端接口（含 `pullSource: 'automation'` 的记录）加载页面，自动拉取行 `td` 数量为 13（人工行 14），"拉取人"列位置为注释节点，错位表现与线上截图完全一致。
2. **二分定位**：去掉该列 `show-overflow-tooltip` 无效；去掉 `el-tooltip` 分支后行渲染恢复 → 锁定 tooltip 分支；注入错误捕获后拿到 `TypeError: _ctx.getPullSourceSceneLabel is not a function`，根因确认。
3. **修复验证**：修正函数名后，dev 环境与重新构建的生产包中，自动拉取行恢复 14 个 `td`，"拉取人"列正确显示"自动"标记，各列数据对齐。
4. **兼容场景**：分别模拟新版后端（`pullSource=automation`）、旧版后端（无 `pullSource`/`puller` 字段）、旧版后端+系统账号创建三种数据，均正常渲染（分别显示"自动"、"—"、创建人），无回归。

## 注意事项

- 需重新部署前端构建产物（本次已执行 `npm run build:prod` 并验证）。
- 若线上仍见错位，请确认浏览器加载的是最新构建的入口 chunk（旧页面可能被浏览器缓存，强刷即可）。
