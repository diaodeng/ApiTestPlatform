"""工单同步自动化关注范围判定服务。"""
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket


@dataclass(frozen=True)
class TicketAutomationScopeDecision:
    """工单当前模块是否属于自动化关注范围的判定结果。"""

    eligible: bool
    reason: str
    matched_by: str
    matched_value: str
    module_id: int | None
    module_name: str
    module_code: str

    def to_audit_data(self) -> dict[str, Any]:
        """将判定结果转换为可写入工单扩展字段的审计数据。"""
        data = asdict(self)
        data["evaluated_at"] = datetime.now().isoformat(timespec="seconds")
        return data


@dataclass(frozen=True)
class TicketAutomationStatisticsScope:
    """统计查询使用的自动化关注范围条件。"""

    module_ids: list[int]
    module_name_includes: list[str]


class TicketAutomationScopeService:
    """统一判定同步工单是否允许进入 AI、自动化、自动推送和默认统计范围。"""

    CONFIG_KEY = "automationScope"
    AUDIT_KEY = "automation_scope"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        """构建自动化关注范围默认配置，默认关闭以保持历史行为。"""
        return {
            "enabled": False,
            "moduleIds": [],
            "moduleCodes": [],
            "moduleNameIncludes": [],
            "applyToStatisticsDefault": True,
        }

    @classmethod
    def normalize_config(cls, value: Any) -> dict[str, Any]:
        """
        规范化自动化关注范围配置。

        :param value: 原始 JSON 配置。
        :return: 包含模块 ID、模块名称关键字和统计默认开关的规范化配置。
        """
        source = value if isinstance(value, dict) else {}
        default = cls.default_config()
        module_ids: list[int] = []
        for item in source.get("moduleIds") if isinstance(source.get("moduleIds"), list) else []:
            try:
                module_id = int(item)
            except (TypeError, ValueError):
                continue
            if module_id > 0 and module_id not in module_ids:
                module_ids.append(module_id)
        module_codes: list[str] = []
        for item in source.get("moduleCodes") if isinstance(source.get("moduleCodes"), list) else []:
            code = str(item or "").strip()
            if code and code.casefold() not in {value.casefold() for value in module_codes}:
                module_codes.append(code)
        name_keywords: list[str] = []
        for item in source.get("moduleNameIncludes") if isinstance(source.get("moduleNameIncludes"), list) else []:
            keyword = str(item or "").strip()
            if keyword and keyword not in name_keywords:
                name_keywords.append(keyword)
        return {
            **default,
            "enabled": bool(source.get("enabled")),
            "moduleIds": module_ids,
            "moduleCodes": module_codes,
            "moduleNameIncludes": name_keywords,
            "applyToStatisticsDefault": source.get("applyToStatisticsDefault") is not False,
        }

    @classmethod
    def evaluate_module(
        cls,
        config: dict[str, Any] | None,
        *,
        module_id: Any = None,
        module_name: Any = None,
        module_code: Any = None,
    ) -> TicketAutomationScopeDecision:
        """
        根据已经映射完成的系统模块判定自动化关注范围。

        :param config: 完整同步自动化配置。
        :param module_id: 系统模块 ID。
        :param module_name: 当前系统模块名称。
        :param module_code: 当前系统模块业务编码，仅记录审计。
        :return: 可否进入自动化链路及命中依据。
        """
        scope = cls.normalize_config((config or {}).get(cls.CONFIG_KEY))
        normalized_module_id = None
        try:
            normalized_module_id = int(module_id) if module_id is not None else None
        except (TypeError, ValueError):
            normalized_module_id = None
        normalized_name = str(module_name or "").strip()
        normalized_code = str(module_code or "").strip()
        if not scope["enabled"]:
            return TicketAutomationScopeDecision(
                eligible=True,
                reason="自动化关注范围未启用",
                matched_by="scope_disabled",
                matched_value="",
                module_id=normalized_module_id,
                module_name=normalized_name,
                module_code=normalized_code,
            )
        if not scope["moduleIds"] and not scope["moduleCodes"] and not scope["moduleNameIncludes"]:
            return TicketAutomationScopeDecision(
                eligible=True,
                reason="自动化关注范围已启用但未配置模块条件",
                matched_by="scope_unrestricted",
                matched_value="",
                module_id=normalized_module_id,
                module_name=normalized_name,
                module_code=normalized_code,
            )
        if normalized_module_id in scope["moduleIds"]:
            return TicketAutomationScopeDecision(
                eligible=True,
                reason="模块ID命中自动化关注范围",
                matched_by="module_id",
                matched_value=str(normalized_module_id),
                module_id=normalized_module_id,
                module_name=normalized_name,
                module_code=normalized_code,
            )
        comparable_name = normalized_name.casefold()
        for keyword in scope["moduleNameIncludes"]:
            if keyword.casefold() in comparable_name:
                return TicketAutomationScopeDecision(
                    eligible=True,
                    reason="模块名称关键字命中自动化关注范围",
                    matched_by="module_name_contains",
                    matched_value=keyword,
                    module_id=normalized_module_id,
                    module_name=normalized_name,
                    module_code=normalized_code,
                )
        comparable_code = normalized_code.casefold()
        for code in scope["moduleCodes"]:
            if comparable_code == code.casefold():
                return TicketAutomationScopeDecision(
                    eligible=True,
                    reason="模块Code命中自动化关注范围",
                    matched_by="module_code",
                    matched_value=code,
                    module_id=normalized_module_id,
                    module_name=normalized_name,
                    module_code=normalized_code,
                )
        return TicketAutomationScopeDecision(
            eligible=False,
            reason="当前模块未命中自动化关注范围",
            matched_by="unmatched",
            matched_value="",
            module_id=normalized_module_id,
            module_name=normalized_name,
            module_code=normalized_code,
        )

    @classmethod
    def evaluate_detected_module(
        cls,
        config: dict[str, Any] | None,
        detected: dict[str, Any] | None,
    ) -> TicketAutomationScopeDecision:
        """
        对同步字段映射后的模块候选值执行范围判定。

        :param config: 完整同步自动化配置。
        :param detected: 外部字段映射得到的内部字段字典。
        :return: 自动化关注范围判定结果。
        """
        values = detected if isinstance(detected, dict) else {}
        return cls.evaluate_module(
            config,
            module_id=values.get("moduleId"),
            module_name=values.get("moduleName"),
            module_code=values.get("moduleCode"),
        )

    @classmethod
    def evaluate_ticket(
        cls,
        db: Session,
        config: dict[str, Any] | None,
        ticket: Ticket,
    ) -> TicketAutomationScopeDecision:
        """
        对已入库工单的当前模块执行范围判定。

        :param db: 数据库会话。
        :param config: 完整同步自动化配置。
        :param ticket: 已入库的 ORM 工单实体。
        :return: 自动化关注范围判定结果。
        """
        return cls.evaluate_module(
            config,
            module_id=ticket.module_id,
            module_name=ticket.module_name,
            module_code=TicketDao.get_module_code_by_id(db, ticket.module_id),
        )

    @classmethod
    def resolve_statistics_scope(
        cls,
        db: Session,
        config: dict[str, Any] | None,
    ) -> TicketAutomationStatisticsScope | None:
        """将配置转换为统计查询条件；未启用或未配置条件时返回不限制。"""
        scope = cls.normalize_config((config or {}).get(cls.CONFIG_KEY))
        if not scope["enabled"] or not scope["applyToStatisticsDefault"]:
            return None
        if not scope["moduleIds"] and not scope["moduleCodes"] and not scope["moduleNameIncludes"]:
            return None
        return TicketAutomationStatisticsScope(
            module_ids=TicketDao.resolve_module_ids_by_scope(
                db,
                module_ids=scope["moduleIds"],
                module_codes=scope["moduleCodes"],
                module_name_includes=scope["moduleNameIncludes"],
            ),
            module_name_includes=scope["moduleNameIncludes"],
        )

    @classmethod
    def attach_audit_data(
        cls,
        extra_data: dict[str, Any] | None,
        decision: TicketAutomationScopeDecision,
    ) -> dict[str, Any]:
        """
        将范围判定写入工单扩展字段，供后续同步、推送与排障复用。

        :param extra_data: 原始工单扩展字段。
        :param decision: 当前范围判定结果。
        :return: 带有 automation_scope 审计信息的新扩展字段。
        """
        result = dict(extra_data or {}) if isinstance(extra_data, dict) else {}
        result[cls.AUDIT_KEY] = decision.to_audit_data()
        return result

    @classmethod
    def resolve_statistics_scope_module_ids(
        cls,
        db: Session,
        config: dict[str, Any] | None,
    ) -> list[int] | None:
        """
        将关注范围配置解析为统计查询可使用的系统模块 ID。

        :param db: 数据库会话。
        :param config: 完整同步自动化配置。
        :return: 未启用默认统计范围时返回 None；启用时返回允许统计的模块 ID 列表。
        """
        scope = cls.normalize_config((config or {}).get(cls.CONFIG_KEY))
        if not scope["enabled"] or not scope["applyToStatisticsDefault"]:
            return None
        return TicketDao.resolve_module_ids_by_scope(
            db,
            module_ids=scope["moduleIds"],
            module_codes=scope["moduleCodes"],
            module_name_includes=scope["moduleNameIncludes"],
        )
