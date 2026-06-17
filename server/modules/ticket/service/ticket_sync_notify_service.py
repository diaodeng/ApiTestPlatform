from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy import or_, false
from sqlalchemy.orm import Session

from module_admin.dao.ai_provider_dao import AiProviderDao
from module_admin.entity.do.user_do import SysUser
from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.do.push_do import PushTarget
from module_hrm.entity.vo.push_vo import PushModel
from module_hrm.utils.parser import parse_string
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.ticket_light_ai_service import TicketLightAiService
from utils.log_util import logger
from utils.message_util import MessageHandler


class TicketSyncNotifyService:
    """
    工单同步通知服务，负责人维度催办提醒与群消息推送。
    """

    FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
    _tenant_token_cache: dict[str, dict[str, Any]] = {}
    _email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    DEFAULT_PERSON_TEMPLATE = (
        "【工单催办提醒】\n"
        # "负责人：${person_name}\n"
        "阈值：${threshold_minutes} 分钟\n"
        "超时条数：${overdue_count}\n"
        "统计时间：${now_time}\n\n"
        "${rows_markdown}"
    )
    DEFAULT_PERSON_ROWS_MARKDOWN_TEMPLATE = (
        "${index}. [${created_at}] 工单号：${ticket_no}${detail_link}"
    )
    DEFAULT_GROUP_TEMPLATE = (
        "【工单同步通知】\n"
        "工单：${ticket_no}\n"
        "标题：${ticket_title}\n"
        "项目：${project_name}\n"
        "模块：${module_name}\n"
        "状态：${ticket_status}\n"
        "当前处理人：${assignee_name}\n"
        "来源：${sync_source_system}\n"
        "修订：${sync_revision}\n"
        "链接：${ticket_url}\n"
        "说明：${description}"
    )
    DEFAULT_SUMMARY_TEMPLATE = (
        "【工单汇总统计】\n"
        "统计范围：${start_time} ~ ${end_time}\n"
        "统计字段：${time_field}\n"
        "工单总数：${total_count}\n\n"
        "状态统计：\n${status_summary}\n\n"
        "分类统计：\n${category_summary}\n\n"
        "优先级统计：\n${priority_summary}\n\n"
        "AI解读：\n${ai_summary}\n\n"
        "生成时间：${now_time}"
    )
    SEND_MODE_PUSH_CONFIG = "push_config"
    SEND_MODE_FEISHU_APP = "feishu_app"
    SEND_MODE_HYBRID = "hybrid"
    PERSON_DATA_SOURCE_BITABLE = "bitable"
    PERSON_DATA_SOURCE_LOCAL = "local"
    SUMMARY_DATA_SOURCE_BITABLE = "bitable"
    SUMMARY_DATA_SOURCE_LOCAL = "local"

    @classmethod
    def _safe_int(cls, value: Any) -> int | None:
        """
        安全转换整数。

        :param value: 原始值。
        :return: 整数或 None。
        """
        try:
            if value in (None, ""):
                return None
            return int(value)
        except Exception:
            return None

    @classmethod
    def _normalize_push_ids(cls, value: Any) -> list[int]:
        """
        归一化推送配置ID数组。

        :param value: 原始值，可为列表或逗号分隔字符串。
        :return: 去重后的推送ID列表。
        """
        if isinstance(value, str):
            source_list = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            source_list = value
        else:
            source_list = []
        result: list[int] = []
        for item in source_list:
            parsed = cls._safe_int(item)
            if parsed and parsed not in result:
                result.append(parsed)
        return result

    @classmethod
    def _normalize_email(cls, value: Any) -> str:
        """
        归一化邮箱文本。

        :param value: 原始邮箱值。
        :return: 小写邮箱字符串。
        """
        return str(value or "").strip().lower()

    @classmethod
    def _is_valid_email(cls, value: Any) -> bool:
        """
        判断文本是否是合法邮箱格式。

        :param value: 原始文本。
        :return: 是否满足邮箱格式。
        """
        normalized = cls._normalize_email(value)
        if not normalized:
            return False
        return bool(cls._email_pattern.match(normalized))

    @classmethod
    def _normalize_send_mode(cls, value: Any) -> str:
        """
        归一化通知发送模式。

        :param value: 原始发送模式文本。
        :return: 归一化后的发送模式。
        """
        mode = str(value or "").strip().lower()
        if mode in {cls.SEND_MODE_PUSH_CONFIG, cls.SEND_MODE_FEISHU_APP, cls.SEND_MODE_HYBRID}:
            return mode
        return cls.SEND_MODE_PUSH_CONFIG

    @classmethod
    def _normalize_chat_ids(cls, value: Any) -> list[str]:
        """
        归一化群 chat_id 列表。

        :param value: 原始 chat_id 列表或逗号分隔文本。
        :return: 去重后的 chat_id 列表。
        """
        if isinstance(value, str):
            source_list = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            source_list = value
        else:
            source_list = []
        result: list[str] = []
        for item in source_list:
            chat_id = str(item or "").strip()
            if chat_id and chat_id not in result:
                result.append(chat_id)
        return result

    @classmethod
    def _normalize_priority(cls, value: Any) -> str:
        """
        归一化优先级文本。

        :param value: 原始优先级。
        :return: 规范化优先级（P1/P2/P3/P4）。
        """
        raw_text = str(value or "").strip()
        text = raw_text.upper().replace(" ", "")
        if not text:
            return ""
        if not text.startswith("P") and text.isdigit():
            text = f"P{text}"
        if text in {"P0", "P1", "P2", "P3", "P4"}:
            return text
        priority_match = re.search(r"P\s*([0-4])", raw_text, flags=re.IGNORECASE)
        if priority_match:
            return f"P{priority_match.group(1)}"
        number_match = re.search(r"([0-4])", raw_text)
        if number_match:
            return f"P{number_match.group(1)}"
        normalized_text = text.replace("-", "").replace("_", "").replace("/", "").replace("：", "").replace(":", "")
        if normalized_text in {"CRITICAL", "URGENT", "SEV1", "S1", "LEVELA"}:
            return "P1"
        if normalized_text in {"HIGH", "SEV2", "S2", "LEVELB"}:
            return "P2"
        if normalized_text in {"MEDIUM", "NORMAL", "SEV3", "S3", "LEVELC"}:
            return "P3"
        if normalized_text in {"LOW", "SEV4", "S4", "LEVELD"}:
            return "P4"
        if any(keyword in raw_text for keyword in ["紧急", "特急", "最高"]):
            return "P1"
        if any(keyword in raw_text for keyword in ["高优", "高"]):
            return "P2"
        if any(keyword in raw_text for keyword in ["中优", "中", "一般", "普通"]):
            return "P3"
        if any(keyword in raw_text for keyword in ["低优", "低"]):
            return "P4"
        return text

    @classmethod
    def _resolve_priority_from_ticket(cls, ticket: Ticket) -> str:
        """
        解析工单优先级（优先取 customer_priority，再取 internal_priority）。

        :param ticket: 工单对象。
        :return: 优先级文本。
        """
        customer_priority = cls._normalize_priority(getattr(ticket, "customer_priority", None))
        if customer_priority:
            return customer_priority
        return cls._normalize_priority(getattr(ticket, "internal_priority", None))

    @classmethod
    def _resolve_feishu_auth(cls, config: dict[str, Any]) -> tuple[str, str]:
        """
        解析飞书应用凭证。

        :param config: 通知配置。
        :return: (app_id, app_secret)。
        """
        app_id = (
            str(config.get("appId") or "").strip()
            or str(config.get("feishuAppId") or "").strip()
            or str(config.get("authAppId") or "").strip()
        )
        app_secret = (
            str(config.get("appSecret") or "").strip()
            or str(config.get("feishuAppSecret") or "").strip()
            or str(config.get("authAppSecret") or "").strip()
        )
        return app_id, app_secret

    @classmethod
    def _request_feishu_json(
        cls,
        *,
        method: str,
        url: str,
        tenant_access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_sec: int = 30,
    ) -> dict[str, Any]:
        """
        调用飞书开放平台接口并返回 JSON。

        :param method: HTTP 方法。
        :param url: 完整请求地址。
        :param tenant_access_token: 飞书租户访问令牌，可为空。
        :param params: URL 查询参数。
        :param json_body: JSON 请求体。
        :param timeout_sec: 超时时间（秒）。
        :return: 响应 JSON 字典。
        """
        try:
            headers = {"Content-Type": "application/json; charset=utf-8"}
            if tenant_access_token:
                headers["Authorization"] = f"Bearer {tenant_access_token}"
            response = requests.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=(10, timeout_sec),
            )
            if response.status_code != 200:
                logger.info(
                    "Request failed with status code: "
                    f"{response.status_code}, {url} - {json.dumps(response.json(), ensure_ascii=False)}"
                )
                response.raise_for_status()
            data = response.json()
            if int(data.get("code") or 0) != 0:
                raise RuntimeError(f"飞书接口调用失败: {data.get('msg') or data}")
            return data
        except Exception as e:
            raise RuntimeError(f"飞书接口调用失败:{e}  {url}") from e

    @classmethod
    def _get_tenant_access_token(cls, app_id: str, app_secret: str) -> str:
        """
        获取飞书租户访问令牌并做内存缓存。

        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :return: tenant_access_token。
        """
        normalized_app_id = str(app_id or "").strip()
        normalized_secret = str(app_secret or "").strip()
        if not normalized_app_id or not normalized_secret:
            raise ValueError("飞书应用 app_id 或 app_secret 未配置")

        cache_item = cls._tenant_token_cache.get(normalized_app_id)
        now = datetime.now()
        if cache_item and isinstance(cache_item, dict):
            expire_at = cache_item.get("expire_at")
            cached_token = str(cache_item.get("token") or "").strip()
            if isinstance(expire_at, datetime) and expire_at > now and cached_token:
                return cached_token

        url = f"{cls.FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        response_data = cls._request_feishu_json(
            method="POST",
            url=url,
            json_body={
                "app_id": normalized_app_id,
                "app_secret": normalized_secret,
            },
        )
        token = str(response_data.get("tenant_access_token") or "").strip()
        expire = int(response_data.get("expire") or 7200)
        if not token:
            raise RuntimeError("飞书 tenant_access_token 为空")
        cls._tenant_token_cache[normalized_app_id] = {
            "token": token,
            "expire_at": now + timedelta(seconds=max(expire - 120, 60)),
        }
        return token

    @classmethod
    def _send_feishu_text_messages(
        cls,
        *,
        app_id: str,
        app_secret: str,
        receive_id_type: str,
        receive_ids: list[str],
        content: str,
        mention_open_ids: list[str] | None = None,
    ) -> int:
        """
        通过飞书应用身份发送文本消息。

        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :param receive_id_type: 接收ID类型（chat_id/email）。
        :param receive_ids: 接收ID列表。
        :param content: 消息正文。
        :param mention_open_ids: 需要在消息中 @ 的 open_id 列表，仅 chat_id 场景生效。
        :return: 发送成功条数。
        """
        normalized_ids = [str(item or "").strip() for item in receive_ids if str(item or "").strip()]
        if not normalized_ids:
            return 0
        mention_text = ""
        message_text = str(content or "").strip()
        if receive_id_type == "chat_id" and isinstance(mention_open_ids, list) and "<at user_id=" not in message_text:
            mention_text = cls._build_feishu_at_tags(mention_open_ids)
        if mention_text:
            message_text = f"{mention_text}\n{message_text}" if message_text else mention_text
        token = cls._get_tenant_access_token(app_id, app_secret)
        sent_count = 0
        for receive_id in normalized_ids:
            try:
                url = f"{cls.FEISHU_BASE_URL}/im/v1/messages"
                cls._request_feishu_json(
                    method="POST",
                    url=url,
                    tenant_access_token=token,
                    params={"receive_id_type": receive_id_type},
                    json_body={
                        "receive_id": receive_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": message_text}, ensure_ascii=False),
                    },
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    f"飞书应用消息发送失败: receive_id_type={receive_id_type}, receive_id={receive_id}, error={exc}"
                )
        return sent_count

    @classmethod
    def _resolve_group_route_targets(
        cls,
        *,
        group_config: dict[str, Any],
        ticket_priority: str,
        override_push_ids: list[int] | None = None,
        override_chat_ids: list[str] | None = None,
    ) -> tuple[list[int], list[str], dict[str, Any]]:
        """
        按优先级解析群推送目标（推送配置ID/群chat_id）。

        :param group_config: 群推送配置。
        :param ticket_priority: 当前工单优先级。
        :param override_push_ids: 覆盖 pushIds。
        :param override_chat_ids: 覆盖 chatIds。
        :return: (push_ids, chat_ids, 路由命中信息)。
        """
        base_push_ids = cls._normalize_push_ids(group_config.get("pushIds"))
        base_chat_ids = cls._normalize_chat_ids(group_config.get("appChatIds"))
        if override_push_ids is not None:
            base_push_ids = cls._normalize_push_ids(override_push_ids)
        if override_chat_ids is not None:
            base_chat_ids = cls._normalize_chat_ids(override_chat_ids)

        routes = group_config.get("priorityRoutes") if isinstance(group_config.get("priorityRoutes"), list) else []
        normalized_priority = cls._normalize_priority(ticket_priority)
        route_hit: dict[str, Any] | None = None
        for route in routes:
            if not isinstance(route, dict):
                continue
            priorities = route.get("priorities")
            if isinstance(priorities, str):
                candidate_priorities = [cls._normalize_priority(item) for item in priorities.split(",")]
            elif isinstance(priorities, list):
                candidate_priorities = [cls._normalize_priority(item) for item in priorities]
            else:
                candidate_priorities = []
            candidate_priorities = [item for item in candidate_priorities if item]
            if normalized_priority and normalized_priority not in candidate_priorities:
                continue
            route_push_ids = cls._normalize_push_ids(route.get("pushIds"))
            route_chat_ids = cls._normalize_chat_ids(route.get("chatIds") or route.get("appChatIds"))
            if route_push_ids:
                base_push_ids = route_push_ids
            if route_chat_ids:
                base_chat_ids = route_chat_ids
            route_hit = {
                "priorities": candidate_priorities,
                "pushIds": route_push_ids,
                "chatIds": route_chat_ids,
            }
            break
        return base_push_ids, base_chat_ids, {"matchedPriority": normalized_priority or None, "matchedRoute": route_hit}

    @classmethod
    def _parse_datetime_value(cls, value: Any) -> datetime | None:
        """
        解析多种格式的时间值。

        :param value: 原始时间值。
        :return: datetime，解析失败返回 None。
        """
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000.0
            try:
                return datetime.fromtimestamp(timestamp)
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            pass
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue
        return None

    @classmethod
    def _extract_person_names(cls, value: Any) -> list[str]:
        """
        从多维表格人员字段中提取姓名列表。

        :param value: 字段值，可能是字符串、字典、列表。
        :return: 去重后的姓名列表。
        """
        if value is None:
            return []
        source_list: list[Any]
        if isinstance(value, list):
            source_list = value
        else:
            source_list = [value]

        names: list[str] = []
        for item in source_list:
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                name = str(item.get("email") or item.get("text") or item.get("value") or "").strip()
            else:
                name = str(item or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    @classmethod
    def _extract_record_time(cls, record: dict[str, Any], time_field: str) -> datetime | None:
        """
        从记录中提取时间字段。

        :param record: 飞书多维表格记录。
        :param time_field: 时间字段名。
        :return: 记录时间。
        """
        fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
        if time_field:
            field_value = fields.get(time_field)
            if isinstance(field_value, list) and field_value:
                for item in field_value:
                    parsed = cls._parse_datetime_value(item)
                    if parsed:
                        return parsed
            parsed = cls._parse_datetime_value(field_value)
            if parsed:
                return parsed

        for fallback_key in ("created_time", "createdTime", "created_at", "createdAt"):
            parsed = cls._parse_datetime_value(record.get(fallback_key))
            if parsed:
                return parsed
        return None

    @classmethod
    def _resolve_sys_user_by_name(cls, db: Session, person_name: str):
        """
        根据姓名在系统用户中匹配账号。

        :param db: 数据库会话。
        :param person_name: 人员姓名。
        :return: 系统用户对象或 None。
        """
        normalized_name = str(person_name or "").strip()
        if not normalized_name:
            return None
        return (
            db.query(SysUser)
            .filter(
                SysUser.del_flag == "0",
                SysUser.status == "0",
                or_(
                    SysUser.user_name == normalized_name,
                    SysUser.nick_name == normalized_name,
                    SysUser.email == normalized_name,
                ),
            )
            .first()
        )

    @classmethod
    def _resolve_target_user(cls, db: Session, user_id: int | None, email: str | None):
        """
        根据用户ID或邮箱解析系统用户。

        :param db: 数据库会话。
        :param user_id: 用户ID。
        :param email: 用户邮箱。
        :return: 系统用户对象或 None。
        """
        if user_id:
            user = (
                db.query(SysUser)
                .filter(SysUser.user_id == user_id, SysUser.del_flag == "0", SysUser.status == "0")
                .first()
            )
            if user:
                return user
        normalized_email = cls._normalize_email(email)
        if normalized_email:
            return (
                db.query(SysUser)
                .filter(
                    SysUser.email == normalized_email,
                    SysUser.del_flag == "0",
                    SysUser.status == "0",
                )
                .first()
            )
        return None

    @classmethod
    def _extract_email_from_payload(cls, payload: Any, candidate_keys: list[str]) -> str:
        """
        从载荷中按候选键提取邮箱。

        :param payload: 载荷对象，支持字典。
        :param candidate_keys: 候选字段名列表。
        :return: 命中的邮箱；未命中返回空字符串。
        """
        if not isinstance(payload, dict):
            return ""
        for key in candidate_keys:
            if key not in payload:
                continue
            value = payload.get(key)
            if isinstance(value, dict):
                value = value.get("email") or value.get("mail") or value.get("value")
            elif isinstance(value, list):
                value = value[0] if value else ""
                if isinstance(value, dict):
                    value = value.get("email") or value.get("mail") or value.get("value")
            normalized_email = cls._normalize_email(value)
            if cls._is_valid_email(normalized_email):
                return normalized_email
        return ""

    @classmethod
    def _resolve_ticket_person_email(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        person_role: str,
        person_name: str,
    ) -> str:
        """
        解析工单人员邮箱，优先使用工单原始载荷邮箱，其次按姓名查系统用户邮箱。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param person_role: 人员角色，支持 reporter/first_line/assignee/internal_owner。
        :param person_name: 人员名称。
        :return: 归一化邮箱，未命中返回空字符串。
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        raw_payload = extra_data.get("raw_payload") if isinstance(extra_data.get("raw_payload"), dict) else {}
        external_mapping = (
            extra_data.get("external_field_mapping")
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        role = str(person_role or "").strip().lower()
        candidate_keys: list[str]
        if role in {"reporter", "first_line", "first_line_assignee"}:
            candidate_keys = [
                "reporterEmail",
                "reporter_email",
                "firstLineAssigneeEmail",
                "first_line_assignee_email",
                "reporterMail",
                "reporter_mail",
                "reporterName",
                "reporter_name",
                "firstLineAssigneeName",
                "first_line_assignee_name",
                "reporter",
            ]
        elif role in {"internal_owner", "internalOwner"}:
            candidate_keys = [
                "internalOwnerEmail",
                "internal_owner_email",
                "internalOwnerName",
                "internal_owner_name",
                "internalOwner",
                "internal_owner",
            ]
        else:
            candidate_keys = [
                "currentAssigneeEmail",
                "current_assignee_email",
                "ticketAssigneeEmail",
                "ticket_assignee_email",
                "assigneeEmail",
                "assignee_email",
                "currentAssigneeName",
                "current_assignee_name",
                "ticketAssignee",
                "ticket_assignee",
                "currentAssignee",
                "current_assignee",
            ]
        direct_email = cls._extract_email_from_payload(raw_payload, candidate_keys)
        if not direct_email:
            direct_email = cls._extract_email_from_payload(external_mapping, candidate_keys)
        if direct_email:
            return direct_email
        user = cls._resolve_sys_user_by_name(db, person_name)
        return cls._normalize_email(getattr(user, "email", "")) if user else ""

    @classmethod
    def _resolve_group_mention_open_ids(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        app_id: str,
        app_secret: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        解析工单提单人与当前处理人的飞书 open_id 列表。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :return: (open_id 列表, 解析明细列表)。
        """
        if not app_id or not app_secret:
            return [], []
        mention_candidates: list[dict[str, Any]] = []
        reporter_name = str(ticket.reporter_name or '').strip()
        if reporter_name:
            mention_candidates.append({'role': 'reporter', 'name': reporter_name})
        first_line_name = str(getattr(ticket, "first_line_assignee_name", "") or "").strip()
        if first_line_name and first_line_name != reporter_name:
            mention_candidates.append({'role': 'first_line', 'name': first_line_name})
        assignee_name = str(ticket.current_assignee_name or '').strip()
        if assignee_name:
            mention_candidates.append({'role': 'assignee', 'name': assignee_name})
        internal_owner_name = str(getattr(ticket, "internal_owner_name", "") or "").strip()
        if internal_owner_name:
            mention_candidates.append({'role': 'internal_owner', 'name': internal_owner_name})
        if not mention_candidates:
            return [], []

        open_ids: list[str] = []
        detail_rows: list[dict[str, Any]] = []
        feishu_user_cache: dict[str, dict[str, Any] | None] = {}
        for candidate in mention_candidates:
            role = str(candidate.get('role') or '').strip()
            name = str(candidate.get('name') or '').strip()
            email = cls._resolve_ticket_person_email(
                db,
                ticket=ticket,
                person_role=role,
                person_name=name,
            )
            open_id = ''
            feishu_user = None
            if email:
                if email not in feishu_user_cache:
                    feishu_user_cache[email] = cls.query_feishu_user_by_email(
                        app_id=app_id,
                        app_secret=app_secret,
                        email=email,
                    )
                feishu_user = feishu_user_cache.get(email) if isinstance(feishu_user_cache.get(email), dict) else None
                open_id = str((feishu_user or {}).get('openId') or '').strip()
                if open_id and open_id not in open_ids:
                    open_ids.append(open_id)
            detail_rows.append(
                {
                    'role': role,
                    'name': name or None,
                    'email': email or None,
                    'openId': open_id or None,
                }
            )
        return open_ids, detail_rows

    @classmethod
    def _build_group_mention_template_variables(cls, mention_targets: list[dict[str, Any]]) -> dict[str, Any]:
        """
        构建模板可直接引用的飞书 @ 变量。

        :param mention_targets: 已解析出的 @ 人员信息。
        :return: mention 相关模板变量。
        """
        mention_open_ids: list[str] = []
        reporter_open_id = ''
        first_line_open_id = ''
        assignee_open_id = ''
        internal_owner_open_id = ''
        for item in mention_targets or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get('role') or '').strip().lower()
            open_id = str(item.get('openId') or '').strip()
            if not open_id:
                continue
            if open_id not in mention_open_ids:
                mention_open_ids.append(open_id)
            if role == 'reporter' and not reporter_open_id:
                reporter_open_id = open_id
            elif role == 'first_line' and not first_line_open_id:
                first_line_open_id = open_id
            elif role == 'assignee' and not assignee_open_id:
                assignee_open_id = open_id
            elif role == 'internal_owner' and not internal_owner_open_id:
                internal_owner_open_id = open_id
        if not first_line_open_id:
            first_line_open_id = reporter_open_id
        reporter_at = cls._build_feishu_at_tags([reporter_open_id]) if reporter_open_id else ''
        first_line_at = cls._build_feishu_at_tags([first_line_open_id]) if first_line_open_id else ''
        assignee_at = cls._build_feishu_at_tags([assignee_open_id]) if assignee_open_id else ''
        internal_owner_at = cls._build_feishu_at_tags([internal_owner_open_id]) if internal_owner_open_id else ''
        mention_at = cls._build_feishu_at_tags(mention_open_ids)
        return {
            'report_at': reporter_at,
            'reporter_at': reporter_at,
            'first_line_at': first_line_at,
            'first_line_assignee_at': first_line_at,
            'assignee_at': assignee_at,
            'internal_owner_at': internal_owner_at,
            'mention_at': mention_at,
            'mention_all_at': mention_at,
            'mention_open_ids': mention_open_ids,
            'mention_targets': mention_targets,
        }
    @classmethod
    def _build_feishu_at_tags(cls, open_ids: list[str]) -> str:
        """
        构建飞书文本消息中的 @ 标签文本。

        :param open_ids: 飞书 open_id 列表。
        :return: `<at user_id=\"...\"></at>` 拼接文本。
        """
        unique_ids: list[str] = []
        for open_id in open_ids:
            normalized_open_id = str(open_id or "").strip()
            if normalized_open_id and normalized_open_id not in unique_ids:
                unique_ids.append(normalized_open_id)
        if not unique_ids:
            return ""
        return " ".join([f"<at user_id=\"{open_id}\"></at>" for open_id in unique_ids])

    @classmethod
    def query_feishu_user_by_email(cls, *, app_id: str, app_secret: str, email: str) -> dict[str, Any] | None:
        """
        根据邮箱查询飞书用户信息。

        :param app_id: 飞书应用 app_id。
        :param app_secret: 飞书应用 app_secret。
        :param email: 邮箱地址。
        :return: 飞书用户信息，失败返回 None。
        """
        normalized_email = cls._normalize_email(email)
        if not normalized_email:
            return None
        try:
            token = cls._get_tenant_access_token(app_id, app_secret)
            batch_url = f"{cls.FEISHU_BASE_URL}/contact/v3/users/batch_get_id"
            batch_data = cls._request_feishu_json(
                method="POST",
                url=batch_url,
                tenant_access_token=token,
                params={"user_id_type": "open_id"},
                json_body={"emails": [normalized_email]},
            ).get("data") or {}
            user_list = batch_data.get("user_list") if isinstance(batch_data.get("user_list"), list) else []
            if not user_list:
                return {"email": normalized_email}
            first_user = user_list[0] if isinstance(user_list[0], dict) else {}
            open_id = str(first_user.get("user_id") or first_user.get("open_id") or "").strip()
            if not open_id:
                return {"email": normalized_email}
            user_detail_url = f"{cls.FEISHU_BASE_URL}/contact/v3/users/{open_id}"
            user_detail_data = cls._request_feishu_json(
                method="GET",
                url=user_detail_url,
                tenant_access_token=token,
                params={"user_id_type": "open_id"},
            ).get("data") or {}
            user_payload = user_detail_data.get("user") if isinstance(user_detail_data.get("user"), dict) else {}
            return {
                "openId": open_id,
                "name": str(user_payload.get("name") or first_user.get("name") or "").strip(),
                "email": str(user_payload.get("email") or normalized_email).strip(),
            }
        except Exception as exc:
            logger.warning(f"飞书用户查询失败，email={normalized_email}, error={exc}")
            return None

    @classmethod
    def get_bitable_record_url(cls, config: dict[str, Any], record_id:str) -> str:
        app_id, app_secret = cls._resolve_feishu_auth(config)
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        view_id = str(config.get("viewId") or "").strip()
        return f"https://feishu.cn/base/{app_token}?table={table_id}&view={view_id}&record={record_id}"

    @classmethod
    def _normalize_bitable_filter_formula(cls, value: Any) -> dict:
        """
        归一化飞书多维表格过滤公式。

        :param value: 原始过滤公式，支持普通公式文本或 JSON 字符串包裹的公式文本。
        :return: 可直接传给飞书 records 接口 filter 参数的公式文本。
        """
        filter_formula = str(value or "").strip()
        if not filter_formula:
            return {}
        try:
            parsed = json.loads(filter_formula)
            return parsed
        except Exception as e:
            logger.warning(f"参数错误：{filter_formula}, 错误：{e}")
            raise ValueError('过滤公式格式错误，请直接填写飞书公式文本，例如：CurrentValue.[状态] != "已关闭"')

    @classmethod
    def query_bitable_records(cls, config: dict[str, Any]) -> list[dict[str, Any]]:
        """
        拉取飞书多维表格记录。

        :param config: 人员催办配置。
        :return: 记录列表。
        """
        app_id, app_secret = cls._resolve_feishu_auth(config)
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        view_id = str(config.get("viewId") or "").strip()
        filter_formula = cls._normalize_bitable_filter_formula(config.get("filterFormula"))
        # filter_formula = str(config.get("filterFormula") or "").strip()
        page_size = min(max(int(config.get("pageSize") or 500), 1), 500)

        if not app_id or not app_secret:
            raise ValueError("飞书应用 appId/appSecret 未配置")
        if not app_token or not table_id:
            raise ValueError("多维表格 appToken/tableId 未配置")

        token = cls._get_tenant_access_token(app_id, app_secret)
        url = f"{cls.FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
        page_token = ""
        all_records: list[dict[str, Any]] = []
        max_pages = 200

        for page_index in range(max_pages):
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            if view_id:
                params["view_id"] = view_id
            if filter_formula:
                params["filter"] = filter_formula
            logger.info(f"飞书多维表格查询参数: {json.dumps(params, ensure_ascii=False)}")
            response_data = cls._request_feishu_json(
                method="POST",
                url=url,
                tenant_access_token=token,
                json_body=params,
            ).get("data") or {}
            page_records = response_data.get("items")
            # logger.info(
            #     f"多维表格数据结构：{json.dumps(page_records[0] if page_records else {}, ensure_ascii=False)}"
            # )
            if not isinstance(page_records, list):
                page_records = []
            all_records.extend([item for item in page_records if isinstance(item, dict)])
            has_more = bool(response_data.get("has_more"))
            page_token = str(response_data.get("page_token") or "").strip()
            if not has_more or not page_token:
                break
            logger.info(f"飞书多维表格分页拉取中: page={page_index + 1}, accumulated={len(all_records)}")
        logger.info(f"飞书多维表格拉取完成: records={len(all_records)}, table_id={table_id}, view_id={view_id or '-'}")
        return all_records

    @classmethod
    def _render_template(cls, template: str, variables: dict[str, Any], default_template: str) -> str:
        """
        渲染消息模板变量。

        :param template: 自定义模板。
        :param variables: 模板变量。
        :param default_template: 默认模板。
        :return: 渲染后的文本。
        """
        template_text = str(template or "").strip() or default_template
        try:
            return str(parse_string(template_text, variables or {}, {}, False))
        except Exception as exc:
            logger.warning(f"通知模板渲染失败，使用原模板兜底: error={exc}")
            return template_text

    @classmethod
    def _send_push_messages(
        cls,
        db: Session,
        *,
        push_ids: list[int],
        content: str,
        at_user_ids: list[str] | None = None,
    ) -> int:
        """
        按推送配置发送消息。

        :param db: 数据库会话。
        :param push_ids: 推送配置ID列表。
        :param content: 消息内容。
        :param at_user_ids: 运行时 @ 的飞书用户ID列表。
        :return: 成功发送的配置条数。
        """
        success_count = 0
        for push_id in push_ids:
            try:
                push_row = PushDao.get(db, int(push_id))
                if not push_row:
                    logger.warning(f"推送配置不存在，已跳过: push_id={push_id}")
                    continue
                MessageHandler(PushModel.model_validate(push_row), {}).push(
                    content=content,
                    at_user_ids=at_user_ids,
                )
                success_count += 1
            except Exception as exc:
                logger.warning(f"推送发送失败: push_id={push_id}, error={exc}")
        return success_count

    @classmethod
    def _build_rows_markdown(cls, rows: list[dict[str, Any]], max_rows: int) -> str:
        """
        构建催办记录的文本摘要。

        :param rows: 原始记录列表。
        :param max_rows: 最大展示条数。
        :return: 文本摘要。
        """
        lines: list[str] = []
        for index, row in enumerate(rows[: max(max_rows, 1)], start=1):
            logger.info(f"index={index}, row={row}")
            created_at = cls._parse_datetime_value(row.get("createdAt"))
            created_text = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
            ticket_no = cls._extract_ticket_no_from_row_payload(row) or "-"
            detail_url = row.get('detailUrl', '')
            line_data = f"{index}. [{created_text}]（工单ID: {ticket_no}）"
            if detail_url:
                line_data = f"{line_data} [详情]({row.get('detailUrl', '')})"
            lines.append(line_data)
        return "\n".join(lines) if lines else "暂无明细"

    @classmethod
    def _build_rows_markdown_with_template(
        cls,
        rows: list[dict[str, Any]],
        max_rows: int,
        rows_markdown_template: str | None,
    ) -> str:
        """
        使用可配置模板构建催办明细 Markdown。

        :param rows: 催办明细列表。
        :param max_rows: 最多输出的明细条数。
        :param rows_markdown_template: 明细行模板文本。
        :return: Markdown 文本。
        """
        lines: list[str] = []
        row_template = str(rows_markdown_template or "").strip() or cls.DEFAULT_PERSON_ROWS_MARKDOWN_TEMPLATE
        for index, row in enumerate(rows[: max(max_rows, 1)], start=1):
            created_at = cls._parse_datetime_value(row.get("createdAt"))
            created_text = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
            ticket_no = cls._extract_ticket_no_from_row_payload(row) or "-"
            detail_url = str(row.get("detailUrl") or "").strip()
            detail_link = f" [详情]({detail_url})" if detail_url else ""
            variables = {
                "index": index,
                "row_index": index,
                "created_at": created_text,
                "createdAt": created_text,
                "ticket_no": ticket_no,
                "ticketNo": ticket_no,
                "detail_url": detail_url,
                "detailUrl": detail_url,
                "detail_link": detail_link,
                "detailLink": detail_link,
            }
            try:
                line_data = str(parse_string(row_template, variables, {}, False))
            except Exception as exc:
                logger.warning(f"person reminder row template render failed, fallback to default: error={exc}")
                line_data = f"{index}. [{created_text}] 工单号：{ticket_no}{detail_link}"
            lines.append(line_data)
        return "\n".join(lines) if lines else "暂无明细"

    @classmethod
    def _extract_ticket_no_from_row_payload(cls, row: dict[str, Any]) -> str:
        """
        从催办明细行中提取工单号。

        :param row: 催办明细行。
        :return: 工单号文本，未命中返回空字符串。
        """
        if not isinstance(row, dict):
            return ""
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        for key in (
            "ticketNo",
            "ticket_no",
            "(IT)SNow工单号_TICKET_NO",
            "工单号",
            "ticketId",
            "ticket_id",
        ):
            value = fields.get(key)
            if value:
                if isinstance(value, str):
                    return value
                else:
                    if isinstance(value, list) and len(value) > 0:
                        return value[0].get("text", "")
        return ""

    @classmethod
    def _resolve_ticket_detail_url_by_ticket_no(
        cls,
        db: Session,
        *,
        ticket_no: str,
        ticket_url_cache: dict[str, str],
    ) -> str:
        """
        根据工单号解析工单详情 URL，并缓存结果。

        :param db: 数据库会话。
        :param ticket_no: 工单号。
        :param ticket_url_cache: 工单URL缓存。
        :return: 工单详情 URL，未命中返回空字符串。
        """
        normalized_ticket_no = str(ticket_no or "").strip()
        if not normalized_ticket_no:
            return ""
        if normalized_ticket_no in ticket_url_cache:
            return ticket_url_cache[normalized_ticket_no]
        ticket_row = (
            db.query(Ticket)
            .filter(Ticket.ticket_no == normalized_ticket_no, Ticket.del_flag == "0")
            .first()
        )
        detail_url = str(getattr(ticket_row, "ticket_url", "") or "").strip() if ticket_row else ""
        ticket_url_cache[normalized_ticket_no] = detail_url
        return detail_url

    @classmethod
    def _build_counter_markdown(cls, counter: dict[str, int]) -> str:
        """
        构建分组计数的文本摘要。

        :param counter: 分组计数字典。
        :return: 可读文本。
        """
        if not counter:
            return "暂无数据"
        ordered = sorted(counter.items(), key=lambda item: (-int(item[1] or 0), str(item[0] or "")))
        return "\n".join([f"- {key}: {count}" for key, count in ordered])

    @classmethod
    def _resolve_summary_time_field(cls, value: Any) -> str:
        """
        归一化汇总统计时间字段。

        :param value: 原始时间字段。
        :return: 可用字段名。
        """
        time_field = str(value or "").strip()
        if time_field in {"create_time", "update_time", "closed_at", "resolved_at", "started_at"}:
            return time_field
        return "create_time"

    @classmethod
    def _normalize_person_data_source(cls, value: Any) -> str:
        """
        归一化按人催办统计数据源。

        :param value: 原始数据源文本。
        :return: 归一化后的数据源（bitable/local）。
        """
        source = str(value or "").strip().lower()
        if source in {cls.PERSON_DATA_SOURCE_BITABLE, cls.PERSON_DATA_SOURCE_LOCAL}:
            return source
        return cls.PERSON_DATA_SOURCE_BITABLE

    @classmethod
    def _normalize_summary_data_source(cls, value: Any) -> str:
        """
        归一化汇总统计数据源。

        :param value: 原始数据源文本。
        :return: 归一化后的数据源（bitable/local）。
        """
        source = str(value or "").strip().lower()
        if source in {cls.SUMMARY_DATA_SOURCE_BITABLE, cls.SUMMARY_DATA_SOURCE_LOCAL}:
            return source
        return cls.SUMMARY_DATA_SOURCE_LOCAL

    @classmethod
    def _resolve_local_person_time_field(cls, value: Any) -> str:
        """
        归一化本地工单统计使用的时间字段。

        :param value: 原始时间字段。
        :return: 可用的工单时间字段名。
        """
        field = str(value or "").strip()
        if field in {"create_time", "update_time", "closed_at", "resolved_at", "started_at"}:
            return field
        return "update_time"

    @classmethod
    def _resolve_bitable_summary_time_field(cls, value: Any) -> str:
        """
        归一化飞书多维表格汇总统计时间字段。

        :param value: 原始时间字段名。
        :return: 时间字段名，未配置返回空字符串。
        """
        return str(value or "").strip()

    @classmethod
    def _normalize_summary_counter_label(cls, value: Any) -> str:
        """
        归一化汇总统计字段值，便于计数聚合。

        :param value: 原始字段值。
        :return: 归一化后的文本。
        """
        if value is None:
            return ""
        if isinstance(value, list):
            merged: list[str] = []
            for item in value:
                item_text = cls._normalize_summary_counter_label(item)
                if item_text and item_text not in merged:
                    merged.append(item_text)
            return "、".join(merged)
        if isinstance(value, dict):
            for key in ("text", "name", "value", "label"):
                item_text = str(value.get(key) or "").strip()
                if item_text:
                    return item_text
            return ""
        return str(value).strip()

    @classmethod
    def _is_closed_status_value(cls, value: Any) -> bool:
        """
        判断状态是否可视为已关闭/已完成。

        :param value: 状态文本。
        :return: 是否为关闭态。
        """
        status_text = str(value or "").strip().lower()
        if not status_text:
            return False
        closed_values = {
            "closed",
            "已关闭",
            "done",
            "已完成",
            "resolved",
            "已解决",
            "close",
            "完成",
        }
        if status_text in closed_values:
            return True
        return any(keyword in status_text for keyword in ["关闭", "完成", "解决"])

    @classmethod
    def _validate_person_reminder_config(cls, config: dict[str, Any]) -> list[str]:
        """
        校验人员催办统计的关键配置是否完整。

        :param config: 人员催办配置。
        :return: 缺失配置项对应的错误信息列表。
        """
        errors: list[str] = []
        data_source = cls._normalize_person_data_source(config.get("dataSource"))
        if data_source == cls.PERSON_DATA_SOURCE_LOCAL:
            return errors
        app_id, app_secret = cls._resolve_feishu_auth(config)
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        person_field = str(config.get("personField") or "").strip()
        time_field = str(config.get("timeField") or "").strip()
        if not app_id or not app_secret:
            errors.append("飞书应用 appId/appSecret 未配置")
        if not app_token or not table_id:
            errors.append("多维表格 appToken/tableId 未配置")
        if not person_field:
            errors.append("人员字段(personField)未配置")
        if not time_field:
            errors.append("时间字段(timeField)未配置")
        return errors

    @classmethod
    def _validate_summary_report_config(cls, config: dict[str, Any]) -> list[str]:
        """
        校验汇总统计关键配置是否完整。

        :param config: 汇总统计配置。
        :return: 配置错误列表。
        """
        errors: list[str] = []
        data_source = cls._normalize_summary_data_source(config.get("dataSource"))
        if data_source == cls.SUMMARY_DATA_SOURCE_LOCAL:
            return errors
        app_id, app_secret = cls._resolve_feishu_auth(config)
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        if not app_id or not app_secret:
            errors.append("飞书应用 appId/appSecret 未配置")
        if not app_token or not table_id:
            errors.append("多维表格 appToken/tableId 未配置")
        return errors

    @classmethod
    def _build_person_reminder_skipped_result(
        cls,
        *,
        config: dict[str, Any],
        skip_reason: str,
        config_errors: list[str] | None = None,
        trigger_source: str | None = None,
    ) -> dict[str, Any]:
        """
        构建人员催办跳过结果，避免配置缺失场景抛出异常。

        :param config: 人员催办配置。
        :param skip_reason: 跳过原因。
        :param config_errors: 配置错误列表。
        :param trigger_source: 可选触发来源。
        :return: 统一的跳过结果。
        """
        result: dict[str, Any] = {
            "skipped": True,
            "skipReason": skip_reason,
            "configErrors": config_errors or [],
            "dataSource": cls._normalize_person_data_source(config.get("dataSource")),
            "thresholdMinutes": max(int(config.get("thresholdMinutes") or 30), 1),
            "totalRecordCount": 0,
            "overdueRecordCount": 0,
            "skippedNoPersonCount": 0,
            "skippedNoTimeCount": 0,
            "skippedNotOverdueCount": 0,
            "personCount": 0,
            "people": [],
        }
        if trigger_source:
            result["triggerSource"] = trigger_source
        return result

    @classmethod
    def _collect_person_overdue_data(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        user_id: int | None = None,
        email: str | None = None,
        all:bool = False,
    ) -> dict[str, Any]:
        """
        统计按人聚合的超时记录。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :return: 统计结果。
        """
        data_source = cls._normalize_person_data_source(config.get("dataSource"))
        if data_source == cls.PERSON_DATA_SOURCE_LOCAL:
            return cls._collect_person_overdue_data_from_local(db, config=config, user_id=user_id, email=email)

        person_field = str(config.get("personField") or "").strip()
        time_field = str(config.get("timeField") or "").strip()
        threshold_minutes = max(int(config.get("thresholdMinutes") or 30), 1)
        if not person_field:
            raise ValueError("人员字段(personField)未配置")
        if not time_field:
            raise ValueError("时间字段(timeField)未配置")

        target_user = cls._resolve_target_user(db, user_id=user_id, email=email)
        if not all and not target_user:
            raise ValueError("未指定用户")

        records = cls.query_bitable_records(config)
        now = datetime.now()


        grouped: dict[str, list[dict[str, Any]]] = {}
        skipped_no_person = 0
        skipped_no_time = 0
        skipped_not_overdue = 0
        overdue_rows = 0
        ticket_url_cache: dict[str, str] = {}

        for record in records:
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            person_emails = cls._extract_person_names(fields.get(person_field))

            if not person_emails:
                skipped_no_person += 1
                continue

            if not all and target_user and target_user.email not in person_emails:
                skipped_no_person += 1
                continue
            created_at = cls._extract_record_time(record, time_field)
            if not created_at:
                skipped_no_time += 1
                continue
            overdue_minutes = int((now - created_at).total_seconds() // 60)
            if overdue_minutes < threshold_minutes:
                skipped_not_overdue += 1
                continue
            record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
            ticket_no = str(
                fields.get("ticketNo")
                or fields.get("ticket_no")
                or fields.get("(IT)SNow工单号_TICKET_NO")
                or fields.get("工单号")
                or fields.get("ticketId")
                or fields.get("ticket_id")
                or ""
            ).strip()
            detail_url = cls._resolve_ticket_detail_url_by_ticket_no(
                db,
                ticket_no=ticket_no,
                ticket_url_cache=ticket_url_cache,
            )
            row_payload = {
                "detailUrl": detail_url,
                "recordId": record_id,
                "ticketNo": ticket_no,
                "title": str(
                    fields.get("title")
                    or fields.get("标题")
                    or fields.get("ticketNo")
                    or fields.get("ticket_no")
                    or "-"
                ).strip(),
                "createdAt": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "overdueMinutes": overdue_minutes,
                "fields": fields,
            }
            for person_email in person_emails:
                grouped.setdefault(person_email, []).append(row_payload)
                overdue_rows += 1

        feishu_user_cache: dict[str, dict[str, Any] | None] = {}
        app_id, app_secret = cls._resolve_feishu_auth(config)
        people: list[dict[str, Any]] = []
        for person_email, person_rows in grouped.items():
            if not all and target_user and person_email != target_user.email:
                continue
            feishu_user = None
            if app_id and app_secret:
                if person_email not in feishu_user_cache:
                    feishu_user_cache[person_email] = cls.query_feishu_user_by_email(
                        app_id=app_id,
                        app_secret=app_secret,
                        email=person_email,
                    )
                feishu_user = feishu_user_cache.get(person_email)
            people.append(
                {
                    # "personName": target_user.user_name,
                    # "userId": target_user.user_id,
                    # "userName": target_user.user_name,
                    # "nickName": target_user.nick_name,
                    "email": person_email,
                    "feishuUser": feishu_user,
                    "overdueCount": len(person_rows),
                    "rows": sorted(person_rows, key=lambda item: item.get("overdueMinutes", 0), reverse=True),
                }
            )
            logger.info(f"催办人： {person_email}, IDS: {[i.get('ticketNo', '') for i in person_rows]}")

        people.sort(key=lambda item: item.get("overdueCount") or 0, reverse=True)
        return {
            "dataSource": data_source,
            "thresholdMinutes": threshold_minutes,
            "totalRecordCount": len(records),
            "overdueRecordCount": overdue_rows,
            "skippedNoPersonCount": skipped_no_person,
            "skippedNoTimeCount": skipped_no_time,
            "skippedNotOverdueCount": skipped_not_overdue,
            "personCount": len(people),
            "people": people,
        }

    @classmethod
    def _collect_person_overdue_data_from_local(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        基于本地工单数据统计按人聚合的超时记录。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :return: 统计结果。
        """
        threshold_minutes = max(int(config.get("thresholdMinutes") or 30), 1)
        time_field = cls._resolve_local_person_time_field(config.get("timeField"))
        include_closed = bool(config.get("includeClosed", False))
        closed_status_values = {"closed", "已关闭", "done", "已完成", "resolved", "已解决"}
        target_user = cls._resolve_target_user(db, user_id=user_id, email=email)
        target_email = cls._normalize_email(email or getattr(target_user, "email", ""))
        target_user_id = int(target_user.user_id) if target_user else (user_id or None)
        now = datetime.now()

        rows = db.query(Ticket).filter(Ticket.del_flag == "0").all()
        grouped: dict[str, dict[str, Any]] = {}
        skipped_no_person = 0
        skipped_no_time = 0
        skipped_not_overdue = 0
        overdue_rows = 0

        user_by_id_cache: dict[int, Any] = {}
        feishu_user_cache: dict[str, dict[str, Any] | None] = {}
        app_id, app_secret = cls._resolve_feishu_auth(config)

        for row in rows:
            row_status = str(getattr(row, "status", "") or "").strip()
            if not include_closed and row_status.lower() in closed_status_values:
                continue
            row_user_id = cls._safe_int(getattr(row, "current_assignee_id", None))
            row_person_name = str(getattr(row, "current_assignee_name", "") or "").strip()
            resolved_user = None
            if row_user_id:
                if row_user_id not in user_by_id_cache:
                    user_by_id_cache[row_user_id] = (
                        db.query(SysUser)
                        .filter(SysUser.user_id == row_user_id, SysUser.del_flag == "0", SysUser.status == "0")
                        .first()
                    )
                resolved_user = user_by_id_cache.get(row_user_id)
            if not row_person_name and resolved_user:
                row_person_name = str(
                    getattr(resolved_user, "nick_name", "")
                    or getattr(resolved_user, "user_name", "")
                    or ""
                ).strip()
            if not row_person_name:
                skipped_no_person += 1
                continue

            row_time = cls._parse_datetime_value(getattr(row, time_field, None))
            if not row_time:
                skipped_no_time += 1
                continue
            overdue_minutes = int((now - row_time).total_seconds() // 60)
            if overdue_minutes < threshold_minutes:
                skipped_not_overdue += 1
                continue

            group_key = f"id:{row_user_id}" if row_user_id else f"name:{row_person_name}"
            if group_key not in grouped:
                grouped[group_key] = {
                    "personName": row_person_name,
                    "userId": row_user_id,
                    "userName": getattr(resolved_user, "user_name", None) if resolved_user else None,
                    "nickName": getattr(resolved_user, "nick_name", None) if resolved_user else None,
                    "email": (
                        cls._normalize_email(getattr(resolved_user, "email", "")) or None
                        if resolved_user
                        else None
                    ),
                    "rows": [],
                }
            grouped[group_key]["rows"].append(
                {
                    "recordId": str(getattr(row, "ticket_no", "") or getattr(row, "ticket_id", "") or "").strip(),
                    "ticketNo": str(getattr(row, "ticket_no", "") or "").strip(),
                    "detailUrl": str(getattr(row, "ticket_url", "") or "").strip(),
                    "title": str(getattr(row, "title", "") or "-").strip(),
                    "createdAt": row_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "overdueMinutes": overdue_minutes,
                    "fields": {
                        "ticketNo": getattr(row, "ticket_no", None),
                        "status": getattr(row, "status", None),
                        "assigneeName": row_person_name,
                    },
                }
            )
            overdue_rows += 1

        people: list[dict[str, Any]] = []
        active_row_count = (
            sum(len(item.get("rows") or []) for item in grouped.values())
            + skipped_not_overdue
            + skipped_no_person
            + skipped_no_time
        )
        for item in grouped.values():
            person_name = str(item.get("personName") or "").strip()
            user_id_value = cls._safe_int(item.get("userId"))
            user = None
            if user_id_value:
                if user_id_value not in user_by_id_cache:
                    user_by_id_cache[user_id_value] = (
                        db.query(SysUser)
                        .filter(SysUser.user_id == user_id_value, SysUser.del_flag == "0", SysUser.status == "0")
                        .first()
                    )
                user = user_by_id_cache.get(user_id_value)
            if not user and person_name:
                user = cls._resolve_sys_user_by_name(db, person_name)
            user_id_value = int(user.user_id) if user else user_id_value
            if target_user_id and user_id_value != target_user_id:
                continue

            user_email = cls._normalize_email(
                getattr(user, "email", "") if user else item.get("email")
            )
            if target_email and user_email != target_email:
                continue

            feishu_user = None
            if user_email and app_id and app_secret:
                if user_email not in feishu_user_cache:
                    feishu_user_cache[user_email] = cls.query_feishu_user_by_email(
                        app_id=app_id,
                        app_secret=app_secret,
                        email=user_email,
                    )
                feishu_user = feishu_user_cache.get(user_email)

            person_rows = item.get("rows") if isinstance(item.get("rows"), list) else []
            people.append(
                {
                    "personName": person_name or "-",
                    "userId": user_id_value,
                    "userName": getattr(user, "user_name", None) if user else item.get("userName"),
                    "nickName": getattr(user, "nick_name", None) if user else item.get("nickName"),
                    "email": user_email or None,
                    "feishuUser": feishu_user,
                    "overdueCount": len(person_rows),
                    "rows": sorted(person_rows, key=lambda row_item: row_item.get("overdueMinutes", 0), reverse=True),
                }
            )

        people.sort(key=lambda item: item.get("overdueCount") or 0, reverse=True)
        return {
            "dataSource": cls.PERSON_DATA_SOURCE_LOCAL,
            "timeField": time_field,
            "thresholdMinutes": threshold_minutes,
            "totalRecordCount": active_row_count if not include_closed else len(rows),
            "overdueRecordCount": overdue_rows,
            "skippedNoPersonCount": skipped_no_person,
            "skippedNoTimeCount": skipped_no_time,
            "skippedNotOverdueCount": skipped_not_overdue,
            "personCount": len(people),
            "people": people,
        }

    @classmethod
    def preview_person_overdue_statistics(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        预览按人聚合的催办统计。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :return: 统计结果。
        """
        logger.info(
            f"开始预览人员催办统计: user_id={user_id or '-'}, email={email or '-'}, "
            f"enabled={bool(config.get('enabled'))}, "
            f"data_source={cls._normalize_person_data_source(config.get('dataSource'))}"
        )
        config_errors = cls._validate_person_reminder_config(config)
        if config_errors:
            skip_reason = "；".join(config_errors)
            logger.warning(
                f"人员催办统计预览跳过: user_id={user_id or '-'}, email={email or '-'}, reason={skip_reason}"
            )
            return cls._build_person_reminder_skipped_result(
                config=config,
                skip_reason=skip_reason,
                config_errors=config_errors,
            )
        result = cls._collect_person_overdue_data(db, config=config, user_id=user_id, email=email)
        logger.info(
            f"人员催办统计完成: person_count={result.get('personCount')}, "
            f"overdue_record_count={result.get('overdueRecordCount')}"
        )
        return result

    @classmethod
    def run_person_overdue_reminder(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        trigger_source: str,
        user_id: int | None = None,
        email: str | None = None,
        is_all: bool = False,
    ) -> dict[str, Any]:
        """
        执行按人催办通知。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param trigger_source: 触发来源，如 scheduler/manual。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :param is_all: 是否通知所有人
        :return: 执行结果摘要。
        """
        if not bool(config.get("enabled")):
            logger.info(f"人员催办通知跳过: enabled=false, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "人员催办开关未启用"}
        logger.info(
            "人员催办通知开始执行: "
            f"trigger={trigger_source}, data_source={cls._normalize_person_data_source(config.get('dataSource'))}, "
            f"user_id={user_id or '-'}, email={email or '-'}"
        )

        send_mode = cls._normalize_send_mode(config.get("sendMode"))
        push_ids = cls._normalize_push_ids(config.get("pushIds"))
        app_id, app_secret = cls._resolve_feishu_auth(config)
        require_push_channel = send_mode in {cls.SEND_MODE_PUSH_CONFIG, cls.SEND_MODE_HYBRID}
        require_feishu_app = send_mode in {cls.SEND_MODE_FEISHU_APP, cls.SEND_MODE_HYBRID}
        enable_push_channel = require_push_channel and bool(push_ids)
        enable_feishu_app = require_feishu_app and bool(app_id and app_secret)
        if send_mode == cls.SEND_MODE_PUSH_CONFIG and not enable_push_channel:
            logger.info(f"人员催办通知跳过: send_mode={send_mode}, pushIds 为空, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置催办推送渠道"}
        if send_mode == cls.SEND_MODE_FEISHU_APP and not enable_feishu_app:
            logger.info(f"人员催办通知跳过: send_mode={send_mode}, 飞书凭证缺失, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "飞书应用凭证未配置"}
        if send_mode == cls.SEND_MODE_HYBRID and not (enable_push_channel or enable_feishu_app):
            logger.info(f"人员催办通知跳过: send_mode={send_mode}, 推送与应用配置都不可用, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置可用的催办发送渠道"}
        if send_mode == cls.SEND_MODE_HYBRID and not enable_push_channel:
            logger.warning(
                f"人员催办通知降级: send_mode=hybrid, pushIds 为空，仅使用飞书应用发送, trigger={trigger_source}"
            )
        if send_mode == cls.SEND_MODE_HYBRID and not enable_feishu_app:
            logger.warning(
                f"人员催办通知降级: send_mode=hybrid, 飞书凭证缺失，仅使用推送配置发送, trigger={trigger_source}"
            )

        config_errors = cls._validate_person_reminder_config(config)
        if config_errors:
            skip_reason = "；".join(config_errors)
            logger.warning(
                f"人员催办通知跳过: trigger={trigger_source}, user_id={user_id or '-'}, "
                f"email={email or '-'}, reason={skip_reason}"
            )
            return cls._build_person_reminder_skipped_result(
                config=config,
                skip_reason=skip_reason,
                config_errors=config_errors,
                trigger_source=trigger_source,
            )

        summary = cls._collect_person_overdue_data(db, config=config, user_id=user_id, email=email, all=is_all)
        message_template = str(config.get("messageTemplate") or "").strip() or cls.DEFAULT_PERSON_TEMPLATE
        rows_markdown_template = str(config.get("rowsMarkdownTemplate") or "").strip()
        max_rows_per_person = max(int(config.get("maxRowsPerPerson") or 20), 1)

        sent_people = 0
        sent_push_count = 0
        sent_private_count = 0
        skipped_people = 0
        skipped_private_count = 0
        person_results: list[dict[str, Any]] = []
        for person in summary.get("people") or []:
            overdue_count = int(person.get("overdueCount") or 0)
            if overdue_count <= 0:
                skipped_people += 1
                continue
            rows = person.get("rows") if isinstance(person.get("rows"), list) else []
            rows_markdown = cls._build_rows_markdown_with_template(
                rows,
                max_rows_per_person,
                rows_markdown_template,
            )
            variables = {
                "person_name": person.get("personName") or "-",
                "threshold_minutes": summary.get("thresholdMinutes") or 0,
                "overdue_count": overdue_count,
                "rows_markdown": rows_markdown,
                "now_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "email": person.get("email") or "-",
            }
            content = cls._render_template(message_template, variables, cls.DEFAULT_PERSON_TEMPLATE)
            feishu_user = person.get("feishuUser") if isinstance(person.get("feishuUser"), dict) else {}
            open_id = str(feishu_user.get("openId") or "").strip()
            at_user_ids = [open_id] if open_id else None
            push_success_count = 0
            if enable_push_channel:
                push_success_count = cls._send_push_messages(
                    db,
                    push_ids=push_ids,
                    content=content,
                    at_user_ids=at_user_ids,
                )
            private_success_count = 0
            person_email = cls._normalize_email(person.get("email"))
            if enable_feishu_app:
                logger.info(f"推送：{person_email}   --  {content}")

                if person_email:
                    private_success_count = cls._send_feishu_text_messages(
                        app_id=app_id,
                        app_secret=app_secret,
                        receive_id_type="email",
                        receive_ids=[person_email],
                        content=content,
                    )
                else:
                    skipped_private_count += 1
            sent_people += 1
            sent_push_count += push_success_count
            sent_private_count += private_success_count
            person_results.append(
                {
                    "personName": person.get("personName"),
                    "email": person.get("email"),
                    "overdueCount": overdue_count,
                    "pushSuccessCount": push_success_count,
                    "privateSuccessCount": private_success_count,
                    "atOpenId": open_id or None,
                }
            )
            logger.info(
                f"人员催办发送完成: person={person.get('personName')}, overdue={overdue_count}, "
                f"push_success={push_success_count}, private_success={private_success_count}, "
                f"send_mode={send_mode}, trigger={trigger_source}"
            )

        return {
            "triggerSource": trigger_source,
            "skipped": False,
            "sendMode": send_mode,
            "personCount": summary.get("personCount"),
            "sentPeople": sent_people,
            "sentPushCount": sent_push_count,
            "sentPrivateCount": sent_private_count,
            "skippedPeople": skipped_people,
            "skippedPrivateCount": skipped_private_count,
            "statSummary": summary,
            "personResults": person_results,
        }

    @classmethod
    def list_push_options(cls, db: Session) -> list[dict[str, Any]]:
        """
        查询可用推送配置下拉选项。

        :param db: 数据库会话。
        :return: 推送配置选项。
        """
        rows = (
            db.query(PushTarget)
            .filter(PushTarget.allow_push == 1)
            .order_by(PushTarget.create_time.desc())
            .all()
        )
        return [
            {
                "pushId": row.push_id,
                "name": row.name,
                "type": row.type,
                "allowPush": row.allow_push,
                "label": f"{row.name}（{row.push_id}）",
            }
            for row in rows
        ]

    @classmethod
    def _build_group_ticket_variables(
        cls,
        ticket: Ticket,
        sync_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        构建群推送模板变量。

        :param ticket: 工单对象。
        :param sync_summary: 同步摘要信息。
        :return: 模板变量字典。
        """
        sync_data = sync_summary if isinstance(sync_summary, dict) else {}
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        external_sync = (
            extra_data.get("external_sync")
            if isinstance(extra_data.get("external_sync"), dict)
            else {}
        )
        source_snapshot = (
            external_sync.get("source")
            if isinstance(external_sync.get("source"), dict)
            else {}
        )
        external_field_mapping = (
            extra_data.get("external_field_mapping")
            if isinstance(extra_data.get("external_field_mapping"), dict)
            else {}
        )
        description = str(ticket.description or "").strip()
        if len(description) > 200:
            description = f"{description[:200]}..."
        ticket_url = (
            str(getattr(ticket, "ticket_url", "") or "").strip()
            or str(sync_data.get("ticketUrl") or sync_data.get("sourceRecordUrl") or "").strip()
        )
        store_id = str(source_snapshot.get("storeId") or "").strip()
        store_name = str(source_snapshot.get("storeName") or "").strip()
        raw_store_info = str(external_field_mapping.get("ticketStore") or "").strip()
        if store_name and store_id:
            store_info = f"{store_name}({store_id})"
        elif store_name:
            store_info = store_name
        elif store_id:
            store_info = store_id
        else:
            store_info = raw_store_info
        reporter_name = str(ticket.reporter_name or "").strip()
        first_line_assignee_name = str(getattr(ticket, "first_line_assignee_name", "") or "").strip()
        internal_owner_name = str(getattr(ticket, "internal_owner_name", "") or "").strip()
        return {
            "ticket_id": ticket.ticket_id,
            "ticket_no": ticket.ticket_no or "-",
            "ticket_title": ticket.title or "-",
            "project_name": ticket.merchant_name or "-",
            "module_name": ticket.module_name or "-",
            "ticket_status": ticket.status or "-",
            "reporter_name": reporter_name or "-",
            "reporterName": reporter_name or "-",
            "first_line_assignee_name": first_line_assignee_name or "-",
            "firstLineAssigneeName": first_line_assignee_name or "-",
            "assignee_name": ticket.current_assignee_name or "-",
            "currentAssigneeName": ticket.current_assignee_name or "-",
            "internal_owner_name": internal_owner_name or "-",
            "internalOwnerName": internal_owner_name or "-",
            "customer_priority": ticket.customer_priority or "-",
            "internal_priority": ticket.internal_priority or "-",
            "source": ticket.source or "-",
            "store_info": store_info or "-",
            "storeInfo": store_info or "-",
            "store_id": store_id or "-",
            "store_name": store_name or "-",
            "description": description or "-",
            "ticket_url": ticket_url or "-",
            "sync_revision": sync_data.get("revision") or "-",
            "sync_source_system": sync_data.get("sourceSystem") or "-",
            "sync_source_record_url": sync_data.get("sourceRecordUrl") or "-",
            "sync_status": sync_data.get("status") or "-",
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def send_group_message_for_ticket(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        group_config: dict[str, Any],
        scene: str,
        manual_trigger: bool = False,
        override_push_ids: list[int] | None = None,
        override_chat_ids: list[str] | None = None,
        override_template: str | None = None,
        sync_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        按工单发送群消息通知。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param group_config: 群推送配置。
        :param scene: 触发场景，支持 external_sync/remote_pull/manual。
        :param manual_trigger: 是否手动触发。
        :param override_push_ids: 手动触发时覆盖推送ID。
        :param override_chat_ids: 手动触发时覆盖群 chat_id。
        :param override_template: 手动触发时覆盖消息模板。
        :param sync_summary: 同步摘要信息。
        :return: 推送结果摘要。
        """
        enabled = bool(group_config.get("enabled"))
        if not enabled:
            logger.info(f"群推送跳过: enabled=false, scene={scene}")
            return {"skipped": True, "skipReason": "群推送开关未启用", "scene": scene}

        if not manual_trigger:
            if scene == "external_sync" and not bool(group_config.get("sendAfterExternalSync")):
                logger.info("群推送跳过: sendAfterExternalSync=false")
                return {"skipped": True, "skipReason": "外部同步后群推送未启用", "scene": scene}
            if scene == "remote_pull" and not bool(group_config.get("sendAfterRemotePull")):
                logger.info("群推送跳过: sendAfterRemotePull=false")
                return {"skipped": True, "skipReason": "远端拉取后群推送未启用", "scene": scene}
        send_mode = cls._normalize_send_mode(group_config.get("sendMode"))
        app_id, app_secret = cls._resolve_feishu_auth(group_config)
        ticket_priority = cls._resolve_priority_from_ticket(ticket)
        push_ids, chat_ids, route_info = cls._resolve_group_route_targets(
            group_config=group_config,
            ticket_priority=ticket_priority,
            override_push_ids=override_push_ids,
            override_chat_ids=override_chat_ids,
        )
        configured_routes = (
            group_config.get("priorityRoutes") if isinstance(group_config.get("priorityRoutes"), list) else []
        )
        if configured_routes and not route_info.get("matchedRoute"):
            route_priorities: list[list[str]] = []
            for route in configured_routes:
                if not isinstance(route, dict):
                    continue
                priorities = route.get("priorities")
                if isinstance(priorities, list):
                    normalized_route_priorities = [cls._normalize_priority(item) for item in priorities]
                elif isinstance(priorities, str):
                    normalized_route_priorities = [cls._normalize_priority(item) for item in priorities.split(",")]
                else:
                    normalized_route_priorities = []
                normalized_route_priorities = [item for item in normalized_route_priorities if item]
                if normalized_route_priorities:
                    route_priorities.append(normalized_route_priorities)
            logger.warning(
                f"群推送优先级路由未命中，将回退默认目标: "
                f"ticket_no={ticket.ticket_no}, scene={scene}, resolved_priority={ticket_priority or '-'}, "
                f"route_priorities={route_priorities}, fallback_push_ids={push_ids}, fallback_chat_ids={chat_ids}"
            )

        require_push_channel = send_mode in {cls.SEND_MODE_PUSH_CONFIG, cls.SEND_MODE_HYBRID}
        require_feishu_app = send_mode in {cls.SEND_MODE_FEISHU_APP, cls.SEND_MODE_HYBRID}
        enable_push_channel = require_push_channel and bool(push_ids)
        enable_feishu_app = require_feishu_app and bool(chat_ids and app_id and app_secret)
        if send_mode == cls.SEND_MODE_PUSH_CONFIG and not enable_push_channel:
            logger.info(f"群推送跳过: send_mode={send_mode}, pushIds 为空, ticket_no={ticket.ticket_no}")
            return {"skipped": True, "skipReason": "未配置群推送渠道", "scene": scene}
        if send_mode == cls.SEND_MODE_FEISHU_APP and not chat_ids:
            logger.info(f"群推送跳过: send_mode={send_mode}, appChatIds 为空, ticket_no={ticket.ticket_no}")
            return {"skipped": True, "skipReason": "未配置群 chat_id", "scene": scene}
        if send_mode == cls.SEND_MODE_FEISHU_APP and (not app_id or not app_secret):
            logger.info(f"群推送跳过: send_mode={send_mode}, 飞书凭证缺失, ticket_no={ticket.ticket_no}")
            return {"skipped": True, "skipReason": "飞书应用凭证未配置", "scene": scene}
        if send_mode == cls.SEND_MODE_HYBRID and not (enable_push_channel or enable_feishu_app):
            logger.info(f"群推送跳过: send_mode={send_mode}, 推送与应用配置都不可用, ticket_no={ticket.ticket_no}")
            return {"skipped": True, "skipReason": "未配置可用的群推送渠道", "scene": scene}
        if send_mode == cls.SEND_MODE_HYBRID and not enable_push_channel:
            logger.warning(f"群推送降级: ticket_no={ticket.ticket_no}, send_mode=hybrid, pushIds 为空，仅应用身份发送")
        if send_mode == cls.SEND_MODE_HYBRID and not enable_feishu_app:
            logger.warning(
                f"群推送降级: ticket_no={ticket.ticket_no}, send_mode=hybrid, 应用 chat_id/凭证不可用，仅推送配置发送"
            )

        message_template = str(override_template or "").strip()
        if not message_template:
            manual_template = str(group_config.get("manualTemplate") or "").strip()
            default_template = str(group_config.get("template") or "").strip()
            message_template = manual_template if manual_trigger and manual_template else default_template

        template_variables = cls._build_group_ticket_variables(ticket, sync_summary=sync_summary)
        mention_open_ids, mention_targets = cls._resolve_group_mention_open_ids(
            db,
            ticket=ticket,
            app_id=app_id,
            app_secret=app_secret,
        )
        template_variables.update(cls._build_group_mention_template_variables(mention_targets))
        content = cls._render_template(message_template, template_variables, cls.DEFAULT_GROUP_TEMPLATE)
        content_has_explicit_mentions = "<at user_id=" in content
        push_success_count = 0
        if enable_push_channel:
            push_success_count = cls._send_push_messages(
                db,
                push_ids=push_ids,
                content=content,
                at_user_ids=None if content_has_explicit_mentions else mention_open_ids or None,
            )
        app_success_count = 0
        if enable_feishu_app:
            app_success_count = cls._send_feishu_text_messages(
                app_id=app_id,
                app_secret=app_secret,
                receive_id_type="chat_id",
                receive_ids=chat_ids,
                content=content,
                mention_open_ids=None if content_has_explicit_mentions else mention_open_ids,
            )
        logger.info(
            f"群推送发送完成: ticket_no={ticket.ticket_no}, scene={scene}, "
            f"ticket_priority={ticket_priority or '-'}, push_success_count={push_success_count}, "
            f"app_success_count={app_success_count}, send_mode={send_mode}, "
            f"mention_count={len(mention_open_ids)}"
        )
        return {
            "skipped": False,
            "scene": scene,
            "ticketNo": ticket.ticket_no,
            "ticketPriority": ticket_priority or None,
            "sendMode": send_mode,
            "routeInfo": route_info,
            "pushCount": len(push_ids),
            "pushSuccessCount": push_success_count,
            "chatCount": len(chat_ids),
            "chatSuccessCount": app_success_count,
            "mentionOpenIds": mention_open_ids,
            "mentionTargets": mention_targets,
            "templateVariables": template_variables,
        }

    @classmethod
    def _collect_ticket_summary(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        time_field: str,
        include_closed: bool,
    ) -> dict[str, Any]:
        """
        在指定时间窗口内统计工单状态/分类/优先级数量（支持本地与多维表格）。

        :param db: 数据库会话。
        :param config: 汇总统计配置。
        :param start_time: 统计开始时间。
        :param end_time: 统计结束时间。
        :param time_field: 时间字段。
        :param include_closed: 是否包含已关闭工单。
        :return: 统计结果摘要。
        """
        data_source = cls._normalize_summary_data_source(config.get("dataSource"))
        if data_source == cls.SUMMARY_DATA_SOURCE_BITABLE:
            return cls._collect_ticket_summary_from_bitable(
                config=config,
                start_time=start_time,
                end_time=end_time,
                include_closed=include_closed,
            )
        return cls._collect_ticket_summary_from_local(
            db,
            start_time=start_time,
            end_time=end_time,
            time_field=time_field,
            include_closed=include_closed,
        )

    @classmethod
    def _collect_ticket_summary_from_local(
        cls,
        db: Session,
        *,
        start_time: datetime,
        end_time: datetime,
        time_field: str,
        include_closed: bool,
    ) -> dict[str, Any]:
        """
        使用本地工单数据统计状态/分类/优先级。

        :param db: 数据库会话。
        :param start_time: 统计开始时间。
        :param end_time: 统计结束时间。
        :param time_field: 本地工单时间字段。
        :param include_closed: 是否包含关闭态。
        :return: 统计结果摘要。
        """
        normalized_time_field = cls._resolve_summary_time_field(time_field)
        time_column = getattr(Ticket, normalized_time_field, Ticket.create_time)
        query = db.query(Ticket).filter(Ticket.del_flag == "0", time_column >= start_time, time_column <= end_time)
        if not include_closed:
            query = query.filter(~Ticket.status.in_(["CLOSED", "closed", "已关闭"]))
        rows = query.all()

        status_counter: dict[str, int] = {}
        category_counter: dict[str, int] = {}
        priority_counter: dict[str, int] = {}
        for row in rows:
            status_value = str(getattr(row, "status", "") or "").strip() or "未知状态"
            category_value = str(getattr(row, "category_name", "") or "").strip() or "未分类"
            priority_value = cls._resolve_priority_from_ticket(row) or "未知优先级"
            status_counter[status_value] = status_counter.get(status_value, 0) + 1
            category_counter[category_value] = category_counter.get(category_value, 0) + 1
            priority_counter[priority_value] = priority_counter.get(priority_value, 0) + 1

        return {
            "dataSource": cls.SUMMARY_DATA_SOURCE_LOCAL,
            "timeField": normalized_time_field,
            "startTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "totalCount": len(rows),
            "sourceRecordCount": len(rows),
            "skippedNoTimeCount": 0,
            "skippedOutOfRangeCount": 0,
            "skippedClosedCount": 0,
            "statusCounter": status_counter,
            "categoryCounter": category_counter,
            "priorityCounter": priority_counter,
        }

    @classmethod
    def _collect_ticket_summary_from_bitable(
        cls,
        *,
        config: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        include_closed: bool,
    ) -> dict[str, Any]:
        """
        使用飞书多维表格数据统计状态/分类/优先级。

        :param config: 汇总统计配置。
        :param start_time: 统计开始时间。
        :param end_time: 统计结束时间。
        :param include_closed: 是否包含关闭态。
        :return: 统计结果摘要。
        """
        status_field = str(config.get("statusField") or "状态").strip() or "状态"
        category_field = str(config.get("categoryField") or "分类").strip() or "分类"
        priority_field = str(config.get("priorityField") or "优先级").strip() or "优先级"
        time_field = cls._resolve_bitable_summary_time_field(config.get("bitableTimeField"))
        records = cls.query_bitable_records(config)

        status_counter: dict[str, int] = {}
        category_counter: dict[str, int] = {}
        priority_counter: dict[str, int] = {}
        skipped_no_time = 0
        skipped_out_of_range = 0
        skipped_closed = 0
        included_count = 0

        for record in records:
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            record_time = cls._extract_record_time(record, time_field)
            if not record_time:
                skipped_no_time += 1
                continue
            if record_time < start_time or record_time > end_time:
                skipped_out_of_range += 1
                continue

            status_value = cls._normalize_summary_counter_label(fields.get(status_field)) or "未知状态"
            if not include_closed and cls._is_closed_status_value(status_value):
                skipped_closed += 1
                continue
            category_value = cls._normalize_summary_counter_label(fields.get(category_field)) or "未分类"
            priority_value = (
                cls._normalize_priority(
                    cls._normalize_summary_counter_label(fields.get(priority_field))
                )
                or "未知优先级"
            )
            status_counter[status_value] = status_counter.get(status_value, 0) + 1
            category_counter[category_value] = category_counter.get(category_value, 0) + 1
            priority_counter[priority_value] = priority_counter.get(priority_value, 0) + 1
            included_count += 1

        return {
            "dataSource": cls.SUMMARY_DATA_SOURCE_BITABLE,
            "timeField": time_field or "created_time",
            "startTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "totalCount": included_count,
            "sourceRecordCount": len(records),
            "skippedNoTimeCount": skipped_no_time,
            "skippedOutOfRangeCount": skipped_out_of_range,
            "skippedClosedCount": skipped_closed,
            "statusCounter": status_counter,
            "categoryCounter": category_counter,
            "priorityCounter": priority_counter,
        }

    @classmethod
    def _build_summary_ai_user_prompt(cls, summary: dict[str, Any]) -> str:
        """
        构建汇总统计 AI 解读的用户提示词。

        :param summary: 汇总统计结果。
        :return: 用户提示词文本。
        """
        summary_json = json.dumps(summary or {}, ensure_ascii=False, separators=(",", ":"), default=str)
        return (
            "请基于以下工单汇总统计结果给出简洁解读。\n"
            "要求：\n"
            "1) 总结核心问题和变化趋势；\n"
            "2) 给出1-3条可执行建议；\n"
            "3) 输出纯文本，不要Markdown列表编号。\n\n"
            f"统计数据：{summary_json}"
        )

    @classmethod
    def _build_summary_ai_text(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        summary: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """
        调用轻量 AI 生成汇总统计解读。

        :param db: 数据库会话。
        :param config: 汇总统计配置。
        :param summary: 汇总统计结果。
        :return: (AI解读文本, 元信息)。
        """
        if not bool(config.get("aiEnabled")):
            return "", {"skipped": True, "skipReason": "aiEnabled=false"}
        provider_code = str(config.get("aiProviderCode") or "").strip()
        prompt_code = str(config.get("aiPromptCode") or "").strip()
        if not provider_code or not prompt_code:
            return "", {
                "skipped": True,
                "skipReason": "未配置 aiProviderCode 或 aiPromptCode",
                "providerCode": provider_code,
                "promptCode": prompt_code,
            }

        provider = AiProviderDao.get_ai_provider_by_code(db, provider_code)
        if not provider or not bool(getattr(provider, "enabled", True)):
            return "", {
                "skipped": True,
                "skipReason": "Provider不存在或已停用",
                "providerCode": provider_code,
                "promptCode": prompt_code,
            }

        prompt_templates = AiPromptTemplateService.get_prompt_template_texts_by_codes(db, [prompt_code])
        if not prompt_templates:
            return "", {
                "skipped": True,
                "skipReason": "提示词模板不存在或未启用",
                "providerCode": provider_code,
                "promptCode": prompt_code,
            }
        prompt_template = prompt_templates[0]
        system_prompt = AiPromptTemplateService.render_prompt_text(
            prompt_template.get("promptContent") or "",
            {
                "start_time": summary.get("startTime"),
                "end_time": summary.get("endTime"),
                "total_count": summary.get("totalCount"),
                "data_source": summary.get("dataSource"),
                "summary_json": json.dumps(summary or {}, ensure_ascii=False, default=str),
            },
        )
        user_prompt = cls._build_summary_ai_user_prompt(summary)
        try:
            ai_text = TicketLightAiService._call_model_api(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
            )
            return str(ai_text or "").strip(), {
                "skipped": False,
                "providerCode": provider_code,
                "promptCode": prompt_code,
            }
        except Exception as exc:
            logger.warning(f"工单汇总AI解读失败: provider={provider_code}, prompt={prompt_code}, error={exc}")
            return "", {
                "skipped": True,
                "providerCode": provider_code,
                "promptCode": prompt_code,
                "error": str(exc),
            }

    @classmethod
    def run_ticket_summary_report(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        trigger_source: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """
        执行工单汇总统计通知。

        :param db: 数据库会话。
        :param config: 汇总通知配置。
        :param trigger_source: 触发来源（scheduler/manual）。
        :param start_time: 可选统计开始时间。
        :param end_time: 可选统计结束时间。
        :return: 发送结果摘要。
        """
        if not bool(config.get("enabled")):
            logger.info(f"工单汇总通知跳过: enabled=false, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "汇总通知开关未启用"}

        data_source = cls._normalize_summary_data_source(config.get("dataSource"))
        config_errors = cls._validate_summary_report_config(config)
        if config_errors:
            skip_reason = "；".join(config_errors)
            logger.warning(
                f"工单汇总通知跳过: trigger={trigger_source}, "
                f"data_source={data_source}, reason={skip_reason}"
            )
            return {
                "triggerSource": trigger_source,
                "skipped": True,
                "skipReason": skip_reason,
                "configErrors": config_errors,
                "dataSource": data_source,
            }

        time_field = cls._resolve_summary_time_field(config.get("timeField"))
        include_closed = bool(config.get("includeClosed", True))
        now = datetime.now()
        resolved_end_time = end_time
        if resolved_end_time is None:
            resolved_end_time = cls._parse_datetime_value(config.get("endTime"))
        if resolved_end_time is None:
            end_delay_minutes = max(cls._safe_int(config.get("endDelayMinutes")) or 0, 0)
            resolved_end_time = now - timedelta(minutes=end_delay_minutes)

        resolved_start_time = start_time
        if resolved_start_time is None:
            resolved_start_time = cls._parse_datetime_value(config.get("startTime"))
        if resolved_start_time is None:
            window_minutes = max(cls._safe_int(config.get("windowMinutes")) or 60, 1)
            resolved_start_time = resolved_end_time - timedelta(minutes=window_minutes)

        if resolved_start_time > resolved_end_time:
            resolved_start_time, resolved_end_time = resolved_end_time, resolved_start_time

        summary = cls._collect_ticket_summary(
            db,
            config=config,
            start_time=resolved_start_time,
            end_time=resolved_end_time,
            time_field=time_field,
            include_closed=include_closed,
        )
        ai_summary_text, ai_summary_meta = cls._build_summary_ai_text(db, config=config, summary=summary)
        if ai_summary_text:
            ai_summary = ai_summary_text
        elif str(ai_summary_meta.get("error") or "").strip():
            ai_summary = f"AI处理失败：{ai_summary_meta.get('error')}"
        elif str(ai_summary_meta.get("skipReason") or "").strip():
            ai_summary = f"未启用AI处理：{ai_summary_meta.get('skipReason')}"
        else:
            ai_summary = "未启用AI处理"

        message_template = str(config.get("messageTemplate") or "").strip() or cls.DEFAULT_SUMMARY_TEMPLATE
        variables = {
            "data_source": summary.get("dataSource"),
            "start_time": summary.get("startTime"),
            "end_time": summary.get("endTime"),
            "time_field": summary.get("timeField"),
            "total_count": summary.get("totalCount"),
            "status_summary": cls._build_counter_markdown(summary.get("statusCounter") or {}),
            "category_summary": cls._build_counter_markdown(summary.get("categoryCounter") or {}),
            "priority_summary": cls._build_counter_markdown(summary.get("priorityCounter") or {}),
            "ai_summary": ai_summary,
            "now_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        content = cls._render_template(message_template, variables, cls.DEFAULT_SUMMARY_TEMPLATE)

        send_mode = cls._normalize_send_mode(config.get("sendMode"))
        push_ids = cls._normalize_push_ids(config.get("pushIds"))
        chat_ids = cls._normalize_chat_ids(config.get("appChatIds"))
        app_id, app_secret = cls._resolve_feishu_auth(config)
        require_push_channel = send_mode in {cls.SEND_MODE_PUSH_CONFIG, cls.SEND_MODE_HYBRID}
        require_feishu_app = send_mode in {cls.SEND_MODE_FEISHU_APP, cls.SEND_MODE_HYBRID}
        enable_push_channel = require_push_channel and bool(push_ids)
        enable_feishu_app = require_feishu_app and bool(chat_ids and app_id and app_secret)
        if send_mode == cls.SEND_MODE_PUSH_CONFIG and not enable_push_channel:
            logger.info(f"工单汇总通知跳过: send_mode={send_mode}, pushIds 为空")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置汇总推送渠道"}
        if send_mode == cls.SEND_MODE_FEISHU_APP and not chat_ids:
            logger.info(f"工单汇总通知跳过: send_mode={send_mode}, appChatIds 为空")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置汇总群 chat_id"}
        if send_mode == cls.SEND_MODE_FEISHU_APP and (not app_id or not app_secret):
            logger.info(f"工单汇总通知跳过: send_mode={send_mode}, 飞书凭证缺失")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "飞书应用凭证未配置"}
        if send_mode == cls.SEND_MODE_HYBRID and not (enable_push_channel or enable_feishu_app):
            logger.info(f"工单汇总通知跳过: send_mode={send_mode}, 推送与应用配置都不可用")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置可用的汇总发送渠道"}
        if send_mode == cls.SEND_MODE_HYBRID and not enable_push_channel:
            logger.warning("工单汇总通知降级: send_mode=hybrid, pushIds 为空，仅应用身份发送")
        if send_mode == cls.SEND_MODE_HYBRID and not enable_feishu_app:
            logger.warning("工单汇总通知降级: send_mode=hybrid, 应用 chat_id/凭证不可用，仅推送配置发送")

        push_success_count = 0
        if enable_push_channel:
            push_success_count = cls._send_push_messages(db, push_ids=push_ids, content=content, at_user_ids=None)
        chat_success_count = 0
        if enable_feishu_app:
            chat_success_count = cls._send_feishu_text_messages(
                app_id=app_id,
                app_secret=app_secret,
                receive_id_type="chat_id",
                receive_ids=chat_ids,
                content=content,
            )

        logger.info(
            f"工单汇总通知发送完成: trigger={trigger_source}, send_mode={send_mode}, "
            f"data_source={summary.get('dataSource')}, push_success_count={push_success_count}, "
            f"chat_success_count={chat_success_count}, total_count={summary.get('totalCount')}, "
            f"time_field={summary.get('timeField')}, ai_enabled={bool(config.get('aiEnabled'))}"
        )
        return {
            "triggerSource": trigger_source,
            "skipped": False,
            "sendMode": send_mode,
            "pushCount": len(push_ids),
            "pushSuccessCount": push_success_count,
            "chatCount": len(chat_ids),
            "chatSuccessCount": chat_success_count,
            "statSummary": summary,
            "messageVariables": variables,
            "aiSummaryMeta": ai_summary_meta,
        }
