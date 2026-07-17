# 工单列表与详情默认折叠优化

## 变更内容

1. 工单列表搜索区默认只展示关键字、自然语言、状态、外部工单号和提交时间，其他筛选项默认折叠。
2. 搜索区在重置按钮后新增“展开更多筛选/收起更多筛选”按钮，用于手动控制其他筛选项的显示。
3. 工单详情页顶部信息默认仅展示前九项，并保留描述与翻译区域可见，其他信息通过标题后的按钮展开或收起。
4. 工单详情页协同 tab 在版本选项加载完成后，会优先回填工单自身版本号；如果工单没有版本号，则回填当前项目下加载到的第一个可用版本。

## 影响范围

- `web/src/views/ticket/index.vue`
- `web/src/views/ticket/hooks/useTicketList.js`
- `web/src/views/ticket/components/TicketDetailWithList.vue`
- `web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`

## 说明

- 折叠状态默认是收起，不会清空被隐藏筛选项的值。
- 详情页更多信息收起后，仅隐藏顶部补充信息，不影响描述、翻译和下方 tabs。
