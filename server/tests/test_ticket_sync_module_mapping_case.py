"""模块映射关键字匹配回归测试。

背景：2026-08-27 提交 132ba29 将 SyncUtil.normalize_keywords 统一小写化后，
模块映射匹配器（_match_module_mapping_with_project）中的 target 未同步小写，
导致“配置关键字大写 + 工单模块文本混合大小写”场景永远无法命中，
工单入库后 module_id 为空、module_code 为空字符串（matched_by=unmatched）。
"""

from modules.ticket.service.sync.ticket_sync_field_mapping_service import (
    ModuleMappingResult,
    TicketSyncFieldMappingService,
)

MODULE_MAPPINGS = [
    {
        "moduleCode": "pos_coupon",
        "moduleName": "POS - 优惠券",
        "keywords": ["POS - 优惠券"],
    },
    {
        "moduleCode": "pos_client",
        "moduleName": "POS - 客户端",
        "keywords": ["POS-客户端", "POS - 客户端", "POS"],
    },
]


def test_module_mapping_hits_when_keyword_case_differs_from_text():
    """配置关键字与工单模块文本大小写不一致时也必须命中映射。"""
    result = TicketSyncFieldMappingService._match_module_mapping_with_project(
        "POS - 优惠券", MODULE_MAPPINGS, None
    )
    assert result is not None
    assert result["moduleCode"] == "pos_coupon"


def test_module_mapping_hits_when_text_case_differs_from_keyword():
    """工单模块文本为小写、配置关键字为大写时同样命中。"""
    result = TicketSyncFieldMappingService._match_module_mapping_with_project(
        "pos - 客户端", MODULE_MAPPINGS, None
    )
    assert result is not None
    assert result["moduleCode"] == "pos_client"


def test_module_mapping_project_isolation_still_applies():
    """大小写修复不得破坏 projectId 项目隔离校验。"""
    scoped_mappings = [{**MODULE_MAPPINGS[0], "projectId": 123}]
    # 项目不匹配 → 不命中
    assert (
        TicketSyncFieldMappingService._match_module_mapping_with_project(
            "POS - 优惠券", scoped_mappings, 456
        )
        is None
    )
    # 项目匹配 → 命中
    assert (
        TicketSyncFieldMappingService._match_module_mapping_with_project(
            "POS - 优惠券", scoped_mappings, 123
        )
        is not None
    )


def test_module_mapping_no_text_returns_empty_result():
    """模块文本为空时返回未命中的空结果，不抛异常。"""
    assert TicketSyncFieldMappingService._match_module_mapping_with_project("", MODULE_MAPPINGS, None) is None
    assert TicketSyncFieldMappingService._match_module_mapping_with_project("  ", MODULE_MAPPINGS, None) is None


def test_mapping_keywords_are_lowercased():
    """mapping_keywords 输出统一小写，与 target 小写比较语义配套。"""
    keywords = TicketSyncFieldMappingService.mapping_keywords(
        {"keywords": ["POS - 优惠券"], "matchText": "POS - 礼券"}
    )
    assert "pos - 优惠券" in keywords
    assert "pos - 礼券" in keywords


def test_resolve_module_by_ticket_modle_resolves_module_text_with_mixed_case():
    """端到端：混合大小写模块文本经映射解析出 resolved 模块信息（内存映射，不查库场景走 direct 语义）。"""
    mappings = [
        {"moduleCode": "POS_COUPON", "moduleName": "POS - 优惠券", "keywords": ["POS - 优惠券"]},
    ]

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            # 模拟 hrm_module 命中行
            return type("Row", (), {"module_id": 1, "module_code": "pos_coupon", "module_name": "POS - 优惠券"})()

    class FakeDB:
        def query(self, *_args, **_kwargs):
            return FakeQuery()

    result = TicketSyncFieldMappingService.resolve_module_by_ticket_modle(
        FakeDB(),
        ticket_modle="pos - 优惠券",
        project_id=None,
        module_mappings=mappings,
    )
    assert isinstance(result, ModuleMappingResult)
    assert result.mapping_matched is True
    assert result.mapped_module_code == "POS_COUPON"
