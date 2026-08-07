"""外部接口字段到工单类型的规则映射服务。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.ticket.util.ticket_statistic_condition_util import match_value


@dataclass(frozen=True)
class ExternalClassificationMatch:
    """外部分类映射命中结果。"""

    rule_id: str
    issue_type_id: str
    issue_type_name: str
    source_field: str
    source_value: Any
    operator: str


class TicketExternalClassificationMappingService:
    """只负责读取外部元数据并匹配配置，不直接写数据库。"""

    @classmethod
    def match(cls, config: dict[str, Any], sync_object: Any) -> ExternalClassificationMatch | None:
        """按优先级匹配外部接口字段，返回第一条有效规则。"""
        rules = config.get("externalClassificationMappings") if isinstance(config, dict) else []
        issue_types = (config.get("statClassification") or {}).get("issueTypes") if isinstance(config, dict) else []
        labels = {str(row.get("value") or "").strip(): str(row.get("label") or "").strip() for row in issue_types if isinstance(row, dict)}
        extra_data = getattr(sync_object, "extra_data", None)
        extra_data = extra_data if isinstance(extra_data, dict) else {}
        mapping = extra_data.get("external_field_mapping") if isinstance(extra_data.get("external_field_mapping"), dict) else {}
        raw_payload = getattr(sync_object, "raw_payload", None)
        raw_payload = raw_payload if isinstance(raw_payload, dict) else {}
        fields = {**raw_payload, **mapping}
        for rule in sorted((item for item in rules if isinstance(item, dict) and item.get("enabled", True)), key=lambda item: int(item.get("priority") or 0), reverse=True):
            source_field = str(rule.get("sourceField") or "").strip()
            issue_type_id = str(rule.get("issueTypeId") or "").strip()
            if not source_field or issue_type_id not in labels or source_field not in fields:
                continue
            source_value = fields.get(source_field)
            if match_value(source_value, str(rule.get("operator") or "equals"), rule.get("matchValues")):
                return ExternalClassificationMatch(
                    rule_id=str(rule.get("ruleId") or "").strip(), issue_type_id=issue_type_id,
                    issue_type_name=labels[issue_type_id] or issue_type_id, source_field=source_field,
                    source_value=source_value, operator=str(rule.get("operator") or "equals").strip(),
                )
        return None
