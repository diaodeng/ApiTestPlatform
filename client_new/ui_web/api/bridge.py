from loguru import logger

from ui_web.api.about_api import AboutApi
from ui_web.api.agent_api import AgentApi
from ui_web.api.app_api import AppApi
from ui_web.api.log_api import LogApi
from ui_web.api.mitm_api import MitmApi
from ui_web.api.pos_api import PosApi
from ui_web.api.sqlite_api import SqliteApi
from ui_web.dialog_bridge import WebDialogService


class Bridge:
    """
    pywebview js_api 门面（协议层）。

    前端统一通过 window.pywebview.api.<method>(...) 调用这里的方法；
    Bridge 自身不承载业务，只做子 API 聚合与生命周期管理：
    - app：主题/插件/文件对话框/弹窗应答/退出（AppApi）
    - agent：Agent 连接与配置（AgentApi）
    - pos：POS 扫描/启停/维护（PosApi）
    - sqlite：SQLite 查询（SqliteApi）
    - mitm：mitmproxy 控制（MitmApi）
    - log：日志 tail（LogApi）
    - about：版本与更新（AboutApi）

    事件推送统一经 ui_web.event_bus.event_bus，事件名约定见各子 API 注释。
    """

    def __init__(self, window_holder):
        self.dialog_service = WebDialogService()
        self.app = AppApi(self.dialog_service, window_holder)
        self.agent = AgentApi()
        self.pos = PosApi()
        self.sqlite = SqliteApi()
        self.mitm = MitmApi()
        self.log = LogApi()
        self.about = AboutApi()
        # 顶层透传的高频方法（避免前端写 app.xxx 的层级差异，保持平铺易用）
        self.resolve_dialog = self.app.resolve_dialog
        self.choose_file = self.app.choose_file
        self.choose_dir = self.app.choose_dir
        self.quit_app = self.app.quit_app

    def shutdown(self):
        """
        应用退出时按依赖顺序停止各后台任务（mitm helper、Agent 连接、日志 tail、弹窗）。
        """
        logger.info("开始执行界面后端清理")
        for name, api in (
            ("mitm", self.mitm),
            ("agent", self.agent),
            ("log", self.log),
        ):
            shutdown = getattr(api, "shutdown", None) or getattr(api, "stop_tail", None)
            if shutdown is None:
                continue
            try:
                shutdown()
            except Exception as e:
                logger.exception(f"清理 {name} 失败: {e}")
        try:
            self.dialog_service.cancel_all()
        except Exception as e:
            logger.debug(f"放行未决弹窗失败: {e}")
        logger.info("界面后端清理完成")
