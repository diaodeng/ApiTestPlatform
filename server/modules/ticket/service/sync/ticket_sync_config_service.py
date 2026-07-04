"""
工单同步配置管理服务：默认配置工厂、配置规范化和持久化。
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.do.config_do import SysConfig
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil


class TicketSyncConfigService:
    """工单同步自动化配置管理。"""

    CONFIG_KEY = "ticket.sync.automation"

    # --- constants migrated from TicketSyncService ---

    DEFAULT_GROUP_PUSH_AUTO_STATUSES = [
        "2. 1.5线处理",
        "3. 待产研处理",
        "4. 产研处理中",
    ]
    DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS = [
        "ticketNo",
        "description",
        "internalPriority",
        "ticketVender",
        "ticketModle",
        "createTime",
        "reporterName",
    ]
    DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS = [
        {"fieldName": "ticketNo", "label": "工单号", "required": True, "category": "basic"},
        {"fieldName": "title", "label": "工单标题", "required": False, "category": "basic"},
        {"fieldName": "description", "label": "问题描述", "required": True, "category": "basic"},
        {"fieldName": "customerPriority", "label": "对方优先级", "required": False, "category": "priority"},
        {"fieldName": "internalPriority", "label": "内部优先级", "required": True, "category": "priority"},
        {"fieldName": "ticketVender", "label": "商家/供应商", "required": True, "category": "mapping"},
        {"fieldName": "ticketModle", "label": "模块", "required": True, "category": "mapping"},
        {"fieldName": "ticketStatus", "label": "外部状态", "required": False, "category": "mapping"},
        {"fieldName": "ticketStore", "label": "门店信息", "required": False, "category": "mapping"},
        {"fieldName": "ticketPos", "label": "POS号", "required": False, "category": "mapping"},
        {"fieldName": "ticketSco", "label": "SCO号", "required": False, "category": "mapping"},
        {"fieldName": "createTime", "label": "创建时间", "required": True, "category": "time"},
        {"fieldName": "reporterName", "label": "报告人/1线处理人", "required": True, "category": "person"},
        {"fieldName": "reporterEmail", "label": "报告人邮箱", "required": False, "category": "person"},
        {"fieldName": "currentAssigneeName", "label": "当前处理人", "required": False, "category": "person"},
        {"fieldName": "currentAssigneeEmail", "label": "当前处理人邮箱", "required": False, "category": "person"},
        {"fieldName": "internalOwner", "label": "内部负责人", "required": False, "category": "person"},
        {"fieldName": "internalOwnerEmail", "label": "内部负责人邮箱", "required": False, "category": "person"},
        {"fieldName": "ticketUrl", "label": "工单链接", "required": False, "category": "basic"},
        {"fieldName": "recordId", "label": "多维表格记录ID", "required": False, "category": "source"},
        {"fieldName": "reason", "label": "原因说明", "required": False, "category": "basic"},
        {"fieldName": "stepReason", "label": "排查过程", "required": False, "category": "basic"},
    ]
    DEFAULT_TICKET_STAT_CLASSIFICATIONS = {
        "issueTypes": [
            {"value": "system_bug", "label": "系统Bug", "isProblem": True},
            {"value": "data_error", "label": "数据错误", "isProblem": True},
            {"value": "config_issue", "label": "配置问题", "isProblem": True},
            {"value": "performance_issue", "label": "性能问题", "isProblem": True},
            {"value": "support_consulting", "label": "支持咨询", "isProblem": False},
            {"value": "requirement_consulting", "label": "需求咨询", "isProblem": False},
            {"value": "user_operation", "label": "用户操作问题", "isProblem": False},
            {"value": "api_exception", "label": "接口异常", "isProblem": True},
        ],
        "rootCauseTypes": [
            {"value": "code_defect", "label": "代码缺陷"},
            {"value": "config_error", "label": "配置错误"},
            {"value": "data_exception", "label": "数据异常"},
            {"value": "third_party", "label": "第三方问题"},
            {"value": "network_issue", "label": "网络问题"},
            {"value": "environment_issue", "label": "环境问题"},
            {"value": "operation_mistake", "label": "操作失误"},
            {"value": "requirement_design", "label": "需求设计问题"},
            {"value": "unknown", "label": "未知"},
        ],
        "solutionTypes": [
            {"value": "code_fix", "label": "代码修复"},
            {"value": "config_fix", "label": "配置修复"},
            {"value": "data_fix", "label": "数据修复"},
            {"value": "temporary_workaround", "label": "临时处理"},
            {"value": "manual_process", "label": "人工处理"},
            {"value": "no_action", "label": "无需处理"},
        ],
        "resolutions": [
            {"value": "fixed", "label": "已修复", "isProblem": True},
            {"value": "non_problem", "label": "非问题", "isProblem": False},
            {"value": "data_processed", "label": "数据已处理", "isProblem": True},
            {"value": "config_fixed", "label": "配置已修复", "isProblem": True},
            {"value": "user_canceled", "label": "用户撤销", "isProblem": False},
            {"value": "duplicated", "label": "重复工单", "isProblem": False},
            {"value": "cannot_reproduce", "label": "无法复现", "isProblem": None},
            {"value": "as_designed", "label": "需求如此", "isProblem": False},
            {"value": "transferred", "label": "已转其他团队", "isProblem": None},
        ],
        "problemPatterns": [
            {
                "value": "memory_leak",
                "label": "内存泄露",
                "moduleCode": "",
                "issueTypeId": "performance_issue",
                "isProblem": True,
                "rootCauseType": "code_defect",
                "resolutionCode": "fixed",
                "description": "进程内存持续增长、未释放或最终 OOM 的问题模式。",
                "positiveExamples": ["内存泄露", "内存泄漏", "memory leak", "OOM"],
                "negativeExamples": ["单次内存高峰", "磁盘空间不足"],
                "enabled": True,
            },
            {
                "value": "coupon_280_paper_rule",
                "label": "280开头券为纸质券规则说明",
                "moduleCode": "coupon",
                "issueTypeId": "support_consulting",
                "isProblem": False,
                "rootCauseType": "requirement_design",
                "resolutionCode": "as_designed",
                "description": "用户反馈 280 开头券不能按电子券处理，实际业务规则定义为纸质券。",
                "positiveExamples": ["280开头券", "纸质券", "券规则说明"],
                "negativeExamples": ["电子券接口报错", "券配置错误"],
                "enabled": True,
            },
        ],
    }

    # --- migrated from TicketSyncService._default_sync_config ---

    @classmethod
    def default_sync_config(cls) -> dict[str, Any]:
        return {
            "autoRunOnSync": False,
            "autoTranslateOnSync": True,
            "defaultPullLimit": 50,
            "feishuAuth": cls.default_feishu_auth_config(),
            "bitableCommon": cls.default_bitable_common_config(),
            "externalFieldModel": cls.default_external_field_model_config(),
            "externalSyncBitable": cls.default_external_sync_bitable_config(),
            "remoteSync": cls.default_remote_sync_config(),
            "bitablePull": cls.default_bitable_pull_config(),
            "groupPush": cls.default_group_push_config(),
            "messageSync": cls.default_message_sync_config(),
            "personReminder": cls.default_person_reminder_config(),
            "summaryReport": cls.default_summary_report_config(),
            "statClassification": cls.default_stat_classification_config(),
            "aiClassification": cls.default_ai_classification_config(),
            "externalSyncRequiredFields": list(cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS),
            "projectMappings": [],
            "moduleMappings": [],
            "vendorMappings": [],
            "storeMappings": [],
            "statusMappings": [],
            "assigneeMappings": [],
            "posPatterns": [r"(?:^|[^A-Z0-9])POS[^0-9]{0,3}(\d{1,10})(?:[^A-Z0-9]|$)"],
            "scoPatterns": [r"(?:^|[^A-Z0-9])SCO[^0-9]{0,3}(\d{1,10})(?:[^A-Z0-9]|$)"],
            "versionPatterns": [
                r"(?:版本|version|app[_\\s-]*version)[:：\\s-]*([A-Za-z0-9._/-]+)",
            ],
            "logPullDefaults": {
                "commandDataType": 1,
                "fileMaxSize": 500,
                "zipMaxSize": 500,
                "storageMode": "local",
                "rangeBeforeMinutes": 10,
                "rangeAfterMinutes": 10,
                "autoAiEnabled": False,
                "aiAgentCode": "",
                "aiProviderCode": "",
            },
            "promptTemplates": {
                "classificationHint": "预留给后续 AI 识别场景，当前版本由可配置规则和正则完成识别。",
            },
        }

    # --- migrated from TicketSyncService._default_feishu_auth_config ---

    @classmethod
    def default_feishu_auth_config(cls) -> dict[str, Any]:
        """
        构建飞书应用统一凭证默认配置。

        :return: 统一凭证配置默认值。
        """
        return {
            "appId": "",
            "appSecret": "",
        }

    # --- migrated from TicketSyncService._default_bitable_common_config ---

    @classmethod
    def default_bitable_common_config(cls) -> dict[str, Any]:
        """
        构建飞书多维表格公共配置。

        :return: 公共多维表格配置默认值。
        """
        return {
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "pageSize": 500,
            "filterFormula": "",
        }

    # --- migrated from TicketSyncService._default_external_field_model_config ---

    @classmethod
    def default_external_field_model_config(cls) -> dict[str, Any]:
        """
        构建外部工单字段模型默认配置。

        :return: 外部字段模型默认值。
        """
        return {
            "fields": [dict(item) for item in cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS],
        }

    # --- migrated from TicketSyncService._default_external_sync_bitable_config ---

    @classmethod
    def default_external_sync_bitable_config(cls) -> dict[str, Any]:
        """
        构建外部同步多维表格补充查询默认配置。

        :return: 外部同步多维表格配置默认值。
        """
        return {
            "enabled": False,
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
        }

    # --- migrated from TicketSyncService._default_bitable_pull_config ---

    @classmethod
    def default_bitable_pull_config(cls) -> dict[str, Any]:
        """
        构建飞书多维表格主动拉取默认配置。

        :return: 主动拉取配置默认值。
        """
        return {
            "enabled": False,
            "appId": "",
            "appSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "pageSize": 200,
            "filterFormula": "",
            "fieldMappings": [],
            "sourceSystem": "feishu_bitable_pull",
            "ticketNoField": "ticketNo",
            "updatedAtField": "",
            "sortField": "",
            "includeRecordUrl": True,
            "createdAfter": "",
            "createdBefore": "",
            "forceSync": False,
            "sendGroupMessage": None,
            "autoAppendTimeFilter": True,
            "automation": {
                "autoIdentify": True,
                "autoLogPull": False,
                "autoAiAnalysis": False,
                "autoTranslate": True,
            },
        }

    # --- migrated from TicketSyncService._default_group_push_config ---

    @classmethod
    def default_group_push_config(cls) -> dict[str, Any]:
        """
        构建工单群推送默认配置。

        :return: 群推送配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "pushIds": [],
            "appChatIds": [],
            "autoPushStatuses": list(cls.DEFAULT_GROUP_PUSH_AUTO_STATUSES),
            "priorityRoutes": [],
            "sendAfterExternalSync": False,
            "sendAfterRemotePull": False,
            "autoSendAfterTime": "",
            "template": "",
            "manualTemplate": "",
        }

    # --- migrated from TicketSyncService._default_message_sync_config ---

    @classmethod
    def default_message_sync_config(cls) -> dict[str, Any]:
        """
        构建工单评论多端同步默认配置。

        :return: 评论同步配置默认值。
        """
        return {
            "enabled": False,
            "feishuEventEnabled": False,
            "feishuWsEnabled": False,
            "feishuWsEncryptKey": "",
            "feishuWsVerificationToken": "",
            "allowedChatIds": [],
            "ignoreBotOpenIds": [],
            "syncFeishuCommentToTicket": True,
            "syncFeishuCommentToBitable": False,
            "syncTicketCommentToBitable": False,
            "syncTicketCommentToFeishuThread": False,
            "syncBitableNewStepToFeishuThread": False,
            "bitableStepReasonField": "stepReason",
            "bitableTicketNoField": "ticketNo",
            "appendStepReasonFormat": "{date} {user}：{content}",
        }

    # --- migrated from TicketSyncService._default_person_reminder_config ---

    @classmethod
    def default_person_reminder_config(cls) -> dict[str, Any]:
        """
        构建按人催办默认配置。

        :return: 人维度催办配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "dataSource": "bitable",
            "pushIds": [],
            "appId": "",
            "appSecret": "",
            "feishuAppId": "",
            "feishuAppSecret": "",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "filterFormula": "",
            "personField": "",
            "timeField": "",
            "thresholdMinutes": 30,
            "messageTemplate": "",
            "rowsMarkdownTemplate": "",
            "maxRowsPerPerson": 20,
            "pageSize": 500,
        }

    # --- migrated from TicketSyncService._default_summary_report_config ---

    @classmethod
    def default_summary_report_config(cls) -> dict[str, Any]:
        """
        构建工单汇总通知默认配置。

        :return: 汇总通知配置默认值。
        """
        return {
            "enabled": False,
            "sendMode": "push_config",
            "dataSource": "local",
            "pushIds": [],
            "appChatIds": [],
            "appId": "",
            "appSecret": "",
            "timeField": "create_time",
            "appToken": "",
            "tableId": "",
            "viewId": "",
            "filterFormula": "",
            "statusField": "状态",
            "categoryField": "分类",
            "priorityField": "优先级",
            "bitableTimeField": "",
            "pageSize": 500,
            "aiEnabled": False,
            "aiProviderCode": "",
            "aiPromptCode": "",
            "windowMinutes": 60,
            "endDelayMinutes": 0,
            "startTime": "",
            "endTime": "",
            "includeClosed": True,
            "messageTemplate": "",
        }

    # --- migrated from TicketSyncService._default_remote_sync_config ---

    @classmethod
    def default_remote_sync_config(cls) -> dict[str, Any]:
        """
        构建远端工单同步默认配置。

        :return: 默认远端同步配置。
        """
        return {
            "enabled": False,
            "pullUrl": "",
            "ackUrl": "",
            "consumer": "",
            "sourceSystem": "public",
            "limit": 50,
            "includeClosed": True,
            "autoTranslateOnPull": True,
            "timeoutSec": 30,
            "headers": {
                "cookie": "",
                "authorization": "",
                "origin": "",
            },
        }

    # --- migrated from TicketSyncService._default_stat_classification_config ---

    @classmethod
    def default_stat_classification_config(cls) -> dict[str, Any]:
        """
        构建工单分类统计枚举默认配置。

        :return: 分类统计枚举配置。
        """
        return {
            "issueTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["issueTypes"]],
            "rootCauseTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["rootCauseTypes"]],
            "solutionTypes": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["solutionTypes"]],
            "resolutions": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["resolutions"]],
            "problemPatterns": [dict(item) for item in cls.DEFAULT_TICKET_STAT_CLASSIFICATIONS["problemPatterns"]],
        }

    # --- migrated from TicketSyncService._default_ai_classification_config ---

    @classmethod
    def default_ai_classification_config(cls) -> dict[str, Any]:
        """
        构建工单 AI 分类统计默认配置。

        :return: AI 分类统计配置。
        """
        return {
            "enabled": False,
            "runOnExternalSync": False,
            "runOnRemotePull": False,
            "runOnManualCreate": False,
            "runOnStatusChange": False,
            "statusChangeTriggerStatuses": [],
            "statusChangeForceReclassify": False,
            "providerCode": "",
            "promptCode": "ticket_stat_classify_default",
            "promptContent": "",
        }

    # --- migrated from TicketSyncService._normalize_stat_option_rows ---

    @classmethod
    def normalize_stat_option_rows(cls, value: Any, default_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        归一化可视化维护的统计枚举行。

        :param value: 前端提交的枚举行。
        :param default_rows: 默认枚举。
        :return: 去重后的枚举行。
        """
        source_rows = value if isinstance(value, list) else default_rows
        result: list[dict[str, Any]] = []
        seen_values: set[str] = set()
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            option_value = str(row.get("value") or row.get("code") or row.get("id") or "").strip()
            option_label = str(row.get("label") or row.get("name") or option_value).strip()
            if not option_value or option_value in seen_values:
                continue
            normalized_row: dict[str, Any] = {
                "value": option_value,
                "label": option_label or option_value,
            }
            if "isProblem" in row:
                raw_is_problem = row.get("isProblem")
                normalized_row["isProblem"] = raw_is_problem if isinstance(raw_is_problem, bool) else None
            elif "is_problem" in row:
                raw_is_problem = row.get("is_problem")
                normalized_row["isProblem"] = raw_is_problem if isinstance(raw_is_problem, bool) else None
            if str(row.get("remark") or "").strip():
                normalized_row["remark"] = str(row.get("remark") or "").strip()
            for extra_key in (
                "moduleCode",
                "issueTypeId",
                "rootCauseType",
                "resolutionCode",
                "description",
                "positiveExamples",
                "negativeExamples",
                "enabled",
            ):
                if extra_key in row:
                    normalized_row[extra_key] = row.get(extra_key)
            for snake_key, camel_key in (
                ("module_code", "moduleCode"),
                ("issue_type_id", "issueTypeId"),
                ("root_cause_type", "rootCauseType"),
                ("resolution_code", "resolutionCode"),
                ("positive_examples", "positiveExamples"),
                ("negative_examples", "negativeExamples"),
            ):
                if snake_key in row and camel_key not in normalized_row:
                    normalized_row[camel_key] = row.get(snake_key)
            result.append(normalized_row)
            seen_values.add(option_value)
        return result or [dict(item) for item in default_rows]

    # --- migrated from TicketSyncService._normalize_stat_classification_config ---

    @classmethod
    def normalize_stat_classification_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化工单分类统计配置。

        :param value: 原始配置。
        :return: 带默认值的配置。
        """
        source = value if isinstance(value, dict) else {}
        defaults = cls.default_stat_classification_config()
        return {
            "issueTypes": cls.normalize_stat_option_rows(
                source.get("issueTypes") or source.get("issue_types"),
                defaults["issueTypes"],
            ),
            "rootCauseTypes": cls.normalize_stat_option_rows(
                source.get("rootCauseTypes") or source.get("root_cause_types"),
                defaults["rootCauseTypes"],
            ),
            "solutionTypes": cls.normalize_stat_option_rows(
                source.get("solutionTypes") or source.get("solution_types"),
                defaults["solutionTypes"],
            ),
            "resolutions": cls.normalize_stat_option_rows(
                source.get("resolutions"),
                defaults["resolutions"],
            ),
            "problemPatterns": cls.normalize_stat_option_rows(
                source.get("problemPatterns") or source.get("problem_patterns"),
                defaults["problemPatterns"],
            ),
        }

    # --- migrated from TicketSyncService._normalize_ai_classification_config ---

    @classmethod
    def normalize_ai_classification_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化工单 AI 分类统计配置。

        :param value: 原始配置。
        :return: 带默认值的配置。
        """
        source = value if isinstance(value, dict) else {}
        defaults = cls.default_ai_classification_config()
        return {
            "enabled": bool(source.get("enabled", defaults["enabled"])),
            "runOnExternalSync": bool(source.get("runOnExternalSync", source.get("run_on_external_sync", False))),
            "runOnRemotePull": bool(source.get("runOnRemotePull", source.get("run_on_remote_pull", False))),
            "runOnManualCreate": bool(source.get("runOnManualCreate", source.get("run_on_manual_create", False))),
            "runOnStatusChange": bool(source.get("runOnStatusChange", source.get("run_on_status_change", False))),
            "statusChangeTriggerStatuses": cls.normalize_ai_classification_status_triggers(
                source.get("statusChangeTriggerStatuses", source.get("status_change_trigger_statuses"))
            ),
            "statusChangeForceReclassify": bool(
                source.get("statusChangeForceReclassify", source.get("status_change_force_reclassify", False))
            ),
            "providerCode": str(source.get("providerCode") or source.get("provider_code") or "").strip(),
            "promptCode": str(
                source.get("promptCode")
                or source.get("prompt_code")
                or defaults["promptCode"]
                or ""
            ).strip(),
            "promptContent": str(source.get("promptContent") or source.get("prompt_content") or "").strip(),
        }

    # --- migrated from TicketSyncService._normalize_ai_classification_status_triggers ---

    @classmethod
    def normalize_ai_classification_status_triggers(cls, value: Any) -> list[str]:
        """
        归一化状态变更触发 AI 分类统计的目标状态列表。

        :param value: 前端或历史配置提交的状态编码列表。
        :return: 去重后的状态编码列表。
        """
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            status = str(item or "").strip()
            if status and status not in normalized:
                normalized.append(status)
        return normalized

    # --- migrated from TicketSyncService._normalize_external_field_model_config ---

    @classmethod
    def normalize_external_field_model_config(cls, value: Any) -> dict[str, Any]:
        """
        归一化外部工单字段模型配置。

        :param value: 原始配置。
        :return: 归一化后的字段模型。
        """
        source = value if isinstance(value, dict) else {}
        source_fields = source.get("fields") if isinstance(source.get("fields"), list) else []
        normalized_fields: list[dict[str, Any]] = []
        seen_field_names: set[str] = set()
        for field in source_fields or cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS:
            if not isinstance(field, dict):
                continue
            field_name = str(field.get("fieldName") or field.get("value") or field.get("name") or "").strip()
            if not field_name or field_name in seen_field_names:
                continue
            normalized_fields.append(
                {
                    "fieldName": field_name,
                    "label": str(field.get("label") or field.get("name") or field_name).strip() or field_name,
                    "required": bool(field.get("required")),
                    "category": str(field.get("category") or "custom").strip() or "custom",
                    "description": str(field.get("description") or "").strip(),
                }
            )
            seen_field_names.add(field_name)
        if not normalized_fields:
            normalized_fields = [dict(item) for item in cls.DEFAULT_EXTERNAL_FIELD_MODEL_FIELDS]
        return {"fields": normalized_fields}

    # --- migrated from TicketSyncService._derive_required_fields_from_external_field_model ---

    @classmethod
    def derive_required_fields_from_external_field_model(cls, value: Any) -> list[str]:
        """
        根据外部字段模型推导必填字段列表。

        :param value: 外部字段模型配置。
        :return: 必填字段列表。
        """
        model_config = cls.normalize_external_field_model_config(value)
        required_fields: list[str] = []
        for item in model_config.get("fields") or []:
            if not isinstance(item, dict):
                continue
            if not bool(item.get("required")):
                continue
            field_name = str(item.get("fieldName") or "").strip()
            if field_name and field_name not in required_fields:
                required_fields.append(field_name)
        return required_fields or list(cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS)

    # --- migrated from TicketSyncService._normalize_bitable_filter_config ---

    @classmethod
    def normalize_bitable_filter_config(cls, value: Any) -> str | dict[str, Any]:
        """
        归一化飞书多维表格查询过滤配置。

        :param value: 页面保存的 JSON 字符串，或任务参数直接传入的 JSON 对象。
        :return: 字符串或对象；空值返回空字符串。
        """
        if isinstance(value, dict):
            return value
        if value in (None, ""):
            return ""
        return str(value or "").strip()

    # --- migrated from TicketSyncService._parse_bitable_filter_config ---

    @classmethod
    def parse_bitable_filter_config(cls, value: Any) -> dict[str, Any]:
        """
        将飞书多维表格过滤配置解析为条件对象。

        :param value: JSON 字符串或字典。
        :return: 可传给飞书 records/search 的 filter 对象；无效时返回空字典。
        """
        if isinstance(value, dict):
            return dict(value)
        if value in (None, ""):
            return {}
        try:
            parsed = json.loads(str(value or "").strip())
        except Exception as exc:
            raise ValueError("过滤条件格式错误，请填写飞书 records/search filter JSON") from exc
        return dict(parsed) if isinstance(parsed, dict) else {}

    # --- migrated from TicketSyncService._format_bitable_filter_config ---

    @classmethod
    def format_bitable_filter_config(cls, value: Any) -> str | dict[str, Any]:
        """
        按原输入形态输出过滤配置，兼容页面保存字符串和任务参数对象。

        :param value: 过滤条件对象。
        :return: JSON 字符串或对象。
        """
        if isinstance(value, dict):
            return value
        return ""

    # --- migrated from TicketSyncService._normalize_bitable_common_config ---

    @classmethod
    def normalize_bitable_common_config(cls, value: Any, *, feishu_auth: dict[str, Any]) -> dict[str, Any]:
        """
        归一化飞书多维表格公共配置。

        :param value: 原始公共配置。
        :param feishu_auth: 飞书统一凭证。
        :return: 归一化后的公共配置。
        """
        source = value if isinstance(value, dict) else {}
        config = {**cls.default_bitable_common_config(), **source}
        config["appId"] = str(config.get("appId") or "").strip()
        config["appSecret"] = str(config.get("appSecret") or "").strip()
        config["appToken"] = str(config.get("appToken") or "").strip()
        config["tableId"] = str(config.get("tableId") or "").strip()
        config["viewId"] = str(config.get("viewId") or "").strip()
        config["pageSize"] = min(max(SyncUtil.safe_int(config.get("pageSize")) or 500, 1), 500)
        config["filterFormula"] = cls.normalize_bitable_filter_config(config.get("filterFormula"))
        return config

    # --- migrated from TicketSyncService._apply_bitable_common_defaults ---

    @classmethod
    def apply_bitable_common_defaults(
        cls,
        config: dict[str, Any] | None,
        *,
        bitable_common: dict[str, Any],
        keep_filter_formula: bool = True,
    ) -> dict[str, Any]:
        """
        将公共多维表格配置补齐到具体业务配置中。

        :param config: 业务侧配置。
        :param bitable_common: 公共多维表格配置。
        :param keep_filter_formula: 是否保留业务侧的 filterFormula 覆盖。
        :return: 合并后的配置。
        """
        source = dict(config or {})
        for key in ("appId", "appSecret", "appToken", "tableId", "viewId"):
            if not str(source.get(key) or "").strip():
                source[key] = bitable_common.get(key)
        page_size = SyncUtil.safe_int(source.get("pageSize"))
        if page_size is None:
            source["pageSize"] = bitable_common.get("pageSize")
        else:
            source["pageSize"] = min(max(page_size, 1), 500)
        if keep_filter_formula and not cls.normalize_bitable_filter_config(source.get("filterFormula")):
            source["filterFormula"] = bitable_common.get("filterFormula")
        return source

    # --- migrated from TicketSyncService._resolve_bitable_runtime_config ---

    @classmethod
    def resolve_bitable_runtime_config(
        cls,
        config: dict[str, Any],
        section_key: str,
        default_config: dict[str, Any],
        *,
        keep_filter_formula: bool = True,
    ) -> dict[str, Any]:
        """
        解析运行时多维表格配置，只在真正执行飞书查询前继承公共配置。

        :param config: 完整同步配置。
        :param section_key: 业务配置段名称。
        :param default_config: 业务配置默认值。
        :param keep_filter_formula: 是否允许公共过滤公式兜底。
        :return: 已按“独立配置优先，公共配置兜底”合并后的运行时配置。
        """
        feishu_auth = config.get("feishuAuth") if isinstance(config.get("feishuAuth"), dict) else {}
        bitable_common = config.get("bitableCommon") if isinstance(config.get("bitableCommon"), dict) else {}
        section_config = config.get(section_key) if isinstance(config.get(section_key), dict) else {}
        runtime_config = {**default_config, **section_config}
        runtime_config = cls.apply_bitable_common_defaults(
            runtime_config,
            bitable_common=bitable_common,
            keep_filter_formula=keep_filter_formula,
        )
        if not str(runtime_config.get("appId") or "").strip():
            runtime_config["appId"] = str(feishu_auth.get("appId") or "").strip()
        if not str(runtime_config.get("appSecret") or "").strip():
            runtime_config["appSecret"] = str(feishu_auth.get("appSecret") or "").strip()
        return runtime_config

    # --- migrated from TicketSyncService._merge_non_empty_runtime_override ---

    @classmethod
    def merge_non_empty_runtime_override(
        cls,
        base_config: dict[str, Any],
        override_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        合并运行时覆盖配置，空字符串不覆盖已继承的公共配置。

        :param base_config: 已解析的基础运行时配置。
        :param override_config: 页面预览或定时任务传入的覆盖配置。
        :return: 合并后的运行时配置。
        """
        merged_config = dict(base_config or {})
        if not isinstance(override_config, dict):
            return merged_config
        for key, value in override_config.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged_config[key] = value
        return merged_config

    # --- migrated from TicketSyncService._normalize_bitable_field_mappings ---

    @classmethod
    def normalize_bitable_field_mappings(cls, value: Any) -> list[dict[str, Any]]:
        """
        归一化多维表格字段映射列表。

        :param value: 原始映射列表。
        :return: 归一化后的映射。
        """
        source_rows = value if isinstance(value, list) else []
        mappings: list[dict[str, Any]] = []
        seen_targets: set[str] = set()
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            source_field = str(row.get("sourceField") or row.get("from") or row.get("bitableField") or "").strip()
            target_field = FeishuBitableUtil.normalize_pull_target_field(
                row.get("targetField") or row.get("to") or row.get("externalField")
            )
            if not source_field or not target_field:
                continue
            unique_key = f"{source_field}->{target_field}"
            if unique_key in seen_targets:
                continue
            mappings.append(
                {
                    "sourceField": source_field,
                    "targetField": target_field,
                    "defaultValue": row.get("defaultValue"),
                    "joinSeparator": str(row.get("joinSeparator") or "").strip() or ",",
                }
            )
            seen_targets.add(unique_key)
        return mappings

    # --- migrated from TicketSyncService._normalize_bitable_pull_target_field ---

    @classmethod
    def normalize_bitable_pull_target_field(cls, value: Any) -> str:
        """委托到 FeishuBitableUtil.normalize_pull_target_field。"""
        return FeishuBitableUtil.normalize_pull_target_field(value)

    # --- migrated from TicketSyncService._normalize_bitable_pull_config ---

    @classmethod
    def normalize_bitable_pull_config(
        cls,
        value: Any,
        *,
        feishu_auth: dict[str, Any],
        bitable_common: dict[str, Any],
    ) -> dict[str, Any]:
        """
        归一化飞书多维表格主动拉取配置。

        :param value: 原始配置。
        :param feishu_auth: 飞书统一凭证。
        :param bitable_common: 多维公共配置。
        :return: 归一化后的主动拉取配置。
        """
        source = value if isinstance(value, dict) else {}
        config = {**cls.default_bitable_pull_config(), **source}
        config["enabled"] = SyncUtil.to_bool(config.get("enabled"), False)
        config["appId"] = str(config.get("appId") or "").strip() or str(feishu_auth.get("appId") or "").strip()
        config["appSecret"] = (
            str(config.get("appSecret") or "").strip() or str(feishu_auth.get("appSecret") or "").strip()
        )
        config["appToken"] = str(config.get("appToken") or "").strip()
        config["tableId"] = str(config.get("tableId") or "").strip()
        config["viewId"] = str(config.get("viewId") or "").strip()
        config["pageSize"] = min(max(SyncUtil.safe_int(config.get("pageSize")) or 200, 1), 500)
        config["filterFormula"] = cls.normalize_bitable_filter_config(config.get("filterFormula"))
        config["sourceSystem"] = (
            str(config.get("sourceSystem") or "feishu_bitable_pull").strip() or "feishu_bitable_pull"
        )
        config["ticketNoField"] = str(config.get("ticketNoField") or "ticketNo").strip() or "ticketNo"
        config["updatedAtField"] = str(config.get("updatedAtField") or "").strip()
        config["sortField"] = str(config.get("sortField") or "").strip()
        config["includeRecordUrl"] = SyncUtil.to_bool(config.get("includeRecordUrl"), True)
        config["createdAfter"] = str(config.get("createdAfter") or "").strip()
        config["createdBefore"] = str(config.get("createdBefore") or "").strip()
        config["forceSync"] = SyncUtil.to_bool(config.get("forceSync"), False)
        raw_send_group = config.get("sendGroupMessage")
        if raw_send_group is None or (isinstance(raw_send_group, str) and str(raw_send_group).strip() == ""):
            config["sendGroupMessage"] = None
        else:
            config["sendGroupMessage"] = SyncUtil.to_bool(raw_send_group)
        config["autoAppendTimeFilter"] = SyncUtil.to_bool(config.get("autoAppendTimeFilter"), True)
        config["fieldMappings"] = cls.normalize_bitable_field_mappings(config.get("fieldMappings"))
        automation = config.get("automation") if isinstance(config.get("automation"), dict) else {}
        config["automation"] = {
            "autoIdentify": SyncUtil.to_bool(automation.get("autoIdentify"), True),
            "autoLogPull": SyncUtil.to_bool(automation.get("autoLogPull"), False),
            "autoAiAnalysis": SyncUtil.to_bool(automation.get("autoAiAnalysis"), False),
            "autoTranslate": SyncUtil.to_bool(automation.get("autoTranslate"), True),
        }
        return config

    # --- migrated from TicketSyncService._resolve_bitable_pull_created_after ---

    @classmethod
    def resolve_bitable_pull_created_after(cls, value: Any) -> datetime | None:
        """
        解析飞书多维表格主动拉取的创建时间下限。

        :param value: 用户指定的时间，支持 datetime、时间戳或常见日期时间文本。
        :return: 可比较的时间对象；为空或无法解析时返回 None。
        """
        if value in (None, ""):
            return None
        return SyncUtil.parse_datetime_value(value)

    # --- migrated from TicketSyncService._datetime_to_bitable_filter_millis ---

    @classmethod
    def datetime_to_bitable_filter_millis(cls, value: datetime) -> int:
        """
        将 datetime 转换为飞书多维表格日期过滤使用的毫秒时间戳。

        :param value: 时间对象；无时区时按本地时间解释。
        :return: 13 位毫秒时间戳。
        """
        return int(value.timestamp() * 1000)

    # --- migrated from TicketSyncService._resolve_bitable_pull_create_time_field ---

    @classmethod
    def resolve_bitable_pull_create_time_field(cls, field_mappings: list[dict[str, Any]]) -> str:
        """
        从主动拉取字段映射中解析外部创建时间对应的多维字段名。

        :param field_mappings: 字段映射配置。
        :return: 多维表格创建时间字段名。
        """
        for item in field_mappings or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("targetField") or "").strip() == "createTime":
                source_field = str(item.get("sourceField") or "").strip()
                if source_field:
                    return source_field
        return "创建时间"

    # --- migrated from TicketSyncService._condition_needs_dynamic_time_value ---

    @classmethod
    def condition_needs_dynamic_time_value(
        cls,
        condition: dict[str, Any],
        *,
        time_field_names: set[str],
    ) -> bool:
        """
        判断过滤条件是否需要补齐动态时间值。

        :param condition: 飞书 filter 条件。
        :param time_field_names: 可识别为时间字段的字段名集合。
        :return: 时间比较条件 value 为空时返回 True。
        """
        if not isinstance(condition, dict):
            return False
        operator = str(condition.get("operator") or "").strip()
        if operator not in {"isGreater", "isGreaterEqual", "isLess", "isLessEqual"}:
            return False
        field_name = str(condition.get("field_name") or "").strip()
        if field_name not in time_field_names:
            return False
        return condition.get("value") in (None, "", [])

    # --- migrated from TicketSyncService._fill_dynamic_time_filter_values ---

    @classmethod
    def fill_dynamic_time_filter_values(
        cls,
        filter_item: Any,
        *,
        time_field_names: set[str],
        filter_value: Any,
    ) -> Any:
        """
        递归补齐时间过滤条件中的动态 value。

        :param filter_item: 飞书 filter 条件、条件组或条件列表。
        :param time_field_names: 可识别为时间字段的字段名集合。
        :param filter_value: 时间窗口下限值。
        :return: 补齐后的 filter 条件结构。
        """
        if isinstance(filter_item, list):
            return [
                cls.fill_dynamic_time_filter_values(
                    item,
                    time_field_names=time_field_names,
                    filter_value=filter_value,
                )
                for item in filter_item
                if isinstance(item, dict)
            ]
        if not isinstance(filter_item, dict):
            return filter_item

        normalized_filter = dict(filter_item)
        if isinstance(normalized_filter.get("children"), list):
            normalized_filter["children"] = cls.fill_dynamic_time_filter_values(
                normalized_filter.get("children"),
                time_field_names=time_field_names,
                filter_value=filter_value,
            )
        if isinstance(normalized_filter.get("conditions"), list):
            normalized_filter["conditions"] = cls.fill_dynamic_time_filter_values(
                normalized_filter.get("conditions"),
                time_field_names=time_field_names,
                filter_value=filter_value,
            )
        if cls.condition_needs_dynamic_time_value(
            normalized_filter,
            time_field_names=time_field_names,
        ):
            normalized_filter["value"] = filter_value
        return normalized_filter

    # --- migrated from TicketSyncService._build_bitable_pull_time_filters ---

    @classmethod
    def build_bitable_pull_time_filters(
        cls,
        *,
        filter_formula: Any,
        created_after: datetime | None,
        created_before: datetime | None = None,
        updated_at_field: str = "",
        auto_append_time_filter: bool = True,
    ) -> list[dict[str, Any]]:
        """
        构建主动拉取时间窗口对应的飞书 records/search filter 列表。

        :param filter_formula: 用户配置的 filter 条件。
        :param created_after: 时间窗口下限。
        :param created_before: 时间窗口上限。
        :param updated_at_field: 多维表格更新时间字段名。
        :param auto_append_time_filter: True 时保持现有行为（自动追加过去1小时窗口）；
            False 时使用精确时间比较（isGreater / isLess）。
        :return: 一个或多个 filter 条件对象；多个对象表示需要分别请求飞书后按 record_id 合并。
        """
        parsed_filter = cls.parse_bitable_filter_config(filter_formula)

        if auto_append_time_filter and not created_after:
            return [parsed_filter] if parsed_filter else []

        time_field = str(updated_at_field or "").strip()
        time_conditions = []
        if created_after:
            start_millis = cls.datetime_to_bitable_filter_millis(created_after)
            time_conditions.append(
                {
                    "field_name": time_field,
                    "operator": "isGreater",
                    "value": ["ExactDate", f"{start_millis}"],
                }
            )
        if created_before:
            end_millis = cls.datetime_to_bitable_filter_millis(created_before)
            time_conditions.append(
                {
                    "field_name": time_field,
                    "operator": "isLess",
                    "value": ["ExactDate", f"{end_millis}"],
                }
            )

        if not parsed_filter:
            return [{"conjunction": "and", "conditions": time_conditions}] if time_conditions else []

        if isinstance(parsed_filter.get("children"), list):
            if time_conditions:
                parsed_filter["children"].append(
                    {
                        "conjunction": "and",
                        "conditions": time_conditions,
                    }
                )
            return [parsed_filter]

        return [parsed_filter]


    # --- migrated from TicketSyncService._query_bitable_pull_records ---

    @classmethod
    def query_bitable_pull_records(
        cls,
        pull_config: dict[str, Any],
        filters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        按一个或多个飞书 filter 查询主动拉取记录，并按 record_id 去重。

        :param pull_config: 主动拉取配置。
        :param filters: 过滤条件列表。
        :return: 去重后的飞书记录。
        """
        if not filters:
            return TicketSyncNotifyService.query_bitable_records(pull_config)
        merged_records: list[dict[str, Any]] = []
        seen_record_ids: set[str] = set()
        for filter_item in filters:
            query_config = dict(pull_config)
            query_config["filterFormula"] = filter_item
            page_records = TicketSyncNotifyService.query_bitable_records(query_config)
            for record in page_records:
                if not isinstance(record, dict):
                    continue
                record_id = str(record.get("record_id") or record.get("recordId") or "").strip()
                unique_key = record_id or SyncUtil.text_sha256(json.dumps(record, ensure_ascii=False, sort_keys=True))
                if unique_key in seen_record_ids:
                    continue
                seen_record_ids.add(unique_key)
                merged_records.append(record)
        return merged_records

    # --- migrated from TicketSyncService._normalize_group_push_auto_statuses ---

    @classmethod
    def normalize_group_push_auto_statuses(
        cls,
        value: Any,
        *,
        fallback: Any = None,
    ) -> list[str]:
        """
        归一化自动群推送状态条件配置。

        :param value: 原始状态条件，支持列表或逗号分隔字符串。
        :param fallback: 回退配置值。
        :return: 去重后的状态文本列表。
        """
        source_value = value
        if source_value is None:
            source_value = fallback
        if isinstance(source_value, str):
            source_list = [item.strip() for item in source_value.split(",")]
        elif isinstance(source_value, list):
            source_list = source_value
        else:
            source_list = []
        normalized: list[str] = []
        for item in source_list:
            status_text = str(item or "").strip()
            if status_text and status_text not in normalized:
                normalized.append(status_text)
        return normalized

    # --- migrated from TicketSyncService._normalize_sync_config ---

    @classmethod
    def normalize_sync_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        merged = cls.default_sync_config()
        if isinstance(config, dict):
            merged.update(config)
        feishu_auth = merged.get("feishuAuth") if isinstance(merged.get("feishuAuth"), dict) else {}
        feishu_auth = {**cls.default_feishu_auth_config(), **feishu_auth}
        feishu_auth["appId"] = str(feishu_auth.get("appId") or "").strip()
        feishu_auth["appSecret"] = str(feishu_auth.get("appSecret") or "").strip()
        merged["feishuAuth"] = feishu_auth
        merged["bitableCommon"] = cls.normalize_bitable_common_config(
            merged.get("bitableCommon"),
            feishu_auth=feishu_auth,
        )
        merged["externalFieldModel"] = cls.normalize_external_field_model_config(merged.get("externalFieldModel"))
        if not isinstance(merged.get("logPullDefaults"), dict):
            merged["logPullDefaults"] = cls.default_sync_config()["logPullDefaults"]
        if not isinstance(merged.get("promptTemplates"), dict):
            merged["promptTemplates"] = cls.default_sync_config()["promptTemplates"]
        merged["statClassification"] = cls.normalize_stat_classification_config(merged.get("statClassification"))
        merged["aiClassification"] = cls.normalize_ai_classification_config(merged.get("aiClassification"))
        external_sync_bitable = (
            merged.get("externalSyncBitable")
            if isinstance(merged.get("externalSyncBitable"), dict)
            else {}
        )
        external_sync_bitable = {
            **cls.default_external_sync_bitable_config(),
            **external_sync_bitable,
        }
        external_sync_bitable["enabled"] = bool(external_sync_bitable.get("enabled"))
        external_sync_bitable["appId"] = str(external_sync_bitable.get("appId") or "").strip()
        external_sync_bitable["appSecret"] = str(external_sync_bitable.get("appSecret") or "").strip()
        external_sync_bitable["appToken"] = str(external_sync_bitable.get("appToken") or "").strip()
        external_sync_bitable["tableId"] = str(external_sync_bitable.get("tableId") or "").strip()
        external_sync_bitable["viewId"] = str(external_sync_bitable.get("viewId") or "").strip()
        merged["externalSyncBitable"] = external_sync_bitable
        merged["bitablePull"] = cls.normalize_bitable_pull_config(
            merged.get("bitablePull"),
            feishu_auth=feishu_auth,
            bitable_common=merged["bitableCommon"],
        )
        external_sync_required_fields = merged.get("externalSyncRequiredFields")
        if isinstance(external_sync_required_fields, list):
            normalized_required_fields: list[str] = []
            for item in external_sync_required_fields:
                field_name = str(item or "").strip()
                if field_name and field_name not in normalized_required_fields:
                    normalized_required_fields.append(field_name)
            merged["externalSyncRequiredFields"] = normalized_required_fields or list(
                cls.DEFAULT_EXTERNAL_SYNC_REQUIRED_FIELDS
            )
        else:
            merged["externalSyncRequiredFields"] = cls.derive_required_fields_from_external_field_model(
                merged.get("externalFieldModel")
            )
        if not isinstance(merged.get("remoteSync"), dict):
            merged["remoteSync"] = cls.default_remote_sync_config()
        else:
            remote_sync = dict(cls.default_remote_sync_config())
            remote_sync.update(merged.get("remoteSync") or {})
            remote_headers = remote_sync.get("headers") if isinstance(remote_sync.get("headers"), dict) else {}
            remote_sync["headers"] = {**cls.default_remote_sync_config()["headers"], **remote_headers}
            remote_sync["enabled"] = bool(remote_sync.get("enabled"))
            remote_sync["limit"] = min(max(int(remote_sync.get("limit") or 50), 1), 200)
            remote_sync["includeClosed"] = bool(remote_sync.get("includeClosed", True))
            remote_sync["autoTranslateOnPull"] = bool(remote_sync.get("autoTranslateOnPull", True))
            remote_sync["timeoutSec"] = max(int(remote_sync.get("timeoutSec") or 30), 10)
            remote_sync["pullUrl"] = str(remote_sync.get("pullUrl") or "").strip()
            remote_sync["ackUrl"] = str(remote_sync.get("ackUrl") or "").strip()
            remote_sync["consumer"] = str(remote_sync.get("consumer") or "").strip()
            remote_sync["sourceSystem"] = str(remote_sync.get("sourceSystem") or "public").strip() or "public"
            merged["remoteSync"] = remote_sync
        group_push = merged.get("groupPush") if isinstance(merged.get("groupPush"), dict) else {}
        default_group_push = cls.default_group_push_config()
        group_push = {**default_group_push, **group_push}
        group_push["sendMode"] = TicketSyncNotifyService._normalize_send_mode(group_push.get("sendMode"))
        group_push["enabled"] = bool(group_push.get("enabled"))
        group_push["sendAfterExternalSync"] = bool(group_push.get("sendAfterExternalSync"))
        group_push["sendAfterRemotePull"] = bool(group_push.get("sendAfterRemotePull"))
        group_push["pushIds"] = TicketSyncNotifyService._normalize_push_ids(group_push.get("pushIds"))
        group_push["appChatIds"] = TicketSyncNotifyService._normalize_chat_ids(group_push.get("appChatIds"))
        group_push["autoPushStatuses"] = cls.normalize_group_push_auto_statuses(
            group_push.get("autoPushStatuses", group_push.get("auto_push_statuses")),
            fallback=default_group_push.get("autoPushStatuses"),
        )
        parsed_group_push_auto_send_after = SyncUtil.parse_datetime_value(
            group_push.get("autoSendAfterTime")
            or group_push.get("auto_send_after_time")
        )
        group_push["autoSendAfterTime"] = (
            parsed_group_push_auto_send_after.isoformat()
            if parsed_group_push_auto_send_after
            else ""
        )
        group_push["appId"] = str(group_push.get("appId") or "").strip()
        group_push["appSecret"] = str(group_push.get("appSecret") or "").strip()
        priority_routes = group_push.get("priorityRoutes") if isinstance(group_push.get("priorityRoutes"), list) else []
        normalized_priority_routes: list[dict[str, Any]] = []
        for route in priority_routes:
            if not isinstance(route, dict):
                continue
            priorities_raw = route.get("priorities")
            if isinstance(priorities_raw, str):
                priorities = [TicketSyncNotifyService._normalize_priority(item) for item in priorities_raw.split(",")]
            elif isinstance(priorities_raw, list):
                priorities = [TicketSyncNotifyService._normalize_priority(item) for item in priorities_raw]
            else:
                priorities = []
            priorities = [item for item in priorities if item]
            push_ids = TicketSyncNotifyService._normalize_push_ids(route.get("pushIds"))
            chat_ids = TicketSyncNotifyService._normalize_chat_ids(route.get("chatIds") or route.get("appChatIds"))
            if not priorities:
                continue
            normalized_priority_routes.append(
                {
                    "priorities": priorities,
                    "pushIds": push_ids,
                    "chatIds": chat_ids,
                }
            )
        group_push["priorityRoutes"] = normalized_priority_routes
        group_push["template"] = str(group_push.get("template") or "").strip()
        group_push["manualTemplate"] = str(group_push.get("manualTemplate") or "").strip()
        if not group_push["appId"]:
            group_push["appId"] = feishu_auth["appId"]
        if not group_push["appSecret"]:
            group_push["appSecret"] = feishu_auth["appSecret"]
        merged["groupPush"] = group_push

        message_sync = merged.get("messageSync") if isinstance(merged.get("messageSync"), dict) else {}
        default_message_sync = cls.default_message_sync_config()
        message_sync = {**default_message_sync, **message_sync}
        message_sync["enabled"] = SyncUtil.to_bool(message_sync.get("enabled"), False)
        message_sync["feishuEventEnabled"] = SyncUtil.to_bool(message_sync.get("feishuEventEnabled"), False)
        message_sync["feishuWsEnabled"] = SyncUtil.to_bool(message_sync.get("feishuWsEnabled"), False)
        message_sync["feishuWsEncryptKey"] = str(message_sync.get("feishuWsEncryptKey") or "").strip()
        message_sync["feishuWsVerificationToken"] = str(
            message_sync.get("feishuWsVerificationToken") or ""
        ).strip()
        message_sync["allowedChatIds"] = TicketSyncNotifyService._normalize_chat_ids(
            message_sync.get("allowedChatIds")
        )
        message_sync["ignoreBotOpenIds"] = [
            str(item or "").strip()
            for item in (
                message_sync.get("ignoreBotOpenIds")
                if isinstance(message_sync.get("ignoreBotOpenIds"), list)
                else str(message_sync.get("ignoreBotOpenIds") or "").split(",")
            )
            if str(item or "").strip()
        ]
        message_sync["syncFeishuCommentToTicket"] = SyncUtil.to_bool(
            message_sync.get("syncFeishuCommentToTicket"),
            True,
        )
        message_sync["syncFeishuCommentToBitable"] = SyncUtil.to_bool(
            message_sync.get("syncFeishuCommentToBitable"),
            False,
        )
        message_sync["syncTicketCommentToBitable"] = SyncUtil.to_bool(
            message_sync.get("syncTicketCommentToBitable"),
            False,
        )
        message_sync["syncTicketCommentToFeishuThread"] = SyncUtil.to_bool(
            message_sync.get("syncTicketCommentToFeishuThread"),
            False,
        )
        message_sync["syncBitableNewStepToFeishuThread"] = SyncUtil.to_bool(
            message_sync.get("syncBitableNewStepToFeishuThread"),
            False,
        )
        message_sync["bitableStepReasonField"] = (
            str(message_sync.get("bitableStepReasonField") or "stepReason").strip() or "stepReason"
        )
        message_sync["bitableTicketNoField"] = (
            str(message_sync.get("bitableTicketNoField") or "ticketNo").strip() or "ticketNo"
        )
        message_sync["appendStepReasonFormat"] = (
            str(message_sync.get("appendStepReasonFormat") or "{date} {user}：{content}").strip()
            or "{date} {user}：{content}"
        )
        merged["messageSync"] = message_sync

        person_reminder = merged.get("personReminder") if isinstance(merged.get("personReminder"), dict) else {}
        default_person_reminder = cls.default_person_reminder_config()
        person_reminder = {**default_person_reminder, **person_reminder}
        person_reminder["sendMode"] = TicketSyncNotifyService._normalize_send_mode(person_reminder.get("sendMode"))
        person_reminder["dataSource"] = TicketSyncNotifyService._normalize_person_data_source(
            person_reminder.get("dataSource")
        )
        person_reminder["enabled"] = bool(person_reminder.get("enabled"))
        person_reminder["pushIds"] = TicketSyncNotifyService._normalize_push_ids(person_reminder.get("pushIds"))
        person_reminder["appId"] = str(person_reminder.get("appId") or "").strip()
        person_reminder["appSecret"] = str(person_reminder.get("appSecret") or "").strip()
        person_reminder["feishuAppId"] = str(person_reminder.get("feishuAppId") or "").strip()
        person_reminder["feishuAppSecret"] = str(person_reminder.get("feishuAppSecret") or "").strip()
        person_reminder["appToken"] = str(person_reminder.get("appToken") or "").strip()
        person_reminder["tableId"] = str(person_reminder.get("tableId") or "").strip()
        person_reminder["viewId"] = str(person_reminder.get("viewId") or "").strip()
        person_reminder["filterFormula"] = cls.normalize_bitable_filter_config(person_reminder.get("filterFormula"))
        person_reminder["personField"] = str(person_reminder.get("personField") or "").strip()
        person_reminder["timeField"] = str(person_reminder.get("timeField") or "").strip()
        person_reminder["thresholdMinutes"] = max(SyncUtil.safe_int(person_reminder.get("thresholdMinutes")) or 30, 1)
        person_reminder["messageTemplate"] = str(person_reminder.get("messageTemplate") or "").strip()
        person_reminder["rowsMarkdownTemplate"] = str(person_reminder.get("rowsMarkdownTemplate") or "").strip()
        person_reminder["maxRowsPerPerson"] = max(SyncUtil.safe_int(person_reminder.get("maxRowsPerPerson")) or 20, 1)
        person_reminder["pageSize"] = min(max(SyncUtil.safe_int(person_reminder.get("pageSize")) or 500, 1), 500)
        if not person_reminder["appId"]:
            person_reminder["appId"] = person_reminder["feishuAppId"]
        if not person_reminder["appSecret"]:
            person_reminder["appSecret"] = person_reminder["feishuAppSecret"]
        person_reminder["feishuAppId"] = person_reminder["appId"]
        person_reminder["feishuAppSecret"] = person_reminder["appSecret"]
        merged["personReminder"] = person_reminder

        summary_report = merged.get("summaryReport") if isinstance(merged.get("summaryReport"), dict) else {}
        default_summary_report = cls.default_summary_report_config()
        summary_report = {**default_summary_report, **summary_report}
        summary_report["enabled"] = bool(summary_report.get("enabled"))
        summary_report["sendMode"] = TicketSyncNotifyService._normalize_send_mode(summary_report.get("sendMode"))
        summary_report["dataSource"] = TicketSyncNotifyService._normalize_summary_data_source(
            summary_report.get("dataSource")
        )
        summary_report["pushIds"] = TicketSyncNotifyService._normalize_push_ids(summary_report.get("pushIds"))
        summary_report["appChatIds"] = TicketSyncNotifyService._normalize_chat_ids(summary_report.get("appChatIds"))
        summary_report["appId"] = str(summary_report.get("appId") or "").strip()
        summary_report["appSecret"] = str(summary_report.get("appSecret") or "").strip()
        summary_report["timeField"] = TicketSyncNotifyService._resolve_summary_time_field(
            summary_report.get("timeField")
        )
        summary_report["appToken"] = str(summary_report.get("appToken") or "").strip()
        summary_report["tableId"] = str(summary_report.get("tableId") or "").strip()
        summary_report["viewId"] = str(summary_report.get("viewId") or "").strip()
        summary_report["filterFormula"] = cls.normalize_bitable_filter_config(summary_report.get("filterFormula"))
        summary_report["statusField"] = str(summary_report.get("statusField") or "状态").strip() or "状态"
        summary_report["categoryField"] = str(summary_report.get("categoryField") or "分类").strip() or "分类"
        summary_report["priorityField"] = str(summary_report.get("priorityField") or "优先级").strip() or "优先级"
        summary_report["bitableTimeField"] = str(summary_report.get("bitableTimeField") or "").strip()
        summary_report["pageSize"] = min(max(SyncUtil.safe_int(summary_report.get("pageSize")) or 500, 1), 500)
        summary_report["aiEnabled"] = bool(summary_report.get("aiEnabled"))
        summary_report["aiProviderCode"] = str(summary_report.get("aiProviderCode") or "").strip()
        summary_report["aiPromptCode"] = str(summary_report.get("aiPromptCode") or "").strip()
        summary_report["windowMinutes"] = max(SyncUtil.safe_int(summary_report.get("windowMinutes")) or 60, 1)
        summary_report["endDelayMinutes"] = max(SyncUtil.safe_int(summary_report.get("endDelayMinutes")) or 0, 0)
        summary_report["startTime"] = str(summary_report.get("startTime") or "").strip()
        summary_report["endTime"] = str(summary_report.get("endTime") or "").strip()
        summary_report["includeClosed"] = bool(summary_report.get("includeClosed", True))
        summary_report["messageTemplate"] = str(summary_report.get("messageTemplate") or "").strip()
        merged["summaryReport"] = summary_report
        if not isinstance(merged.get("projectMappings"), list):
            merged["projectMappings"] = []
        if not isinstance(merged.get("moduleMappings"), list):
            merged["moduleMappings"] = []
        if not isinstance(merged.get("vendorMappings"), list):
            merged["vendorMappings"] = []
        if not isinstance(merged.get("storeMappings"), list):
            merged["storeMappings"] = []
        if not isinstance(merged.get("statusMappings"), list):
            merged["statusMappings"] = []
        if not isinstance(merged.get("assigneeMappings"), list):
            merged["assigneeMappings"] = []
        if not isinstance(merged.get("posPatterns"), list):
            merged["posPatterns"] = cls.default_sync_config()["posPatterns"]
        if not isinstance(merged.get("scoPatterns"), list):
            merged["scoPatterns"] = cls.default_sync_config()["scoPatterns"]
        if not isinstance(merged.get("versionPatterns"), list):
            merged["versionPatterns"] = cls.default_sync_config()["versionPatterns"]
        merged["autoRunOnSync"] = bool(merged.get("autoRunOnSync"))
        merged["autoTranslateOnSync"] = bool(merged.get("autoTranslateOnSync", True))
        merged["defaultPullLimit"] = min(max(int(merged.get("defaultPullLimit") or 50), 1), 200)
        return merged

    # --- migrated from TicketSyncService.ensure_param_config_rows ---

    @classmethod
    def ensure_param_config_rows(cls, db: Session) -> None:
        now = datetime.now()
        existing = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
        if existing:
            return
        db.add(
            SysConfig(
                config_name="工单同步自动化配置",
                config_key=cls.CONFIG_KEY,
                config_value=SyncUtil.json_dumps(cls.default_sync_config()),
                config_type="Y",
                create_by="system",
                update_by="system",
                create_time=now,
                update_time=now,
                remark="外部工单同步、内网拉取、规则识别和自动化链路配置 JSON",
            )
        )
        db.flush()

    # --- migrated from TicketSyncService._load_sync_config ---

    @classmethod
    def load_sync_config(cls, db: Session) -> dict[str, Any]:
        cls.ensure_param_config_rows(db)
        row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
        config = SyncUtil.json_loads(getattr(row, "config_value", None), cls.default_sync_config())
        if not isinstance(config, dict):
            return cls.default_sync_config()
        return cls.normalize_sync_config(config)

    # --- migrated from TicketSyncService.get_sync_automation_config_services ---

    @classmethod
    def get_sync_automation_config_services(cls, db: Session) -> dict[str, Any]:
        config_value = cls.load_sync_config(db)
        config_value["externalSyncRequiredFields"] = cls.derive_required_fields_from_external_field_model(
            config_value.get("externalFieldModel")
        )
        return {
            "configKey": cls.CONFIG_KEY,
            "configValue": config_value,
        }

    # --- migrated from TicketSyncService.get_ticket_stat_classification_options ---

    @classmethod
    def get_ticket_stat_classification_options(cls, db: Session) -> dict[str, Any]:
        """
        获取工单分类统计枚举选项。
        :param db: 数据库会话
        :return: 工单分类统计枚举配置
        """
        config = cls.load_sync_config(db)
        return cls.normalize_stat_classification_config(config.get("statClassification"))

    # --- migrated from TicketSyncService._merge_legacy_ai_classification_prompt_content ---

    @classmethod
    def merge_legacy_ai_classification_prompt_content(
        cls,
        current_config: dict[str, Any],
        next_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        保存同步配置时保留旧版内联 AI 分类提示词正文。

        新版页面只保存 Provider/Prompt 编码，提示词正文统一由 SysAiPromptTemplate 管理。
        仅在前端未显式提交 promptContent 字段时才保留旧值，避免字段缺失导致的历史数据丢失。
        如果前端显式提交了 promptContent（包括空字符串），则以前端值为准。
        :param current_config: 当前已生效配置。
        :param next_config: 本次待保存配置。
        :return: 合并后的配置。
        """
        current_ai_config = (
            current_config.get("aiClassification")
            if isinstance(current_config.get("aiClassification"), dict)
            else {}
        )
        next_ai_config = (
            next_config.get("aiClassification")
            if isinstance(next_config.get("aiClassification"), dict)
            else {}
        )
        # 仅在前端未显式提交 promptContent 字段时才保留旧值
        if "promptContent" not in next_ai_config:
            legacy_prompt_content = str(current_ai_config.get("promptContent") or "").strip()
            if legacy_prompt_content:
                next_ai_config["promptContent"] = legacy_prompt_content
                next_config["aiClassification"] = next_ai_config
        return next_config

    # --- migrated from TicketSyncService.update_sync_automation_config_services ---

    @classmethod
    def update_sync_automation_config_services(
        cls,
        db: Session,
        config_value: dict[str, Any],
        current_user_name: str,
    ) -> CrudResponseModel:
        try:
            current_config = cls.load_sync_config(db)
            merged = cls.normalize_sync_config(config_value)
            merged = cls.merge_legacy_ai_classification_prompt_content(current_config, merged)
            now = datetime.now()
            row = db.query(SysConfig).filter(SysConfig.config_key == cls.CONFIG_KEY).first()
            if row:
                row.config_name = "宸ュ崟鍚屾鑷姩鍖栭厤缃?"
                row.config_value = SyncUtil.json_dumps(merged)
                row.config_type = "Y"
                row.update_by = current_user_name
                row.update_time = now
            else:
                db.add(
                    SysConfig(
                        config_name="宸ュ崟鍚屾鑷姩鍖栭厤缃?",
                        config_key=cls.CONFIG_KEY,
                        config_value=SyncUtil.json_dumps(merged),
                        config_type="Y",
                        create_by=current_user_name,
                        update_by=current_user_name,
                        create_time=now,
                        update_time=now,
                        remark="澶栭儴宸ュ崟鍚屾銆佸唴缃戞媺鍙栥€佽鍒欒瘑鍒拰鑷姩鍖栭摼璺厤缃?JSON",
                    )
                )
            db.commit()
            return CrudResponseModel(is_success=True, message="淇濆瓨鎴愬姛", result=merged)
        except Exception as exc:
            db.rollback()
            raise exc

    # --- migrated from TicketSyncService.get_sync_notify_push_options_services ---

    @classmethod
    def get_sync_notify_push_options_services(cls, db: Session) -> list[dict[str, Any]]:
        """
        查询通知相关可选推送配置。

        :param db: 数据库会话。
        :return: 推送配置列表。
        """
        return TicketSyncNotifyService.list_push_options(db)
