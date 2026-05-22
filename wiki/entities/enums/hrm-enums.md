---
title: HRM 枚举集
type: entity
entity_category: enum
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - server/module_hrm/enums/enums.py
---

# HRM 枚举集

HRM 枚举集统一描述测试管理域中的状态、类型、范围和错误码。

```mermaid
mindmap
  root((HRM 枚举))
    推送
      PushTypeEnum
      PushReminderEnum
      AllowPushEnum
    用例与执行
      CaseRunStatus
      CaseStatusEnum
      RunTypeEnum
      RunModelEnum
      TaskStatusEnum
    测试步骤
      TstepTypeEnum
      ParameterTypeEnum
      CodeTypeEnum
    转发与 Mock
      ForwardRulesEnum
      ForwardRuleMatchTypeEnum
      MockTypeEnum
```

## 代表性枚举

- `PushTypeEnum`、`PushReminderEnum`、`AllowPushEnum`
- `DataType`、`FuncTypeEnum`、`CaseRunStatus`、`QtrDataStatusEnum`、`CaseStatusEnum`
- `TstepTypeEnum`、`RunTypeEnum`、`RunModelEnum`、`ParameterTypeEnum`
- `TaskStatusEnum`、`ForwardRulesEnum`、`ForwardRuleMatchTypeEnum`
- `AgentResponseEnum`、`ScopeEnum`、`AssertOriginalEnum`、`CodeTypeEnum`
- `ConfigDataTypeEnum`、`MockTypeEnum`、`UrlContentEnum`

## 参见

- [HRM 测试管理域](../services/hrm-domain.md)
- [HRM 核心数据模型](../data-models/hrm-core-models.md)

## 被引用

- [项目总览](../../overview.md)
- [HRM 测试管理域](../services/hrm-domain.md)
