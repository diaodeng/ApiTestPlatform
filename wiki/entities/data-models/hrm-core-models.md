---
title: HRM 核心数据模型
type: entity
entity_category: data_model
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - server/module_hrm/entity/do/project_do.py
  - server/module_hrm/entity/do/module_do.py
  - server/module_hrm/entity/do/config_do.py
  - server/module_hrm/entity/do/case_do.py
  - server/module_hrm/entity/do/suite_do.py
  - server/module_hrm/entity/do/report_do.py
  - server/module_hrm/entity/do/run_detail_do.py
  - server/module_hrm/entity/do/run_error_do.py
  - server/module_hrm/entity/do/env_do.py
  - server/module_hrm/entity/do/api_do.py
  - server/module_hrm/entity/do/mock_do.py
  - server/module_hrm/entity/do/forward_rules_do.py
  - server/module_hrm/entity/do/agent_do.py
  - server/module_hrm/entity/do/web_case_do.py
  - server/module_hrm/entity/do/desktop_case_do.py
---

# HRM 核心数据模型

HRM 核心数据模型覆盖项目、模块、配置、用例、套件、报告、执行记录、环境、接口、Mock、转发规则、Agent、桌面测试和 Web 测试。

```mermaid
erDiagram
  HrmProject ||--o{ HrmModule : contains
  HrmProject ||--o{ HrmEnv : uses
  HrmModule ||--o{ HrmCase : contains
  HrmCase ||--o{ HrmRunDetail : produces
  HrmSuite ||--o{ HrmSuiteDetail : contains
  HrmReport ||--o{ HrmRunDetail : summarizes
```

## 主要实体

- `HrmProject`、`HrmModule`、`HrmConfig`
- `HrmCase`、`HrmSuite`、`HrmSuiteDetail`
- `HrmReport`、`HrmRunDetail`、`HrmRunError`
- `HrmEnv`、`HrmApi`、`HrmMockRule`、`HrmMockResponse`
- `HrmAgent`、`HrmForwardRules`、`HrmWebCase`、`HrmDesktopCase`

## 参见

- [HRM 测试管理域](../services/hrm-domain.md)
- [HRM 枚举集](../enums/hrm-enums.md)

## 被引用

- [项目总览](../../overview.md)
- [HRM 测试管理域](../services/hrm-domain.md)
