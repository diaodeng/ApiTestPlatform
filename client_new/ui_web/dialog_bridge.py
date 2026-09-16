import threading
import uuid
from typing import Any

from loguru import logger

from ui_web.event_bus import event_bus

# 前端应答等待超时（秒）：超时按“取消”处理，避免后台任务永久挂起。
_DIALOG_WAIT_TIMEOUT = 300.0


class WebDialogService:
    """
    面向后台任务的模态弹窗桥（替代原 Qt DialogService/DialogUtil）。

    POS 启动引擎等业务在执行过程中需要向用户弹确认框；pywebview 下后端
    无法直接弹系统对话框，这里改为：
    1. 通过 EventBus 推送 "ui_dialog" 事件给前端；
    2. 用 threading.Event 阻塞等待用户操作；
    3. 前端把结果经 Bridge.resolve_dialog(req_id, value) 回传后放行。

    语义与原 Qt 实现一致：
    - confirm: Yes/No，默认 No（超时/关窗视为 No）
    - choice: 取消=0 / 确定=1 / 切换后启动=2（超时视为 0）
    - error/success: 非阻塞提示，推送 toast 后立即返回
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pending: dict[str, tuple[threading.Event, Any]] = {}

    # ===== 前端应答入口（由 Bridge 转发） =====

    def resolve(self, req_id: str, value) -> bool:
        """
        前端用户操作完成后回传结果。

        :param req_id: 弹窗请求 id
        :param value: confirm 传 bool；choice 传 0/1/2
        :return: 是否成功匹配到等待中的请求
        """
        with self._lock:
            pending = self._pending.pop(req_id, None)
        if not pending:
            logger.debug(f"弹窗应答未匹配到等待请求 req_id={req_id}")
            return False

        event, holder = pending
        holder.value = value
        event.set()
        return True

    def cancel_all(self) -> None:
        """
        应用退出时放行所有未决弹窗（按取消处理），避免关闭阶段卡线程。
        """
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for event, holder in pending:
            holder.value = None if holder.kind == "choice" else False
            event.set()

    # ===== 供业务代码调用的弹窗实现 =====

    def confirm(self, title: str, msg: str) -> bool:
        """
        确认框：返回用户是否点击“确定”。默认/超时/退出均为 False。
        """
        value = self._ask("confirm", title, msg)
        return bool(value)

    def choice(self, title: str, msg: str) -> int:
        """
        三选项框：取消=0、确定=1、切换后启动=2。默认/超时为 0。
        """
        value = self._ask("choice", title, msg)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def error(self, msg: str) -> None:
        self._notify("error", msg)

    def success(self, msg: str) -> None:
        self._notify("success", msg)

    # ===== 内部实现 =====

    def _ask(self, kind: str, title: str, msg: str):
        req_id = uuid.uuid4().hex
        event = threading.Event()
        holder = _ResultHolder(kind=kind)

        with self._lock:
            self._pending[req_id] = (event, holder)

        event_bus.push(
            "ui_dialog",
            {"req_id": req_id, "kind": kind, "title": title, "message": msg},
        )

        if not event.wait(timeout=_DIALOG_WAIT_TIMEOUT):
            logger.warning(f"弹窗等待超时，按取消处理 kind={kind}, title={title}")
            with self._lock:
                self._pending.pop(req_id, None)
            return False if kind == "confirm" else 0

        return holder.value

    def _notify(self, level: str, msg: str) -> None:
        event_bus.push("ui_toast", {"level": level, "message": str(msg or "")})


class _ResultHolder:
    """
    弹窗应答结果的载体：Event 只能做同步，值需要挂在对象上回传。
    """

    def __init__(self, kind: str):
        self.kind = kind
        self.value = False if kind == "confirm" else 0
