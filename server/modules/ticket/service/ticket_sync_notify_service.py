from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

from module_admin.entity.do.user_do import SysUser
from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.do.push_do import PushTarget
from module_hrm.entity.vo.push_vo import PushModel
from module_hrm.utils.parser import parse_string
from modules.ticket.entity.do.ticket_do import Ticket
from utils.log_util import logger
from utils.message_util import MessageHandler


class TicketSyncNotifyService:
    """
    工单同步通知服务，负责人维度催办提醒与群消息推送。
    """

    FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
    _tenant_token_cache: dict[str, dict[str, Any]] = {}

    DEFAULT_PERSON_TEMPLATE = (
        "【工单催办提醒】\n"
        "负责人：${person_name}\n"
        "阈值：${threshold_minutes} 分钟\n"
        "超时条数：${overdue_count}\n"
        "统计时间：${now_time}\n\n"
        "${rows_markdown}"
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
        "说明：${description}"
    )

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
        response.raise_for_status()
        data = response.json()
        if int(data.get("code") or 0) != 0:
            raise RuntimeError(f"飞书接口调用失败: {data.get('msg') or data}")
        return data

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
                name = str(item.get("name") or item.get("text") or item.get("value") or "").strip()
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
    def query_bitable_records(cls, config: dict[str, Any]) -> list[dict[str, Any]]:
        """
        拉取飞书多维表格记录。

        :param config: 人员催办配置。
        :return: 记录列表。
        """
        app_id = str(config.get("feishuAppId") or "").strip()
        app_secret = str(config.get("feishuAppSecret") or "").strip()
        app_token = str(config.get("appToken") or "").strip()
        table_id = str(config.get("tableId") or "").strip()
        view_id = str(config.get("viewId") or "").strip()
        filter_formula = str(config.get("filterFormula") or "").strip()
        page_size = min(max(int(config.get("pageSize") or 500), 1), 500)

        if not app_id or not app_secret:
            raise ValueError("飞书应用 appId/appSecret 未配置")
        if not app_token or not table_id:
            raise ValueError("多维表格 appToken/tableId 未配置")

        token = cls._get_tenant_access_token(app_id, app_secret)
        url = f"{cls.FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
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
            response_data = cls._request_feishu_json(
                method="GET",
                url=url,
                tenant_access_token=token,
                params=params,
            ).get("data") or {}
            page_records = response_data.get("items")
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
            created_at = cls._parse_datetime_value(row.get("createdAt"))
            created_text = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
            title = str(row.get("title") or "-").strip()
            record_id = str(row.get("recordId") or "-").strip()
            overdue_minutes = cls._safe_int(row.get("overdueMinutes")) or 0
            lines.append(f"{index}. [{created_text}] {title}（记录ID: {record_id}，超时: {overdue_minutes}分钟）")
        return "\n".join(lines) if lines else "暂无明细"

    @classmethod
    def _collect_person_overdue_data(
        cls,
        db: Session,
        *,
        config: dict[str, Any],
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        统计按人聚合的超时记录。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :return: 统计结果。
        """
        person_field = str(config.get("personField") or "").strip()
        time_field = str(config.get("timeField") or "").strip()
        threshold_minutes = max(int(config.get("thresholdMinutes") or 30), 1)
        if not person_field:
            raise ValueError("人员字段(personField)未配置")
        if not time_field:
            raise ValueError("时间字段(timeField)未配置")

        records = cls.query_bitable_records(config)
        now = datetime.now()
        target_user = cls._resolve_target_user(db, user_id=user_id, email=email)
        target_email = cls._normalize_email(email or getattr(target_user, "email", ""))
        target_user_id = int(target_user.user_id) if target_user else (user_id or None)

        grouped: dict[str, list[dict[str, Any]]] = {}
        skipped_no_person = 0
        skipped_no_time = 0
        skipped_not_overdue = 0
        overdue_rows = 0

        for record in records:
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            person_names = cls._extract_person_names(fields.get(person_field))
            if not person_names:
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
            row_payload = {
                "recordId": str(record.get("record_id") or record.get("recordId") or "").strip(),
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
            for person_name in person_names:
                grouped.setdefault(person_name, []).append(row_payload)
                overdue_rows += 1

        feishu_user_cache: dict[str, dict[str, Any] | None] = {}
        app_id = str(config.get("feishuAppId") or "").strip()
        app_secret = str(config.get("feishuAppSecret") or "").strip()
        people: list[dict[str, Any]] = []
        for person_name, person_rows in grouped.items():
            user = cls._resolve_sys_user_by_name(db, person_name)
            user_email = cls._normalize_email(getattr(user, "email", ""))
            user_id_value = int(user.user_id) if user else None
            if target_user_id and user_id_value != target_user_id:
                continue
            if target_email and user_email != target_email:
                continue
            feishu_user = None
            if user_email:
                if user_email not in feishu_user_cache:
                    feishu_user_cache[user_email] = cls.query_feishu_user_by_email(
                        app_id=app_id,
                        app_secret=app_secret,
                        email=user_email,
                    )
                feishu_user = feishu_user_cache.get(user_email)
            people.append(
                {
                    "personName": person_name,
                    "userId": user_id_value,
                    "userName": getattr(user, "user_name", None),
                    "nickName": getattr(user, "nick_name", None),
                    "email": user_email or None,
                    "feishuUser": feishu_user,
                    "overdueCount": len(person_rows),
                    "rows": sorted(person_rows, key=lambda item: item.get("overdueMinutes", 0), reverse=True),
                }
            )

        people.sort(key=lambda item: item.get("overdueCount") or 0, reverse=True)
        return {
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
            f"enabled={bool(config.get('enabled'))}"
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
    ) -> dict[str, Any]:
        """
        执行按人催办通知。

        :param db: 数据库会话。
        :param config: 人员催办配置。
        :param trigger_source: 触发来源，如 scheduler/manual。
        :param user_id: 可选用户ID过滤。
        :param email: 可选邮箱过滤。
        :return: 执行结果摘要。
        """
        if not bool(config.get("enabled")):
            logger.info(f"人员催办通知跳过: enabled=false, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "人员催办开关未启用"}

        push_ids = cls._normalize_push_ids(config.get("pushIds"))
        if not push_ids:
            logger.info(f"人员催办通知跳过: 未配置 pushIds, trigger={trigger_source}")
            return {"triggerSource": trigger_source, "skipped": True, "skipReason": "未配置催办推送渠道"}

        summary = cls._collect_person_overdue_data(db, config=config, user_id=user_id, email=email)
        message_template = str(config.get("messageTemplate") or "").strip() or cls.DEFAULT_PERSON_TEMPLATE
        max_rows_per_person = max(int(config.get("maxRowsPerPerson") or 20), 1)

        sent_people = 0
        sent_push_count = 0
        skipped_people = 0
        person_results: list[dict[str, Any]] = []
        for person in summary.get("people") or []:
            overdue_count = int(person.get("overdueCount") or 0)
            if overdue_count <= 0:
                skipped_people += 1
                continue
            rows = person.get("rows") if isinstance(person.get("rows"), list) else []
            rows_markdown = cls._build_rows_markdown(rows, max_rows_per_person)
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
            success_count = cls._send_push_messages(
                db,
                push_ids=push_ids,
                content=content,
                at_user_ids=at_user_ids,
            )
            sent_people += 1
            sent_push_count += success_count
            person_results.append(
                {
                    "personName": person.get("personName"),
                    "email": person.get("email"),
                    "overdueCount": overdue_count,
                    "pushSuccessCount": success_count,
                    "atOpenId": open_id or None,
                }
            )
            logger.info(
                f"人员催办发送完成: person={person.get('personName')}, overdue={overdue_count}, "
                f"push_success={success_count}, trigger={trigger_source}"
            )

        return {
            "triggerSource": trigger_source,
            "skipped": False,
            "personCount": summary.get("personCount"),
            "sentPeople": sent_people,
            "sentPushCount": sent_push_count,
            "skippedPeople": skipped_people,
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
        description = str(ticket.description or "").strip()
        if len(description) > 200:
            description = f"{description[:200]}..."
        return {
            "ticket_id": ticket.ticket_id,
            "ticket_no": ticket.ticket_no or "-",
            "ticket_title": ticket.title or "-",
            "project_name": ticket.merchant_name or "-",
            "module_name": ticket.module_name or "-",
            "ticket_status": ticket.status or "-",
            "assignee_name": ticket.current_assignee_name or "-",
            "customer_priority": ticket.customer_priority or "-",
            "internal_priority": ticket.internal_priority or "-",
            "source": ticket.source or "-",
            "description": description or "-",
            "sync_revision": sync_data.get("revision") or "-",
            "sync_source_system": sync_data.get("sourceSystem") or "-",
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

        push_ids = override_push_ids if override_push_ids else cls._normalize_push_ids(group_config.get("pushIds"))
        if not push_ids:
            logger.info("群推送跳过: pushIds 为空")
            return {"skipped": True, "skipReason": "未配置群推送渠道", "scene": scene}

        message_template = str(override_template or "").strip()
        if not message_template:
            manual_template = str(group_config.get("manualTemplate") or "").strip()
            default_template = str(group_config.get("template") or "").strip()
            message_template = manual_template if manual_trigger and manual_template else default_template

        template_variables = cls._build_group_ticket_variables(ticket, sync_summary=sync_summary)
        content = cls._render_template(message_template, template_variables, cls.DEFAULT_GROUP_TEMPLATE)
        push_success_count = cls._send_push_messages(db, push_ids=push_ids, content=content, at_user_ids=None)
        logger.info(
            f"群推送发送完成: ticket_no={ticket.ticket_no}, scene={scene}, "
            f"push_success_count={push_success_count}, push_count={len(push_ids)}"
        )
        return {
            "skipped": False,
            "scene": scene,
            "ticketNo": ticket.ticket_no,
            "pushCount": len(push_ids),
            "pushSuccessCount": push_success_count,
            "templateVariables": template_variables,
        }
