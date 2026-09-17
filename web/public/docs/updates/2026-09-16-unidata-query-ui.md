# 新增大数据查询（Unidata）功能

- 新增后端模块 `server/modules/unidata/`：数据源配置服务（系统参数 `unidata.query.sources`）、Unidata OpenAPI 网关服务（库权限/表清单/只读 SQL 执行）、查询编排服务与 `/unidata/*` 控制器。
- 新增前端页面「大数据查询」（菜单：大数据/大数据查询，路由 `/bigdata/query`，组件 `unidata/index`）：数据源切换、权限驱动的库/表浏览（带 stable/gray 分层标签）、只读 SQL 编辑与结果展示（动态列、行数、耗时、截断标记）。
- 菜单通过代码化权限同步机制注册（`modules/unidata/perms.py`），启动时自动同步到菜单管理。
- 配置方式：统一凭证管理创建 API Key 凭证 + 「大数据查询」业务绑定，系统参数 `unidata.query.sources` 维护数据源清单（baseUrl/workbenchCode/credentialBindingId/defaultEngine）。密钥不落业务配置。
- 关键适配点：keyword 搜索返回值带 HTML 高亮需剥离；表接口仅支持 keyword 子串搜索需按精确库名过滤；Unidata 业务失败以 HTTP 502 返回需转译 message；当前 UAT 未配置 StarRocks 资源，默认引擎为 kyuubi。
- 引擎选择改为动态探测：新增 `GET /unidata/sources/{code}/engines`，用 `SELECT 1` 对 Unidata 契约候选引擎（kyuubi/starrocks）逐一真实探测并按 5 分钟 TTL 缓存，前端引擎下拉只展示探测可用的引擎（UAT 不可用的 starrocks 不显示），默认引擎跟随数据源配置的 defaultEngine。
- 左侧浏览改为库→表→字段三级懒加载树：展开库显示表（含中文名），展开表显示全部字段（名称/类型/备注，来自 Unidata table-detail 接口 `GET /unidata/sources/{code}/table-columns`），表节点悬停提供「+」按钮插入查询模板；库名过滤保留，原分页表列表移除。
- 表清单改为分块渐进加载：每次 200 张，列表底部出现「加载更多表（剩 N）」节点，点击追加下一块（el-tree append/remove 原地追加，保留已展开子树与滚动位置），避免大库一次渲染上千节点；库与字段保持全量加载（规模小、展开即需全量）。
- 菜单结构修正：顶级 C 菜单会被路由组装器生成无 "/" 前缀路径，导致 vue-router `Invalid path` 报错、动态路由注册中断；改为顶级 M 目录「大数据」（/bigdata）+ 子菜单「大数据查询」（/bigdata/query），与全库"目录包菜单"的既有约定一致。原菜单行按同步标记原地更新（路径与父级变更），角色授权关系不受影响。
- 新增单元测试 `server/tests/test_unidata_query_service.py`（8 个用例）。
- Prod 环境接入时仅需新增凭证/绑定并追加数据源配置，无需改代码。