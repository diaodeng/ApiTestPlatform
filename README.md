<h1 align="center" style="margin: 30px 0 30px; font-weight: bold;">QTestRunner</h1>
<h4 align="center">基于RuoYi-Vue3+FastAPI前后端分离的快速开发框架</h4>


[本项目gitee地址](https://gitee.com/zywstart/api-test-platform.git)
[本项目github地址](https://github.com/diaodeng/ApiTestPlatform.git)


## 平台简介

RuoYi-Vue3-FastAPI是一套全部开源的快速开发平台，毫无保留给个人及企业免费使用。

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

## 项目开发及发布相关

### 开发

```bash
# 克隆项目
git clone https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI.git

# 进入项目根目录
cd RuoYi-Vue3-FastAPI
```

#### 前端
```bash
# 进入前端目录
cd ruoyi-fastapi-frontend

# 安装依赖
npm install 或 yarn --registry=https://registry.npmmirror.com

# 建议不要直接使用 cnpm 安装依赖，会有各种诡异的 bug。可以通过如下操作解决 npm 下载速度慢的问题
npm install --registry=https://registry.npmmirror.com

# 启动服务
npm run dev 或 yarn dev
```

#### 后端
```bash
# 进入后端目录
cd ruoyi-fastapi-backend

# 安装项目依赖环境
pip3 install -r requirements.txt

# 配置环境
在.env.dev文件中配置开发环境的数据库和redis

# 运行sql文件
1.新建数据库ruoyi-fastapi(默认，可修改)
2.使用命令或数据库连接工具运行sql文件夹下的ruoyi-fastapi.sql

# 运行后端
python3 app.py --env=dev
```

#### 访问
```bash
# 默认账号密码
账号：admin
密码：admin123

# 浏览器访问
地址：http://localhost:80
```

### 发布

#### 前端
```bash
# 构建测试环境
npm run build:stage 或 yarn build:stage

# 构建生产环境
npm run build:prod 或 yarn build:prod
```

#### 后端
```bash
# 配置环境
在.env.prod文件中配置生产环境的数据库和redis

# 运行后端
python3 app.py --env=prod
```
