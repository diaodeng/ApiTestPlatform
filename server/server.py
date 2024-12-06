from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sub_applications.handle import handle_sub_applications
from middlewares.handle import handle_middleware
from exceptions.handle import handle_exception
from module_admin.controller.login_controller import loginController
from module_admin.controller.captcha_controller import captchaController
from module_admin.controller.user_controller import userController
from module_admin.controller.menu_controller import menuController
from module_admin.controller.dept_controller import deptController
from module_admin.controller.role_controller import roleController
from module_admin.controller.post_controler import postController
from module_admin.controller.dict_controller import dictController
from module_admin.controller.config_controller import configController
from module_admin.controller.notice_controller import noticeController
from module_admin.controller.log_controller import logController
from module_admin.controller.online_controller import onlineController
from module_admin.controller.job_controller import jobController
from module_admin.controller.server_controller import serverController
from module_admin.controller.cache_controller import cacheController
from module_admin.controller.common_controller import commonController
from module_hrm.controller.project_controller import projectController
from module_hrm.controller.debugtalk_controller import debugtalkController
from module_hrm.controller.module_controler import moduleController
from module_hrm.controller.env_controller import envController
from module_hrm.controller.case_controler import caseController
from module_hrm.controller.runner_controler import runnerController
from module_hrm.controller.report_controler import reportController
from module_hrm.controller.config_controller import hrmConfigController
from module_hrm.controller.common_controller import hrmCommonController
from module_hrm.controller.api_controler import hrmApiController
from module_hrm.controller.qtrJob_controller import qtrJobController
from module_hrm.controller.suite_controller import suiteController
from module_hrm.controller.checkStatus_controler import qtrServiceStatusController
from module_qtr.controller.agent_controller import agentController, startup_handler
from module_hrm.controller.forward_rules_controller import forwardRulesController
from module_hrm.controller.test_controller import testController
from module_hrm.controller.agent_controller import agentController as agentManagerController

from config.env import AppConfig
from config.get_redis import RedisUtil
from config.get_db import init_create_table
from config.get_scheduler import sys_scheduler_util as SysSchedulerUtil
from config.get_qtr_scheduler import qtr_scheduler_util as QtrSchedulerUtil
from utils.log_util import logger
from utils.common_util import worship

# 生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{AppConfig.app_name}开始启动")
    worship()
    await init_create_table()
    app.state.redis = await RedisUtil.create_redis_pool()
    await RedisUtil.init_sys_dict(app.state.redis)
    await RedisUtil.init_sys_config(app.state.redis)
    await SysSchedulerUtil.init_system_scheduler()
    await QtrSchedulerUtil.init_qtr_scheduler()
    await startup_handler()
    logger.info(f"{AppConfig.app_name}启动成功")
    yield
    await SysSchedulerUtil.close_scheduler()
    await QtrSchedulerUtil.close_scheduler()
    await RedisUtil.close_redis_pool(app)


# 初始化FastAPI对象
app = FastAPI(
    title=AppConfig.app_name,
    description=f'{AppConfig.app_name}接口文档',
    version=AppConfig.app_version,
    lifespan=lifespan
)

# 挂载子应用
handle_sub_applications(app)
# 加载中间件处理方法
handle_middleware(app)
# 加载全局异常处理方法
handle_exception(app)


# 加载路由列表
controller_list = [
    {'router': loginController, 'tags': ['登录模块']},
    {'router': captchaController, 'tags': ['验证码模块']},
    {'router': userController, 'tags': ['系统管理-用户管理']},
    {'router': roleController, 'tags': ['系统管理-角色管理']},
    {'router': menuController, 'tags': ['系统管理-菜单管理']},
    {'router': deptController, 'tags': ['系统管理-部门管理']},
    {'router': postController, 'tags': ['系统管理-岗位管理']},
    {'router': dictController, 'tags': ['系统管理-字典管理']},
    {'router': configController, 'tags': ['系统管理-参数管理']},
    {'router': noticeController, 'tags': ['系统管理-通知公告管理']},
    {'router': logController, 'tags': ['系统管理-日志管理']},
    {'router': onlineController, 'tags': ['系统监控-在线用户']},
    {'router': jobController, 'tags': ['系统监控-定时任务']},
    {'router': serverController, 'tags': ['系统监控-菜单管理']},
    {'router': cacheController, 'tags': ['系统监控-缓存监控']},
    {'router': commonController, 'tags': ['通用模块']},
    {'router': projectController, 'tags': ['HRM-项目管理']},
    {'router': debugtalkController, 'tags': ['项目管理-DebugTalk']},
    {'router': moduleController, 'tags': ['HRM-模块管理']},
    {'router': envController, 'tags': ['HRM-环境管理']},
    {'router': caseController, 'tags': ['HRM-用例管理']},
    {'router': runnerController, 'tags': ['HRM-运行管理']},
    {'router': reportController, 'tags': ['HRM-报告管理']},
    {'router': hrmConfigController, 'tags': ['HRM-配置管理']},
    {'router': hrmCommonController, 'tags': ['HRM-common']},
    {'router': hrmApiController, 'tags': ['HRM-接口管理']},
    {'router': qtrJobController, 'tags': ['HRM-测试计划']},
    {'router': suiteController, 'tags': ['HRM-测试套件']},
    {'router': qtrServiceStatusController, 'tags': ['HRM-服务状态']},
    {'router': agentController, 'tags': ['QTR-Agent管理']},
    {'router': testController, 'tags': ['QTR-test管理']},
    {'router': forwardRulesController, 'tags': ['QTR-转发规则管理']},
    {'router': agentManagerController, 'tags': ['QTR-agent后台管理']},
]

for controller in controller_list:
    app.include_router(router=controller.get('router'), tags=controller.get('tags'))
