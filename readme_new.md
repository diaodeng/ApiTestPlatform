# API Test Platform 架构文档

## 一、项目概述

API Test Platform 是一个完整的 API 测试平台，包含 Web 前端、后端服务和一个轻量级桌面客户端。

## 二、系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端层 (Client)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐                                                        │
│  │   client_new/   │  PySide6 桌面客户端                                    │
│  │                 │  ├── main.py (入口)                                    │
│  │   桌面客户端     │  ├── ui/ (界面层)                                       │
│  │                 │  │   ├── pages/ (页面: agent, mitmproxy, pos, sql等)    │
│  │                 │  │   ├── widgets/ (自定义组件)                          │
│  │                 │  │   └── dialogs/ (对话框)                             │
│  │                 │  ├── services/ (服务层)                                │
│  │                 │  │   ├── mitmproxy_service/ (代理服务)                 │
│  │                 │   │   └── pos/ (网络抓包服务)                          │
│  │                 │  ├── server/ (内置Agent服务)                          │
│  │                 │  ├── controller/ (控制器)                              │
│  │                 │  ├── models/ (数据模型)                                │
│  │                 │  └── workers/ (工作线程)                               │
│  └─────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP/WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              服务端层 (Server)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐                                                        │
│  │   server/       │  FastAPI 后端服务                                      │
│  │                 │                                                        │
│  │   后端服务      │  ├── app.py / server.py (入口)                         │
│  │                 │                                                        │
│  │                 │  ├── module_admin/ (管理后台模块)                       │
│  │                 │  │   ├── controller/ (控制器)                         │
│  │                 │   │   ├── service/ (业务服务)                          │
│  │                 │   │   ├── dao/ (数据访问)                              │
│  │                 │   │   └── entity/ (实体)                               │
│  │                 │  │       ├── do/ (数据对象)                            │
│  │                 │  │       └── vo/ (视图对象)                            │
│  │                 │  │                                                    │
│  │                 │  ├── module_hrm/ (API测试核心模块)                     │
│  │                 │  │   ├── controller/ (API/用例/项目/环境等控制器)       │
│  │                 │  │   ├── service/ (业务服务)                           │
│  │                 │  │   │   └── runner/ (用例执行器)                       │
│  │                 │  │   ├── dao/ (数据访问)                              │
│  │                 │  │   ├── entity/ (实体)                               │
│  │                 │  │   └── utils/ (工具类)                              │
│  │                 │  │                                                    │
│  │                 │  ├── module_qtr/ (QTR任务调度)                        │
│  │                 │  │   ├── controller/                                  │
│  │                 │  │   └── service/                                     │
│  │                 │  │                                                    │
│  │                 │  ├── module_task/ (任务调度)                          │
│  │                 │  │   ├── scheduler_qtr.py                             │
│  │                 │   │   └── task_register.py                           │
│  │                 │  │                                                    │
│  │                 │  ├── agentTools/ (Agent工具)                          │
│  │                 │  │   ├── agent_plus.py                               │
│  │                 │  │   └── common/ (工具类)                             │
│  │                 │  │                                                    │
│  │                 │  ├── config/ (配置管理)                               │
│  │                 │  ├── common/ (公共组件/权限)                           │
│  │                 │  ├── middlewares/ (中间件)                           │
│  │                 │  ├── exceptions/ (异常处理)                           │
│  │                 │  └── utils/ (工具类)                                   │
│  └─────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP/Vue组件渲染
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Web)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐                                                        │
│  │   web/          │  Vue3 + Vite 前端                                     │
│  │                 │  ├── src/                                              │
│  │   Web前端       │  │   ├── api/ (API调用层)                              │
│  │                 │  │   │   ├── hrm/ (用例/API/项目等API)                  │
│  │                 │  │   │   ├── monitor/ (监控API)                       │
│  │                 │  │   │   ├── qtr/ (任务调度API)                        │
│  │                 │   │   │   └── system/ (系统管理API)                    │
│  │                 │  │   │                                                │
│  │                 │  │   ├── views/ (页面)                                 │
│  │                 │  │   │   └── hrm/ (用例/API/报告等页面)                │
│  │                 │  │   │                                                │
│  │                 │  │   ├── components/ (组件)                          │
│  │                 │  │   │   ├── hrm/ (业务组件)                          │
│  │                 │  │   │   └── qtr/ (QTR组件)                          │
│  │                 │  │   │                                                │
│  │                 │  │   ├── layout/ (布局)                               │
│  │                 │  │   ├── router/ (路由)                              │
│  │                 │  │   ├── store/ (状态管理)                           │
│  │                 │  │   ├── plugins/ (插件)                             │
│  │                 │  │   └── utils/ (工具)                               │
│  │                 │  └── dist/ (构建产物)                                 │
│  └─────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 三、技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 后端 | FastAPI | 高性能 Web 框架 |
| 后端 | SQLAlchemy | ORM |
| 后端 | APScheduler | 任务调度 |
| 后端 | Celery | 异步任务队列 |
| 后端 | Redis | 缓存/消息队列 |
| 前端 | Vue3 | 渐进式 JS 框架 |
| 前端 | Element Plus | UI 组件库 |
| 前端 | Pinia | 状态管理 |
| 桌面客户端 | PySide6 | Qt for Python |
| 桌面客户端 | mitmproxy | HTTP 代理/抓包 |
| 数据库 | SQLite/MySQL | 数据存储 |

## 四、核心模块说明

### 4.1 module_hrm (API测试核心模块)

HRM = HTTP Request Manager，负责 API 测试的核心功能：

| 模块 | 功能 |
|------|------|
| api_controler | API 接口管理 |
| case_controler | 测试用例管理 |
| project_controler | 项目管理 |
| env_controller | 环境变量管理 |
| debugtalk_controller | 调试函数管理 |
| mock_controller | Mock 服务 |
| forward_rules_controller | 转发规则 |
| report_controler | 测试报告 |
| suite_controller | 测试套件 |
| runner_controler | 用例执行 |

### 4.2 module_admin (管理后台)

提供系统管理功能：

| 模块 | 功能 |
|------|------|
| user_controller | 用户管理 |
| role_controller | 角色管理 |
| menu_controller | 菜单管理 |
| dept_controller | 部门管理 |
| dict_controller | 字典管理 |
| config_controller | 配置管理 |
| job_controller | 定时任务 |
| log_controller | 日志管理 |

### 4.3 module_qtr / module_task (任务调度)

- **module_qtr**: QTR (Quicker Test Runner) 任务调度服务
- **module_task**: 通用任务调度注册和调度器

### 4.4 client_new 桌面客户端

| 模块 | 功能 |
|------|------|
| ui/pages | Agent页面、mitmproxy页面、POS页面、SQL查询页面 |
| services/mitmproxy_service | HTTP 代理服务，支持抓包、拦截、断点设置 |
| services/pos | 网络流量抓取服务 |
| server/ | 内置 Agent 服务器 |

## 五、数据流向

```
桌面客户端 (PySide6)
    │
    ├─ mitmproxy_service ──抓包/代理──► 流量数据 ──► UI展示
    │
    └─ server/agent_server ──HTTP/WebSocket──► FastAPI 后端
                                                       │
                                                       ├─ SQLite/MySQL (数据持久化)
                                                       │
                                                       └─ Web 前端 (Vue3)
```

## 六、部署架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Web 前端   │     │  FastAPI 后端 │     │    MySQL     │
│   (Nginx)    │◄───►│   (uvicorn)   │◄───►│   (数据)      │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Redis     │
                     │  (缓存/队列)  │
                     └──────────────┘
```

## 七、目录结构总览

```
api-test-platform/
├── server/                 # FastAPI 后端
│   ├── app.py             # 入口
│   ├── module_admin/      # 管理后台
│   ├── module_hrm/        # API测试核心
│   ├── module_qtr/        # QTR调度
│   ├── module_task/       # 任务调度
│   ├── agentTools/        # Agent工具
│   ├── config/            # 配置
│   ├── common/            # 公共组件
│   ├── middlewares/        # 中间件
│   ├── exceptions/         # 异常
│   └── utils/              # 工具
│
├── web/                   # Vue3 前端
│   ├── src/
│   │   ├── api/          # API调用
│   │   ├── views/        # 页面
│   │   ├── components/   # 组件
│   │   ├── router/       # 路由
│   │   └── store/        # 状态
│   └── dist/             # 构建产物
│
└── client_new/           # PySide6 桌面客户端
    ├── main.py           # 入口
    ├── ui/               # 界面
    ├── services/         # 服务
    ├── server/           # 内置服务
    ├── models/           # 模型
    └── workers/          # 工作线程
```

## 八、启动方式

### 后端服务
```bash
cd server
uv sync
uv run python app.py --env=dev
```

### Web 前端
```bash
cd web
npm run dev
```

### 桌面客户端
```bash
cd client_new
uv sync
uv run python main.py
```
