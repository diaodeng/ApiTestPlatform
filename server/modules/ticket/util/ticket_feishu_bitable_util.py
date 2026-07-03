"""
飞书多维表格工具类：富文本解析、人员字段提取、字段映射转换等纯数据转换函数。

所有方法均为 @staticmethod，无数据库或外部服务依赖。
从 TicketSyncService 中提取，供 sync_service、message_sync_service、config_service 等复用。
"""
import hashlib
import json
import re
from typing import Any

from modules.ticket.util.sync_util import SyncUtil


class FeishuBitableUtil:
    """飞书多维表格数据解析与转换工具。"""

    # ---- 目标字段名归一化 ----

    @staticmethod
    def normalize_pull_target_field(value: Any) -> str:
        """
        归一化主动拉取字段映射的目标字段名。

        :param value: 配置中的目标字段名。
        :return: 外部同步模型识别的规范字段名。
        """
        field_name = str(value or "").strip()
        alias_map = {
            "ticketModel": "ticketModle",
            "ticket_model": "ticketModle",
            "moduleName": "ticketModle",
            "module_name": "ticketModle",
            "projectName": "ticketVender",
            "project_name": "ticketVender",
            "merchantName": "ticketVender",
            "merchant_name": "ticketVender",
            "internalOwnerName": "internalOwner",
            "internal_owner_name": "internalOwner",
            "ticketAssigneeName": "ticketAssignee",
            "ticket_assignee_name": "ticketAssignee",
            "assigneeName": "ticketAssignee",
            "assignee_name": "ticketAssignee",
            "ticketAssigneeEmail": "ticketAssigneeEmail",
            "ticket_assignee_email": "ticketAssigneeEmail",
            "assigneeEmail": "ticketAssigneeEmail",
            "assignee_email": "ticketAssigneeEmail",
        }
        return alias_map.get(field_name, field_name)

    # ---- 邮箱提取与脱敏 ----

    @staticmethod
    def extract_email(value: Any) -> str:
        """
        从飞书多维表格字段值中提取邮箱，兼容人员字段、文本字段和数组字段。

        :param value: 多维表格字段值
        :return: 邮箱，未命中返回空字符串
        """
        if isinstance(value, list):
            for item in value:
                email = FeishuBitableUtil.extract_email(item)
                if email:
                    return email
            return ""
        if isinstance(value, dict):
            for key in (
                "email",
                "mail",
                "userEmail",
                "user_email",
                "workEmail",
                "work_email",
                "text",
                "value",
            ):
                email = FeishuBitableUtil.extract_email(value.get(key))
                if email:
                    return email
            return ""
        text = str(value or "").strip().lower()
        if "@" not in text:
            return ""
        matched = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        return matched.group(0).lower() if matched else ""

    @staticmethod
    def mask_email_for_log(email: str) -> str:
        """
        将邮箱脱敏后写入日志，避免排查同步链路时泄露完整邮箱。

        :param email: 原始邮箱
        :return: 脱敏后的邮箱
        """
        normalized_email = str(email or "").strip().lower()
        if "@" not in normalized_email:
            return normalized_email
        local_part, domain = normalized_email.split("@", 1)
        if len(local_part) <= 2:
            masked_local = f"{local_part[:1]}*"
        else:
            masked_local = f"{local_part[:2]}***{local_part[-1:]}"
        if "." in domain:
            domain_name, domain_suffix = domain.rsplit(".", 1)
            masked_domain = f"{domain_name[:1]}***.{domain_suffix}"
        else:
            masked_domain = f"{domain[:1]}***"
        return f"{masked_local}@{masked_domain}"

    @staticmethod
    def describe_field_value_for_log(value: Any) -> dict[str, Any]:
        """
        生成多维表格字段值的日志摘要，只记录类型、结构和是否像邮箱，不记录原始字段值。

        :param value: 多维表格字段值
        :return: 字段值摘要
        """
        if value is None:
            return {"type": "missing", "empty": True}
        if isinstance(value, list):
            return {
                "type": "list",
                "empty": len(value) == 0,
                "length": len(value),
                "itemTypes": sorted({type(item).__name__ for item in value}),
            }
        if isinstance(value, dict):
            return {
                "type": "dict",
                "empty": len(value) == 0,
                "keys": list(value.keys())[:20],
            }
        text = str(value or "").strip()
        return {
            "type": type(value).__name__,
            "empty": not bool(text),
            "length": len(text),
            "hasEmailPattern": "@" in text,
        }

    # ---- 富文本识别与归一化 ----

    @staticmethod
    def is_rich_text_segment(value: Any) -> bool:
        """
        判断字段值是否为飞书多维表格富文本片段。

        :param value: 多维表格字段中的单个值。
        :return: 是富文本片段返回 True，否则返回 False。
        """
        return isinstance(value, dict) and "text" in value and (
            "type" in value or "link" in value or "mention_user_id" in value
        )

    @staticmethod
    def is_rich_text_list(value: Any) -> bool:
        """
        判断字段值是否为飞书多维表格富文本片段数组。

        :param value: 多维表格字段值。
        :return: 是富文本片段数组返回 True，否则返回 False。
        """
        return (
            isinstance(value, list)
            and bool(value)
            and all(FeishuBitableUtil.is_rich_text_segment(item) for item in value)
        )

    @staticmethod
    def normalize_rich_text_segment(
        value: Any,
        *,
        join_separator: str = ",",
    ) -> str:
        """
        将飞书富文本片段归一化为原始文本，保留换行等排版字符。

        :param value: 单个富文本片段，通常包含 text/type/link 等字段。
        :param join_separator: 嵌套列表值的拼接分隔符。
        :return: 片段文本，空片段返回空字符串。
        """
        if not isinstance(value, dict):
            return str(value or "")
        mention_user_id = str(value.get("mention_user_id") or value.get("mentionUserId") or "").strip()
        raw_text = value.get("text")
        if raw_text is None:
            raw_text = value.get("name") or value.get("value") or value.get("title") or value.get("link")
        if isinstance(raw_text, str):
            if mention_user_id and raw_text and not raw_text.startswith("@"):
                return f"@{raw_text}"
            return raw_text
        normalized_text = FeishuBitableUtil.normalize_record_scalar(raw_text, join_separator=join_separator)
        text = str(normalized_text or "")
        if mention_user_id and text and not text.startswith("@"):
            return f"@{text}"
        return text

    @staticmethod
    def normalize_rich_text_segments_for_comment(value: Any) -> list[dict[str, Any]]:
        """
        将多维表格富文本片段转换为评论附件可保存的内部片段。

        :param value: 多维表格字段原始值。
        :return: text/mention 片段列表。
        """
        if not isinstance(value, list) or not FeishuBitableUtil.is_rich_text_list(value):
            return []
        segments: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            text = FeishuBitableUtil.normalize_rich_text_segment(item, join_separator="\n")
            if not text:
                continue
            mention_user_id = str(item.get("mention_user_id") or item.get("mentionUserId") or "").strip()
            if mention_user_id:
                segments.append(
                    {
                        "type": "mention",
                        "text": text,
                        "name": text[1:] if text.startswith("@") else text,
                        "openId": mention_user_id,
                        "userId": mention_user_id,
                    }
                )
            else:
                segments.append({"type": "text", "text": text})
        return segments

    # ---- 字段值归一化 ----

    @staticmethod
    def normalize_record_scalar(
        value: Any,
        *,
        join_separator: str = ",",
    ) -> Any:
        """
        将飞书多维表格字段值归一化为适合外部同步入参的标量。

        :param value: 多维表格原始字段值。
        :param join_separator: 列表字段拼接分隔符。
        :return: 归一化后的字段值。
        """
        if value is None:
            return None
        if isinstance(value, list):
            if FeishuBitableUtil.is_rich_text_list(value):
                return "".join(
                    FeishuBitableUtil.normalize_rich_text_segment(item, join_separator=join_separator)
                    for item in value
                )
            normalized_items: list[str] = []
            for item in value:
                normalized_item = FeishuBitableUtil.normalize_record_scalar(item, join_separator=join_separator)
                text = str(normalized_item or "").strip()
                if text and text not in normalized_items:
                    normalized_items.append(text)
            return join_separator.join(normalized_items)
        if isinstance(value, dict):
            if FeishuBitableUtil.is_rich_text_segment(value):
                return FeishuBitableUtil.normalize_rich_text_segment(value, join_separator=join_separator)
            for key in ("text", "name", "value", "email", "link", "title"):
                if key in value:
                    normalized_value = FeishuBitableUtil.normalize_record_scalar(
                        value.get(key),
                        join_separator=join_separator,
                    )
                    if normalized_value not in (None, ""):
                        return normalized_value
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, (int, float, bool)):
            return value
        text = str(value).strip()
        return text

    @staticmethod
    def normalize_record_datetime_text(value: Any) -> str:
        """
        将多维表格时间字段归一化为接口可消费的时间文本。

        :param value: 原始时间字段值。
        :return: `YYYY-MM-DD HH:MM:SS` 格式文本，失败时返回原始文本。
        """
        parsed = SyncUtil.parse_datetime_value(value)
        if parsed:
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        return str(value or "").strip()

    # ---- 人员字段提取 ----

    @staticmethod
    def extract_person_text(
        value: Any,
        *,
        preferred_keys: tuple[str, ...],
        join_separator: str = ",",
    ) -> str:
        """
        从飞书多维表格人员字段中提取指定文本。

        :param value: 多维表格原始字段值，支持人员对象、数组或普通文本。
        :param preferred_keys: 优先提取的字段键，例如 email/name/text。
        :param join_separator: 多个人员值的拼接分隔符。
        :return: 去重后的文本，未提取到时返回空字符串。
        """
        if value is None:
            return ""
        if isinstance(value, list):
            result_items: list[str] = []
            for item in value:
                item_text = FeishuBitableUtil.extract_person_text(
                    item,
                    preferred_keys=preferred_keys,
                    join_separator=join_separator,
                )
                if item_text and item_text not in result_items:
                    result_items.append(item_text)
            return join_separator.join(result_items)
        if isinstance(value, dict):
            for key in preferred_keys:
                if key not in value:
                    continue
                item_text = FeishuBitableUtil.extract_person_text(
                    value.get(key),
                    preferred_keys=preferred_keys,
                    join_separator=join_separator,
                )
                if item_text:
                    return item_text
            return ""
        return str(value or "").strip()

    @staticmethod
    def extract_person_email(value: Any, *, join_separator: str = ",") -> str:
        """
        从飞书多维表格人员字段中提取邮箱。

        :param value: 多维表格原始字段值。
        :param join_separator: 多个邮箱的拼接分隔符。
        :return: 邮箱文本，未提取到时返回空字符串。
        """
        return FeishuBitableUtil.extract_person_text(
            value,
            preferred_keys=("email", "mail"),
            join_separator=join_separator,
        )

    @staticmethod
    def extract_person_name(value: Any, *, join_separator: str = ",") -> str:
        """
        从飞书多维表格人员字段中提取人员名称。

        :param value: 多维表格原始字段值。
        :param join_separator: 多个人员名的拼接分隔符。
        :return: 人员名称文本，未提取到时返回空字符串。
        """
        return FeishuBitableUtil.extract_person_text(
            value,
            preferred_keys=("name", "text", "value", "en_name", "nickname"),
            join_separator=join_separator,
        )

    # ---- 记录 URL 与快照 ----

    @staticmethod
    def build_record_url(
        config: dict[str, Any],
        *,
        record_id: str,
        record_url: str | None = None,
    ) -> str:
        """
        根据多维表格配置构建记录详情 URL。

        :param config: 多维配置。
        :param record_id: 记录ID。
        :param record_url: 飞书接口直接返回的记录详情 URL。
        :return: 记录详情地址。
        """
        from modules.ticket.service.ticket_sync_notify_service import TicketSyncNotifyService
        return TicketSyncNotifyService.get_bitable_record_url(config, record_id, record_url=record_url)

    # ---- 字段映射转换 ----

    @staticmethod
    def build_pull_field_mapping_from_record(
        fields: dict[str, Any],
        *,
        field_mappings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        根据多维表格字段映射生成外部同步字段字典。

        :param fields: 多维表格 fields。
        :param field_mappings: 可视化或任务参数配置的字段映射。
        :return: 同步字段字典。
        """
        payload: dict[str, Any] = {}
        field_segments: dict[str, list[dict[str, Any]]] = {}
        for mapping in field_mappings:
            source_field = str(mapping.get("sourceField") or "").strip()
            target_field = FeishuBitableUtil.normalize_pull_target_field(mapping.get("targetField"))
            if not source_field or not target_field:
                continue
            raw_value = fields.get(source_field)
            join_separator = str(mapping.get("joinSeparator") or ",").strip() or ","
            if target_field in {
                "reporterEmail",
                "currentAssigneeEmail",
                "ticketAssigneeEmail",
                "internalOwnerEmail",
            }:
                normalized_value = FeishuBitableUtil.extract_person_email(
                    raw_value, join_separator=join_separator
                )
            elif target_field in {
                "reporterName",
                "currentAssigneeName",
                "ticketAssignee",
                "internalOwner",
            }:
                normalized_value = (
                    FeishuBitableUtil.extract_person_name(raw_value, join_separator=join_separator)
                    or FeishuBitableUtil.normalize_record_scalar(raw_value, join_separator=join_separator)
                )
            else:
                normalized_value = FeishuBitableUtil.normalize_record_scalar(
                    raw_value,
                    join_separator=join_separator,
                )
            if normalized_value in (None, "", []):
                default_value = mapping.get("defaultValue")
                normalized_value = default_value if default_value not in ("", None) else None
            if normalized_value in (None, "", []):
                continue
            if target_field in {"createTime"}:
                payload[target_field] = FeishuBitableUtil.normalize_record_datetime_text(normalized_value)
            else:
                payload[target_field] = normalized_value
            if target_field == "stepReason":
                segments = FeishuBitableUtil.normalize_rich_text_segments_for_comment(raw_value)
                if segments:
                    field_segments[target_field] = segments
                    field_segments[source_field] = segments
        if field_segments:
            extra_data = payload.get("extraData") if isinstance(payload.get("extraData"), dict) else {}
            extra_data = dict(extra_data or {})
            extra_data["_bitable_field_segments"] = field_segments
            payload["extraData"] = extra_data
        return payload

    @staticmethod
    def build_pull_snapshot_hash(
        *,
        source_payload: dict[str, Any],
        field_mapping_snapshot: dict[str, str],
    ) -> str:
        """
        计算主动拉取记录快照哈希，用于判断记录内容是否变化。

        :param source_payload: 归一化后的同步负载。
        :param field_mapping_snapshot: 字段映射快照。
        :return: SHA256 哈希。
        """
        raw = {
            "payload": source_payload,
            "mapping": field_mapping_snapshot,
        }
        return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
