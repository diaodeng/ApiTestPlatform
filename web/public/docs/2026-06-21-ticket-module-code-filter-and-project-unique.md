# 工单模块 Code 筛选与项目内唯一约束

## 背景

工单列表和统计页原先只能按模块 ID/名称筛选，不方便跨项目按同一业务模块 code 聚合问题。同时模块管理对 `moduleCode` 做了全局唯一限制，和当前“同类项目复用相同模块 code”的维护方式不一致。

## 本次调整

1. 工单列表页新增“模块Code”下拉筛选。
2. 工单统计页新增“模块Code”多选下拉筛选。
3. 模块 code 下拉不写死前端，统一根据后端模块选项接口动态生成。
4. 模块管理中的 `moduleCode` 唯一性由“全局唯一”改为“同一项目下唯一”。

## 接口调整

### 1. 模块选项接口

`GET /ticket/modules/options`

返回字段补充：

```json
{
  "moduleId": 1001,
  "moduleName": "支付中心",
  "moduleCode": "payment",
  "projectId": 2001
}
```

前端根据 `moduleCode` 去重后生成筛选下拉。

### 2. 工单列表接口

`GET /ticket/list`

新增查询参数：

```text
moduleCode=payment
```

说明：

1. 未选择项目时，会匹配所有项目下 `moduleCode=payment` 的有效模块。
2. 选择项目后，只匹配当前项目下该 code 对应的模块。
3. 如果同时传 `moduleId` 和 `moduleCode`，最终按交集过滤。

### 3. 工单统计接口

`GET /ticket/statistics/overview`

新增查询参数：

```text
moduleCodes=payment,order
```

说明：

1. 统计页支持模块 code 多选。
2. `projectIds`、`moduleIds`、`moduleCodes` 会共同参与过滤。
3. 所有统计维度和状态流转统计共用同一套过滤条件。

## 模块管理约束

模块管理保存时：

1. 不再检查 `moduleCode` 全局唯一。
2. 只检查同一个 `projectId` 下是否已存在相同 `moduleCode`。
3. 编辑模块时，如果修改了所属项目，也会按目标项目重新校验唯一性。

## 影响范围

- `server/modules/ticket/entity/vo/ticket_vo.py`
- `server/modules/ticket/controller/ticket_controller.py`
- `server/modules/ticket/service/ticket_service.py`
- `server/modules/ticket/dao/ticket_dao.py`
- `server/module_hrm/service/module_service.py`
- `web/src/views/ticket/index.vue`
- `web/src/views/ticket/statistics/index.vue`
- `web/src/views/hrm/module/index.vue`

## 验证建议

1. 在模块管理中，分别在两个不同项目下保存相同 `moduleCode`，应允许成功。
2. 在同一项目下新增或编辑为重复 `moduleCode`，应提示失败。
3. 工单列表页切换项目时，模块 code 下拉应随项目动态变化。
4. 工单统计页选择一个模块 code 后，接口请求中应带上 `moduleCodes` 参数。
