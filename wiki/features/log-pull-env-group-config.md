---
title: 日志拉取环境分组配置
type: entity
entity_category: feature
source_type: code
knowledge_state: stable
confidence: high
created: 2026-08-12
updated: 2026-08-12
related_files:
  - server/modules/ticket/entity/vo/ticket_log_pull_vo.py
  - server/modules/ticket/controller/ticket_log_pull_controller.py
  - server/modules/ticket/service/log_pull/ticket_log_pull_service.py
  - web/src/components/ticket/LogPullConfigFields.vue
  - web/src/views/ticket/logPullRecord/index.vue
  - web/src/views/ticket/syncAutomation/index.vue
  - web/src/views/ticket/syncAutomation/hooks/useLogPullExternalConfig.js
  - web/src/api/ticket/logPull.js
  - web/src/api/ticket/ticket.js
---

# 日志拉取环境分组配置

## 概述

日志拉取外部接口配置从扁平多环境升级为 **"环境分组 → 子环境 → 商家映射"** 三层模型，实现用户选择环境分组和商家后自动匹配子环境及凭证，无需手动记忆子环境关系。

## 配置结构

配置存储在 `sys_config` 表，`config_key = "ticket.logPull.external"`，JSON 格式：

```json
{
  "prod": {
    "label": "生产环境",
    "items": {
      "prod": {
        "label": "生产环境",
        "insertUrl": "https://prod.xxx.com/api",
        "pageUrl": "https://prod.xxx.com",
        "credentialBindingId": "123",
        "origin": "https://erp.rta-os.com",
        "vendorFilter": ["*"]
      }
    },
    "defaultItem": "prod"
  },
  "uat": {
    "label": "UAT环境",
    "items": {
      "uat1": {
        "label": "UAT1",
        "insertUrl": "https://uat1.xxx.com/api",
        "pageUrl": "https://uat1.xxx.com",
        "credentialBindingId": "456",
        "origin": "https://uat1.rta-os.com",
        "vendorFilter": ["10001", "10002"]
      },
      "uat2": {
        "label": "UAT2",
        "insertUrl": "https://uat2.xxx.com/api",
        "pageUrl": "https://uat2.xxx.com",
        "credentialBindingId": "789",
        "origin": "https://uat2.rta-os.com",
        "vendorFilter": ["10003", "10004"]
      }
    },
    "defaultItem": null
  }
}
```

### 字段说明

| 层级 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 分组 | `label` | string | 用户可见的分组名称（如"生产环境"） |
| 分组 | `items` | object | 子环境映射，key 为子环境标识 |
| 分组 | `defaultItem` | string / null | 商家未匹配时的兜底子环境 key |
| 子环境 | `label` | string | 子环境展示名称 |
| 子环境 | `insertUrl` | string | 日志录入接口地址 |
| 子环境 | `pageUrl` | string | 页面列表查询地址 |
| 子环境 | `credentialBindingId` | string | 统一凭证绑定 ID |
| 子环境 | `origin` | string | 请求 Origin 头 |
| 子环境 | `vendorFilter` | string[] | `["*"]` 全部商家，或 `["10001","10002"]` 指定 |

## 向后兼容

- **旧单环境格式** `{insertUrl, pageUrl, credentialBindingId, ...}` → 自动升级为一个默认分组
- **旧多环境格式** `{env1: {insertUrl,...}, env2: {insertUrl,...}}` → 每个环境升级为独立分组，`vendorFilter` 设为 `["*"]`
- 升级在 `_normalize_external_config` 中自动完成，保存时写入新格式

## 日志拉取记录存储

- `TicketLogPullRecord.environment` 字段存储 `group_key:item_key` 格式（如 `uat:uat2`）
- 历史记录存储旧环境 key 仍可兼容，`_get_external_config_dict` 会遍历分组查找匹配

## 匹配逻辑

1. 用户选择环境分组（如 `uat`）
2. 用户选择商家（如 `10003`）
3. 前端调用 `GET /ticket/log-pull/resolve-env-item?group_key=uat&vender_no=10003`
4. 后端遍历 `uat.items`，检查各子环境的 `vendorFilter` 是否包含 `"*"` 或 `"10003"`
5. 匹配结果：
   - **无匹配**：前端提示"该商家在当前环境下未匹配到任何子环境配置"
   - **单匹配**：前端显示绿色提示"已匹配：UAT / UAT2"
   - **多匹配**：前端展示单选列表让用户选择

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ticket/log-pull/vendor-store-options` | 商家/门店联动选项（environments 返回 `[{key,label}]` 格式） |
| GET | `/ticket/log-pull/resolve-env-item?group_key=&vender_no=` | 解析环境分组+商家匹配的子环境列表 |
| GET | `/ticket/log-pull/external-config` | 获取分组格式外部接口配置 |
| PUT | `/ticket/log-pull/external-config` | 保存分组格式外部接口配置 |

## 配置页面入口

**工单同步自动化** → **外部接口** Tab

该 Tab 提供可视化的分组/子环境/商家映射/凭证绑定配置，支持：
- 新增/删除环境分组
- 新增/删除子环境，配置 insertUrl、pageUrl、凭证绑定、origin
- 商家范围多选（`*` 全部商家或指定商家 venderNo）
- 设置默认子环境（商家未匹配时的兜底）
- 凭证绑定下拉从统一凭证管理的 `ticket_log_pull` 类型绑定中获取
