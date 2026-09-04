"""
工单附件临时下载链接服务：基于多维表格附件 file_token 实时换取临时下载链接。

设计要点（方案A）：
- 附件持久化只存 fileToken/name/size/type（见 FeishuBitableUtil.extract_attachment_tokens），
  不保存飞书 API 返回的临时 URL（约 24 小时过期，不可长期使用）。
- 用户查看附件时由本服务实时调用飞书素材接口换取临时下载链接；
  图片等直接渲染场景返回 302 跳转即可（由 controller 决定出参方式）。
- 临时链接做进程内短 TTL 缓存，减少高频查看时的飞书 API 调用。
"""
import time
from typing import Any

from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from utils.log_util import logger


class TicketAttachmentUrlService:
    """多维表格附件 file_token 换取临时下载链接。"""

    # 临时链接缓存秒数；飞书临时链接有效期为 24 小时，这里只缓存 30 分钟避免进程内过期链接被复用。
    CACHE_TTL_SECONDS = 30 * 60
    _cache: dict[str, tuple[float, str]] = {}

    @classmethod
    def resolve_bitable_runtime(cls, db) -> dict[str, Any]:
        """
        读取主动拉取运行时配置（appId/appSecret/appToken/tableId），
        附件换链与记录拉取使用同一套多维表格配置。
        :param db: 数据库会话。
        :return: 运行时配置字典。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        return TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )

    @classmethod
    def get_tmp_download_url(
        cls,
        *,
        config: dict[str, Any],
        file_token: str,
    ) -> str | None:
        """
        按附件 file_token 换取飞书临时下载链接（带进程内缓存）。

        :param config: 多维表格运行时配置（需包含 appId/appSecret）。
        :param file_token: 附件 file_token。
        :return: 临时下载链接；换取失败返回 None。
        """
        normalized_token = str(file_token or "").strip()
        if not normalized_token:
            return None
        cached = cls._cache.get(normalized_token)
        if cached and cached[0] > time.time():
            return cached[1]
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(config)
        if not app_id or not app_secret:
            logger.warning(f"附件临时链接换取跳过: 缺少飞书应用配置, file_token={normalized_token[:8]}***")
            return None
        try:
            token = TicketSyncNotifyService._get_tenant_access_token(app_id, app_secret)
            # 飞书云文档素材接口：drive/v1/medias/{file_token}/download 支持批量换取临时下载链接。
            response_data = TicketSyncNotifyService.request_feishu_json(
                method="GET",
                url=f"{TicketSyncNotifyService.FEISHU_BASE_URL}/drive/v1/medias/batch_get_tmp_download_url",
                tenant_access_token=token,
                params={"file_tokens": [normalized_token]},
            )
            data = response_data.get("data") if isinstance(response_data.get("data"), dict) else {}
            tmp_url = str(data.get("tmp_download_url") or "").strip()
            if not isinstance(data.get("tmp_download_url"), str):
                # 兼容返回结构为 {file_token: {"tmp_download_url": "..."}} 的批量形式。
                token_result = data.get(normalized_token)
                if isinstance(token_result, dict):
                    tmp_url = str(token_result.get("tmp_download_url") or "").strip()
            if not tmp_url:
                logger.warning(
                    f"附件临时链接换取失败: file_token={normalized_token[:8]}***, "
                    f"code={response_data.get('code')}, msg={response_data.get('msg')}"
                )
                return None
            cls._cache[normalized_token] = (time.time() + cls.CACHE_TTL_SECONDS, tmp_url)
            return tmp_url
        except Exception as exc:
            logger.warning(f"附件临时链接换取异常: file_token={normalized_token[:8]}***, error={exc}")
            return None

    @classmethod
    def collect_ticket_extra_attachments(cls, ticket_extra_data: Any) -> dict[str, list[dict[str, Any]]]:
        """
        从工单 extra_data 中提取附件元信息分组。

        :param ticket_extra_data: 工单 extra_data JSON。
        :return: {来源字段: [{fileToken,name,size,type}]}；无附件返回空字典。
        """
        if not isinstance(ticket_extra_data, dict):
            return {}
        raw = ticket_extra_data.get("bitable_attachments")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[dict[str, Any]]] = {}
        for field_name, items in raw.items():
            if not isinstance(items, list):
                continue
            normalized_items = [
                item for item in items if isinstance(item, dict) and str(item.get("fileToken") or "").strip()
            ]
            if normalized_items:
                result[str(field_name)] = normalized_items
        return result
