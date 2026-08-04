"""工单自定义统计方案的字段白名单与配置归一化。"""
from __future__ import annotations

import re
from typing import Any


class TicketCustomStatisticsDefinitionService:
    """维护统计方案允许使用的字段、时间口径和安全规则配置。"""

    PROFILE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    CONDITION_OPERATORS = {"equals", "contains", "in", "regex", "is_empty", "is_not_empty"}
    TIME_RANGE_MODES = {"today", "yesterday", "rolling_days", "current_week", "previous_week", "custom"}
    SEND_MODES = {"push_config", "feishu_app", "hybrid"}
    MESSAGE_FORMATS = {"text", "feishu_card"}
    FIELD_REGISTRY = {
        "issueTypeId": {"attribute": "issue_type_id", "label": "工单类型"},
        "isProblem": {"attribute": "is_problem", "label": "是否问题"},
        "status": {"attribute": "status", "label": "工单状态"},
        "source": {"attribute": "source", "label": "来源"},
        "rootCauseType": {"attribute": "root_cause_type", "label": "根因分类"},
        "solutionType": {"attribute": "solution_type", "label": "解决方式"},
        "resolutionCode": {"attribute": "resolution_code", "label": "关闭结果"},
        "internalPriority": {"attribute": "internal_priority", "label": "内部优先级"},
        "projectId": {"attribute": "project_id", "label": "项目"},
        "moduleId": {"attribute": "module_id", "label": "模块"},
        "moduleName": {"attribute": "module_name", "label": "模块名称"},
        "problemPatternCode": {"attribute": "problem_pattern_code", "label": "细分问题"},
        "processedAt": {"attribute": "processed_at", "label": "形成结论时间"},
        "hasConclusion": {"attribute": None, "label": "是否有结论"},
    }
    TIME_FIELD_REGISTRY = {
        "submitTime": "提交时间",
        "createTime": "创建时间",
        "firstResponseAt": "首次响应时间",
        "processedAt": "形成结论时间",
        "resolvedAt": "处置完成时间",
        "closedAt": "关闭时间",
    }

    @classmethod
    def get_definitions(cls) -> dict[str, Any]:
        """返回前端配置统计方案所需的字段和枚举。"""
        return {
            "fields": [{"key": key, **value} for key, value in cls.FIELD_REGISTRY.items()],
            "timeFields": [{"key": key, "label": label} for key, label in cls.TIME_FIELD_REGISTRY.items()],
            "operators": sorted(cls.CONDITION_OPERATORS),
            "timeRangeModes": sorted(cls.TIME_RANGE_MODES),
        }

    @classmethod
    def build_ticket_source(cls, ticket: Any) -> dict[str, Any]:
        """构造仅包含白名单字段的规则匹配数据源。"""
        source = {
            field_key: getattr(ticket, definition["attribute"], None)
            for field_key, definition in cls.FIELD_REGISTRY.items()
            if definition["attribute"]
        }
        source["hasConclusion"] = "true" if source.get("processedAt") else "false"
        return source

    @classmethod
    def normalize_profiles(cls, value: Any) -> list[dict[str, Any]]:
        """归一化统计方案，拒绝未注册字段、无效规则和重复编码。"""
        profiles: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        for item in value if isinstance(value, list) else []:
            if not isinstance(item, dict):
                continue
            profile_code = str(item.get("profileCode") or item.get("profile_code") or "").strip()
            if not cls.PROFILE_CODE_PATTERN.fullmatch(profile_code) or profile_code in seen_codes:
                continue
            profiles.append(
                {
                    "profileCode": profile_code,
                    "label": str(item.get("label") or profile_code).strip() or profile_code,
                    "enabled": bool(item.get("enabled", True)),
                    "timeField": cls.normalize_time_field(item.get("timeField")),
                    "timeRange": cls.normalize_time_range(item.get("timeRange")),
                    "scope": cls.normalize_scope(item.get("scope")),
                    "grouping": cls.normalize_grouping(item.get("grouping")),
                    "notification": cls.normalize_notification(item.get("notification")),
                }
            )
            seen_codes.add(profile_code)
        return profiles

    @classmethod
    def normalize_time_field(cls, value: Any) -> str:
        """返回受支持的工单时间字段编码。"""
        field = str(value or "submitTime").strip()
        return field if field in cls.TIME_FIELD_REGISTRY else "submitTime"

    @classmethod
    def normalize_time_range(cls, value: Any) -> dict[str, Any]:
        """归一化相对或固定时间范围配置。"""
        source = value if isinstance(value, dict) else {}
        mode = str(source.get("mode") or "today").strip().lower()
        mode = mode if mode in cls.TIME_RANGE_MODES else "today"
        rolling_days = min(max(cls.to_int(source.get("rollingDays"), 1), 1), 90)
        return {
            "mode": mode,
            "rollingDays": rolling_days,
            "startTime": str(source.get("startTime") or "").strip(),
            "endTime": str(source.get("endTime") or "").strip(),
        }

    @classmethod
    def normalize_scope(cls, value: Any) -> dict[str, Any]:
        """归一化 SQL 可安全处理的范围筛选项。"""
        source = value if isinstance(value, dict) else {}
        return {
            "projectIds": cls.normalize_positive_ints(source.get("projectIds")),
            "moduleIds": cls.normalize_positive_ints(source.get("moduleIds")),
            "moduleCodes": cls.normalize_texts(source.get("moduleCodes")),
            "issueTypeIds": cls.normalize_texts(source.get("issueTypeIds")),
            "problemPatternCodes": cls.normalize_texts(source.get("problemPatternCodes")),
        }

    @classmethod
    def normalize_grouping(cls, value: Any) -> dict[str, Any]:
        """归一化按字段或按规则的分组定义。"""
        source = value if isinstance(value, dict) else {}
        mode = str(source.get("mode") or "field").strip().lower()
        source_field = str(source.get("sourceField") or "status").strip()
        if source_field not in cls.FIELD_REGISTRY:
            source_field = "status"
        return {
            "mode": "rules" if mode == "rules" else "field",
            "sourceField": source_field,
            "overlapMode": "exclusive" if str(source.get("overlapMode") or "allow").lower() == "exclusive" else "allow",
            "includeUnmatched": bool(source.get("includeUnmatched", True)),
            "groups": cls.normalize_rule_groups(source.get("groups")),
        }

    @classmethod
    def normalize_rule_groups(cls, value: Any) -> list[dict[str, Any]]:
        """归一化规则分组，规则只允许命中字段注册表。"""
        groups: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        for index, group in enumerate(value if isinstance(value, list) else []):
            if not isinstance(group, dict):
                continue
            group_code = str(group.get("groupCode") or "").strip()
            if not cls.PROFILE_CODE_PATTERN.fullmatch(group_code) or group_code in seen_codes:
                continue
            conditions: list[dict[str, Any]] = []
            for condition in group.get("conditions") if isinstance(group.get("conditions"), list) else []:
                if not isinstance(condition, dict):
                    continue
                field = str(condition.get("sourceField") or "").strip()
                operator = str(condition.get("operator") or "equals").strip().lower()
                values = (
                    condition.get("matchValues")
                    if isinstance(condition.get("matchValues"), list)
                    else [condition.get("matchValue")]
                )
                normalized_values = cls.normalize_texts(values)
                if field not in cls.FIELD_REGISTRY or operator not in cls.CONDITION_OPERATORS:
                    continue
                if not normalized_values and operator not in {"is_empty", "is_not_empty"}:
                    continue
                conditions.append(
                    {
                        "sourceField": field,
                        "operator": operator,
                        "matchValues": [] if operator in {"is_empty", "is_not_empty"} else normalized_values,
                    }
                )
            if not conditions:
                continue
            groups.append(
                {
                    "groupCode": group_code,
                    "label": str(group.get("label") or group_code).strip() or group_code,
                    "priority": cls.to_int(group.get("priority"), (len(value) - index) * 10),
                    "conditionMode": "any" if str(group.get("conditionMode") or "all").lower() == "any" else "all",
                    "conditions": conditions,
                }
            )
            seen_codes.add(group_code)
        return groups

    @classmethod
    def normalize_notification(cls, value: Any) -> dict[str, Any]:
        """归一化通知渠道、格式和明细数量配置。"""
        source = value if isinstance(value, dict) else {}
        send_mode = str(source.get("sendMode") or "push_config").strip().lower()
        message_format = str(source.get("messageFormat") or "text").strip().lower()
        return {
            "enabled": bool(source.get("enabled", False)),
            "sendMode": send_mode if send_mode in cls.SEND_MODES else "push_config",
            "pushIds": cls.normalize_positive_ints(source.get("pushIds")),
            "appChatIds": cls.normalize_texts(source.get("appChatIds")),
            "appId": str(source.get("appId") or "").strip(),
            "appSecret": str(source.get("appSecret") or "").strip(),
            "messageFormat": message_format if message_format in cls.MESSAGE_FORMATS else "text",
            "messageTemplate": str(source.get("messageTemplate") or "").strip(),
            "includeTopTickets": bool(source.get("includeTopTickets", False)),
            "topTicketLimit": min(max(cls.to_int(source.get("topTicketLimit"), 10), 1), 20),
        }

    @staticmethod
    def normalize_texts(value: Any) -> list[str]:
        """将列表或逗号分隔值转为去重文本数组。"""
        source = value.split(",") if isinstance(value, str) else value if isinstance(value, list) else []
        result: list[str] = []
        for item in source:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @classmethod
    def normalize_positive_ints(cls, value: Any) -> list[int]:
        """将列表或逗号分隔值转为去重正整数数组。"""
        result: list[int] = []
        for item in cls.normalize_texts(value):
            parsed = cls.to_int(item, 0)
            if parsed > 0 and parsed not in result:
                result.append(parsed)
        return result

    @staticmethod
    def to_int(value: Any, default: int) -> int:
        """安全转换整数。"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
