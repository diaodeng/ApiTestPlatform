import threading
from typing import Any

from config.database import SessionLocal
from modules.ticket.service.collaboration.ticket_message_sync_service import TicketMessageSyncService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from utils.log_util import logger


class TicketFeishuEventListenerService:
    """
    飞书官方 SDK 长连接事件监听服务，用于在无公网回调地址时接收工单群消息。
    """

    _thread: threading.Thread | None = None
    _client: Any = None
    _running = False
    _lock = threading.Lock()

    @classmethod
    def _handle_message_event(cls, event: Any) -> None:
        """
        处理长连接收到的飞书消息事件。
        :param event: lark_oapi 长连接回调事件对象
        :return: 无返回值
        """
        with SessionLocal() as db:
            try:
                result = TicketMessageSyncService.handle_feishu_sdk_message_event(db, event)
                logger.info(f"飞书长连接消息事件处理完成: result={result}")
            except Exception as exc:
                db.rollback()
                logger.exception(f"飞书长连接消息事件处理失败: error={exc}")

    @classmethod
    def _run_ws_client(
        cls,
        *,
        app_id: str,
        app_secret: str,
        encrypt_key: str,
        verification_token: str,
    ) -> None:
        """
        在线程内启动飞书 SDK 长连接客户端。
        :param app_id: 飞书应用 app_id
        :param app_secret: 飞书应用 app_secret
        :param encrypt_key: 事件加密密钥，未配置时为空
        :param verification_token: 事件校验 token，未配置时为空
        :return: 无返回值
        """
        try:
            import lark_oapi as lark

            event_handler = (
                lark.EventDispatcherHandler.builder(encrypt_key, verification_token)
                .register_p2_im_message_receive_v1(cls._handle_message_event)
                .build()
            )
            cls._client = lark.ws.Client(
                app_id,
                app_secret,
                event_handler=event_handler,
                log_level=lark.LogLevel.INFO,
            )
            logger.info("飞书长连接监听启动中: event=im.message.receive_v1")
            cls._client.start()
        except Exception as exc:
            logger.exception(f"飞书长连接监听异常退出: error={exc}")
        finally:
            with cls._lock:
                cls._running = False
                cls._client = None

    @classmethod
    def start_from_config(cls) -> dict[str, Any]:
        """
        从工单同步配置读取长连接开关并启动监听。
        :return: 启动结果摘要
        """
        with cls._lock:
            if cls._running:
                return {"skipped": True, "reason": "already_running"}

        with SessionLocal() as db:
            sync_config = TicketSyncConfigService.load_sync_config(db)
        message_config = sync_config.get("messageSync") if isinstance(sync_config.get("messageSync"), dict) else {}
        if not bool(message_config.get("enabled")) or not bool(message_config.get("feishuWsEnabled")):
            logger.info("飞书长连接监听未启动: 评论同步或长连接开关未启用")
            return {"skipped": True, "reason": "disabled"}

        feishu_auth = sync_config.get("feishuAuth") if isinstance(sync_config.get("feishuAuth"), dict) else {}
        group_config = sync_config.get("groupPush") if isinstance(sync_config.get("groupPush"), dict) else {}
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth({**feishu_auth, **group_config})
        if not app_id or not app_secret:
            logger.warning("飞书长连接监听未启动: 缺少 appId 或 appSecret")
            return {"skipped": True, "reason": "missing_feishu_app_config"}

        encrypt_key = str(message_config.get("feishuWsEncryptKey") or "").strip()
        verification_token = str(message_config.get("feishuWsVerificationToken") or "").strip()
        with cls._lock:
            cls._running = True
            cls._thread = threading.Thread(
                target=cls._run_ws_client,
                kwargs={
                    "app_id": app_id,
                    "app_secret": app_secret,
                    "encrypt_key": encrypt_key,
                    "verification_token": verification_token,
                },
                name="ticket-feishu-event-listener",
                daemon=True,
            )
            cls._thread.start()
        return {"skipped": False, "event": "im.message.receive_v1"}

    @classmethod
    def stop(cls) -> dict[str, Any]:
        """
        标记停止飞书长连接监听。
        :return: 停止结果摘要
        """
        with cls._lock:
            was_running = cls._running
            cls._running = False
        if was_running:
            logger.info("飞书长连接监听已标记停止: 当前 SDK 未提供显式 stop 接口，连接将在进程退出时释放")
        return {"skipped": not was_running}

