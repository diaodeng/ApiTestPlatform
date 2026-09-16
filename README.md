<h1 align="center" style="margin: 30px 0 30px; font-weight: bold;">QTestRunner</h1>
<h4 align="center">基于RuoYi-Vue3+FastAPI前后端分离的接口测试平台</h4>


[本项目gitee地址](https://gitee.com/zywstart/api-test-platform.git)
[本项目github地址](https://github.com/diaodeng/ApiTestPlatform.git)


## 平台简介

QTestRunner（api-test-platform）是一套前后端分离 + 桌面客户端的接口测试平台，由三部分组成：

* **服务端**（`server/`）：FastAPI 后端，承担用例管理、任务调度、Agent 通信、AI 分析等业务；
* **Web 管理端**（`web/`）：Vue3 + Vite 前端（RuoYi-Vue3 模板），管理用例、任务、工单、AI 配置等；
* **桌面客户端**（`client_new/`）：pywebview 客户端，作为测试 Agent 注册到服务端，接收并执行下发任务（接口测试、桌面测试、Web 测试、抓包代理等），旧版 Flet 客户端（`client/`）保留但不再演进。

* 特别鸣谢：<u>[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)</u>

## 测试相关功能
1. 项目管理
2. 模块管理
3. 配置管理
4. 用例管理
5. 测试套件
6. 定时任务
7. 报告管理
8. 环境管理
9. 客户端管理: 可以将用例执行转发到对应的客户机执行，客户机启动时会自动注册到服务端
10. 转发规则管理： 转发规则，比如将固定开头的URL换成其他URL来请求
11. 接口管理

## 内置功能

1.  用户管理：用户是系统操作者，该功能主要完成系统用户配置。
2.  角色管理：角色菜单权限分配、设置角色按机构进行数据范围权限划分。
3.  菜单管理：配置系统菜单，操作权限，按钮权限标识等。
4.  部门管理：配置系统组织机构（公司、部门、小组）。
5.  岗位管理：配置系统用户所属担任职务。
6.  字典管理：对系统中经常使用的一些较为固定的数据进行维护。
7.  参数管理：对系统动态配置常用参数。
8.  通知公告：系统通知公告信息发布维护。
9.  操作日志：系统正常操作日志记录和查询；系统异常信息日志记录和查询。
10. 登录日志：系统登录日志记录查询包含登录异常。
11. 在线用户：当前系统中活跃用户状态监控。
12. 定时任务：在线（添加、修改、删除）任务调度包含执行结果日志。
13. 服务监控：监视当前系统CPU、内存、磁盘、堆栈等相关信息。
14. 缓存监控：对系统的缓存信息查询，命令统计等。
15. 系统接口：根据业务代码自动生成相关的api接口文档。

## 项目结构

```
api-test-platform
├── server/            # FastAPI 后端（uv 管理依赖，module_admin/module_qtr/module_task 按域分模块）
├── web/               # Vue3 + Vite 前端（RuoYi-Vue3 模板，Docker 由 nginx 托管构建产物）
│   └── public/docs/   # 面向用户的说明文档与更新记录（前端自动发现展示）
├── client_new/        # 桌面客户端（pywebview + WebView2，测试 Agent，当前主力）
├── client/            # 旧版 Flet 客户端（保留，不再演进）
└── wiki/              # 项目内部知识库（架构、组件、流程设计文档）
```

## 快速开始

### 后端（server/）

```bash
# 进入后端目录
cd server

# 安装依赖（uv 管理，含 .venv 创建）
uv sync

# 配置环境
# .env.base 为公共配置，.env.dev / .env.prod 分别对应开发/生产环境的数据库与 redis
# 数据库支持 MySQL（DB_TYPE=mysql）与 SQLite（DB_TYPE=sqlite）

# 初始化数据库
# 新建数据库后执行 server/sql/apitest.sql（增量变更脚本在 server/sql/ 下按日期追加）

# 启动后端
uv run python app.py --env=dev

# 代码检查
uv run ruff check .
```

### 前端（web/）

```bash
# 进入前端目录
cd web

# 安装依赖
npm install --registry=https://registry.npmmirror.com

# 启动开发服务
npm run dev

# 浏览器访问（默认账号密码 admin / admin123，访问地址以启动输出为准）
```

### 桌面客户端（client_new/）

```bash
# 进入客户端目录
cd client_new

# 安装依赖
uv sync

# 启动客户端（作为测试 Agent 注册到服务端）
uv run python main.py
```

旧版 Flet 客户端（client/）启动方式：`cd client && uv run flet run`。

## 构建与发版

### 桌面客户端一键构建（client_new/scripts/build_release.py）

```bash
cd client_new

# 开发打包（默认）：允许未提交代码，产物在 dist_dev/
uv run python scripts/build_release.py

# 正式发版打包：三道硬闸门（工作区干净、HEAD 上有 tag v{version.py 版本}、Gitee 无同名 release），
# 任一不满足拒绝构建；产物在 dist_release/（exe、portable.zip、插件、sha256、release-manifest.json）
uv run python scripts/build_release.py --mode release
```

- 版本号唯一来源 `client_new/version.py`（纯数字四段式），tag 格式 `v{版本号}`；
- 发版顺序：改 version.py → commit → 打 tag → release 构建 → 按 `release-manifest.json` 清单上传 Gitee release；
- 主程序重依赖拆分为插件包（desktop-test / web-test / proxy），由客户端「插件管理」在线下载安装；
- 客户端内置检查更新（走 Gitee release），详见 `client_new/README.md` 与 `wiki/entities/components/client-release-build.md`。

### Docker 部署

```bash
# 后端（qtr-api，端口 9099，挂载 server/.env.dev 配置）
cd server && docker compose up -d

# 前端（多阶段构建，nginx 托管 web/dist 构建产物）
cd web && docker build -t qtr-web .
```

## 文档

- **用户说明**：`web/public/docs/`（平台内自动发现展示），覆盖 Agent 连接、插件管理、抓包 Mock、AI 配置等模块使用说明；
- **更新记录**：`web/public/docs/updates/`（按时间倒序）；
- **内部设计知识库**：`wiki/`（架构、组件、流程设计，供开发与 AI 分析使用）。
