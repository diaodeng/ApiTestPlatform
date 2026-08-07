# 2026-07-24 版本号统一管理

## 背景
项目三端（server / web / client_new）版本号散落在多个文件且不一致，发版时需手动修改多处，容易遗漏。

## 改动

### Server
- **新建** `server/version.py` — 服务端版本号唯一来源，当前 `1.0.4.2`
- **修改** `server/config/env.py` — `AppSettings.app_version` 默认值从 `version.py` 读取，不再硬编码
- **修改** `server/.env.base` — 删除 `APP_VERSION` 行（不再通过环境变量覆盖版本号）
- **修改** `server/.env.dev / .env.prod / .env.test` — 删除 `APP_VERSION` 行
- **修改** `server/pyproject.toml` — 添加注释指向 `version.py`

### Client (client_new)
- **新建** `client_new/version.py` — 客户端版本号唯一来源，当前 `1.0.4.4`
- **修改** `client_new/utils/__init__.py` — `VERSION` 改为从 `version.py` 导入
- **修改** `client_new/pyproject.toml` — 版本号从 `0.1.0` 同步为 `1.0.4.4`
- **修改** `client_new/QTRClientNew.spec` — 从 `version.py` 动态读取版本号，打包时设置 exe 文件属性中的版本信息（此前缺失）
- **修改** `client_new/QTRClientNewPortable.spec` — 同上

### Web
无改动，`web/package.json` 已是唯一版本来源。

## 发版流程变更

**之前**：改 N 个文件的版本号
**之后**：每端只需改一个文件

| 端 | 修改位置 |
|----|----------|
| server | `server/version.py` |
| client_new | `client_new/version.py` |
| web | `web/package.json` |

注意：`pyproject.toml` 中的 `version` 字段仍需**手动同步**（Python 包元数据，无法动态读取）。
