"""工单可配置趋势指标的定义、实时聚合和快照行构造服务。"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.util.ticket_statistic_condition_util import match_conditions


class TicketCustomMetricService:
    """只接受白名单字段的指标定义，避免配置直接参与 SQL。"""

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
    }

    @classmethod
    def get_definitions(cls, db: Session) -> dict[str, Any]:
        """返回前端配置和展示所需的字段白名单及启用指标。"""
        config = TicketSyncConfigService.load_sync_config(db)
        configured_fields = config.get("statisticFieldKeys") or list(cls.FIELD_REGISTRY)
        return {
            "availableFields": [{"key": key, **value} for key, value in cls.FIELD_REGISTRY.items() if key in configured_fields],
            "metrics": [item for item in config.get("customTrendMetrics", []) if item.get("enabled")],
            "definitionRevision": cls.definition_revision(config.get("customTrendMetrics", [])),
        }

    @staticmethod
    def definition_revision(metrics: Any) -> str:
        """生成定义内容版本，用于识别需补跑快照的配置变更。"""
        text = json.dumps(metrics if isinstance(metrics, list) else [], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def selected_metrics(cls, db: Session, metric_codes: list[str] | None = None) -> list[dict[str, Any]]:
        """读取已启用且被本次请求选择的指标。"""
        metrics = cls.get_definitions(db)["metrics"]
        if metric_codes is None:
            return metrics
        allowed = set(metric_codes)
        return [item for item in metrics if item.get("metricCode") in allowed]

    @classmethod
    def evaluate_ticket(cls, ticket: Any, metric: dict[str, Any]) -> list[dict[str, str]]:
        """计算一张工单命中的指标分组，exclusive 仅保留最高优先级组。"""
        source = {field_key: getattr(ticket, definition["attribute"], None) for field_key, definition in cls.FIELD_REGISTRY.items()}
        matches = [group for group in metric.get("groups", []) if match_conditions(source, group.get("conditions"), group.get("conditionMode", "all"))]
        if str(metric.get("overlapMode") or "allow") == "exclusive" and matches:
            matches = [sorted(matches, key=lambda item: int(item.get("priority") or 0), reverse=True)[0]]
        return [{"groupCode": str(group["groupCode"]), "groupLabel": str(group.get("label") or group["groupCode"])} for group in matches]

    @classmethod
    def build_realtime_series(cls, db: Session, rows: list[Any], bucket_getter: Any, metric_codes: list[str] | None) -> list[dict[str, Any]]:
        """按提交时间桶聚合被选择的自定义指标。"""
        metrics = cls.selected_metrics(db, metric_codes)
        aggregate: dict[tuple[str, str, str], int] = defaultdict(int)
        labels: dict[tuple[str, str], tuple[str, str]] = {}
        for ticket in rows:
            bucket = bucket_getter(ticket)
            if not bucket:
                continue
            for metric in metrics:
                for group in cls.evaluate_ticket(ticket, metric):
                    aggregate[(str(bucket), metric["metricCode"], group["groupCode"])] += 1
                    labels[(metric["metricCode"], group["groupCode"])] = (metric["label"], group["groupLabel"])
        result = []
        for metric in metrics:
            metric_rows = []
            for group in metric.get("groups", []):
                group_code = str(group["groupCode"])
                metric_rows.append({"groupCode": group_code, "groupLabel": str(group.get("label") or group_code), "countsByBucket": {bucket: aggregate.get((bucket, metric["metricCode"], group_code), 0) for bucket in {key[0] for key in aggregate}}})
            result.append({"metricCode": metric["metricCode"], "label": metric["label"], "groups": metric_rows})
        return result

    @classmethod
    def build_snapshot_rows(cls, db: Session, rows: list[Any], snapshot_scope: str, definition_revision: str) -> list[dict[str, Any]]:
        """将一批已限定时间范围的新增工单计算为通用指标快照行。"""
        metrics = cls.selected_metrics(db)
        counts: dict[tuple[int, int, str, str, str], int] = defaultdict(int)
        labels: dict[tuple[str, str], tuple[str, str]] = {}
        for ticket in rows:
            project_id, module_id, issue_type_id = (0, 0, "") if snapshot_scope == "all" else (int(getattr(ticket, "project_id", 0) or 0), int(getattr(ticket, "module_id", 0) or 0), str(getattr(ticket, "issue_type_id", "") or ""))
            for metric in metrics:
                for group in cls.evaluate_ticket(ticket, metric):
                    counts[(project_id, module_id, issue_type_id, metric["metricCode"], group["groupCode"])] += 1
                    labels[(metric["metricCode"], group["groupCode"])] = (metric["label"], group["groupLabel"])
        return [{"snapshot_scope": snapshot_scope, "project_id": key[0], "module_id": key[1], "issue_type_id": key[2], "metric_code": key[3], "group_code": key[4], "metric_label": labels[(key[3], key[4])][0], "group_label": labels[(key[3], key[4])][1], "count": count, "definition_revision": definition_revision} for key, count in counts.items()]
