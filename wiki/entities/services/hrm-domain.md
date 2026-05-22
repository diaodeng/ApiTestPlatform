---
title: HRM 测试管理域
type: entity
entity_category: service
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - server/module_hrm/controller/project_controller.py
  - server/module_hrm/controller/case_controler.py
  - server/module_hrm/controller/web_case_controller.py
  - server/module_hrm/service/project_service.py
  - server/module_hrm/service/case_service.py
  - server/module_hrm/service/web_case_service.py
  - server/module_hrm/dao/project_dao.py
  - server/module_hrm/dao/case_dao.py
  - server/module_hrm/dao/web_case_dao.py
  - server/module_hrm/entity/do/project_do.py
  - server/module_hrm/entity/do/case_do.py
  - server/module_hrm/entity/vo/web_case_vo.py
  - server/module_hrm/enums/enums.py
  - server/module_hrm/perms.py
---

# HRM 测试管理域

HRM 域承载项目、模块、配置、用例、套件、执行计划、报告、环境、接口、Web 测试、桌面测试、Mock、转发规则、Agent 与工具能力。

```mermaid
graph TD
  A[HRM 控制器] --> B[测试管理服务]
  B --> C[用例/套件/报告/环境]
  B --> D[Web/桌面录制与执行]
  B --> E[Mock 与转发规则]
  B --> F[接口与 DebugTalk]
  B --> G[权限定义]
```

## 主要子模块

- 项目管理、模块管理、配置管理、用例管理。
- 测试套件、执行计划、报告管理、环境管理。
- 接口管理、Web 测试、桌面测试、Agent 管理、转发规则管理、Mock 管理。

## 参见

- [模块全景图](../../concepts/module-landscape.md)
- [HRM 核心数据模型](../data-models/hrm-core-models.md)
- [HRM 枚举集](../enums/hrm-enums.md)

## 被引用

- [项目总览](../../overview.md)
- [模块全景图](../../concepts/module-landscape.md)
