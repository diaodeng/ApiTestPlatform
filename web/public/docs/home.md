<h1 align="center" style="margin: 30px 0 30px; font-weight: bold;">TRunner</h1>

[//]: # (<h4 align="center">基于RuoYi-Vue3+FastAPI前后端分离的用例管理、测试、调试平台</h4>)

[//]: # (<p align="center">)

[//]: # (	<a href="https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/stargazers"><img src="https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/badge/star.svg?theme=dark"></a>)

[//]: # (    <a href="https://github.com/insistence/RuoYi-Vue3-FastAPI"><img src="https://img.shields.io/github/stars/insistence/RuoYi-Vue3-FastAPI?style=social"></a>)

[//]: # (	<a href="https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI"><img src="https://img.shields.io/badge/RuoYiVue3FastAPI-v1.1.2-brightgreen.svg"></a>)

[//]: # (	<a href="https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/blob/master/LICENSE"><img src="https://img.shields.io/github/license/mashape/apistatus.svg"></a>)

[//]: # (    <img src="https://img.shields.io/badge/python-≥3.8-blue">)

[//]: # (    <img src="https://img.shields.io/badge/MySQL-≥5.7-blue">)

[//]: # (</p>)



[//]: # (## 平台简介)


[//]: # (RuoYi-Vue3-FastAPI是一套全部开源的快速开发平台，毫无保留给个人及企业免费使用。)

[//]: # ()
[//]: # (* 前端采用Vue、Element Plus，基于<u>[RuoYi-Vue3]&#40;https://github.com/yangzongzhuan/RuoYi-Vue3&#41;</u>前端项目修改。)

[//]: # (* 后端采用FastAPI、sqlalchemy、MySQL、Redis、OAuth2 & Jwt。)

[//]: # (* 权限认证使用OAuth2 & Jwt，支持多终端认证系统。)

[//]: # (* 支持加载动态权限菜单，多方式轻松权限控制。)

[//]: # (* Vue2版本：)

[//]: # (  - Gitte仓库地址：https://gitee.com/insistence2022/RuoYi-Vue-FastAPI)

[//]: # (  - GitHub仓库地址：https://github.com/insistence/RuoYi-Vue-FastAPI)
[//]: # (* 原仓库地址：)
[//]: # (  - [Gitte仓库地址]&#40;https://gitee.com/insistence2022/dash-fastapi-admin&#41;)
[//]: # (  - [GitHub仓库地址]&#40;https://github.com/insistence/Dash-FastAPI-Admin&#41;)

[//]: # (* 特别鸣谢：<u>[RuoYi-Vue3]&#40;https://github.com/yangzongzhuan/RuoYi-Vue3&#41;</u>)

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
