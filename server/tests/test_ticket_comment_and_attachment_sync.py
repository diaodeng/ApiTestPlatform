"""工单评论与附件同步改造的纯函数单测：幂等键、时间边界、分段解析、附件提取与记录评论解析。"""
import hashlib
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_bitable_record_comment_service import (
    TicketBitableRecordCommentService,
)
from modules.ticket.service.sync.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil


class TicketSyncCommentServiceTests(unittest.TestCase):
    """评论同步服务：时间边界与幂等键。"""

    def test_parse_step_reason_date_today_returns_none(self):
        """当天日期应返回 None，评论时间由入库时间兜底。"""
        today_text = datetime.now().strftime("%Y%m%d")
        self.assertIsNone(TicketSyncCommentService.parse_step_reason_date(today_text))

    def test_parse_step_reason_date_past_keeps_midnight(self):
        """非当天日期应保持原行为返回当天 00:00:00。"""
        result = TicketSyncCommentService.parse_step_reason_date("20200101")
        self.assertEqual(result, datetime(2020, 1, 1, 0, 0, 0))

    def test_parse_step_reason_date_invalid_returns_none(self):
        """非法文本应返回 None。"""
        self.assertIsNone(TicketSyncCommentService.parse_step_reason_date("abc"))
        self.assertIsNone(TicketSyncCommentService.parse_step_reason_date(""))
        self.assertIsNone(TicketSyncCommentService.parse_step_reason_date("202001"))

    def test_segment_key_step_reason_keeps_legacy_structure(self):
        """stepReason 幂等键必须与历史键结构一致，保证已入库评论不被重复创建。"""
        legacy_raw = "feishu_bitable_pull|rec1|stepReason|0"
        legacy_key = hashlib.sha256(legacy_raw.encode("utf-8")).hexdigest()
        self.assertEqual(
            TicketSyncCommentService.build_step_reason_segment_key(
                source_system="feishu_bitable_pull",
                source_record_id="rec1",
                segment_index=0,
            ),
            legacy_key,
        )

    def test_segment_key_l1_response_is_field_scoped(self):
        """l1Response 幂等键应包含字段名，与 stepReason 及不同分段互不冲突。"""
        kwargs = {"source_system": "feishu_bitable_pull", "source_record_id": "rec1", "segment_index": 0}
        step_key = TicketSyncCommentService.build_step_reason_segment_key(**kwargs)
        l1_key = TicketSyncCommentService.build_step_reason_segment_key(**kwargs, source_field="l1Response")
        l1_key_other = TicketSyncCommentService.build_step_reason_segment_key(
            source_system="feishu_bitable_pull",
            source_record_id="rec1",
            segment_index=1,
            source_field="l1Response",
        )
        self.assertNotEqual(step_key, l1_key)
        self.assertNotEqual(l1_key, l1_key_other)
        # 同参数重复构建必须稳定
        self.assertEqual(
            l1_key,
            TicketSyncCommentService.build_step_reason_segment_key(**kwargs, source_field="l1Response"),
        )

    def test_resolve_field_text_reads_model_attr_and_raw_payload(self):
        """字段文本读取应支持模型属性和 raw_payload 两种来源。"""
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "source": {"system": "feishu_bitable_pull", "recordId": "rec1"},
                "ticketNo": "TK1",
                "l1Response": "20260901 张三：已修复",
                "raw_payload": {"stepReason": "20260901 李四：排查完成"},
            }
        )
        self.assertEqual(
            TicketSyncCommentService._resolve_field_text(sync_object, source_field="l1Response"),
            "20260901 张三：已修复",
        )
        self.assertEqual(
            TicketSyncCommentService._resolve_field_text(sync_object, source_field="stepReason"),
            "20260901 李四：排查完成",
        )

    def test_sync_step_reason_comments_covers_l1_response(self):
        """同步摘要应包含 l1Response 字段分组，且 l1 评论带一线回复标识。"""
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "source": {"system": "feishu_bitable_pull", "recordId": "rec1"},
                "ticketNo": "TK1",
                "l1Response": "20200101 张三：已修复并验证",
            }
        )
        captured: dict = {}

        def fake_upsert(db, **kwargs):
            captured.update(kwargs)
            return object(), "created"

        ticket_stub = SimpleNamespace(ticket_id=123)
        with patch(
            "modules.ticket.service.sync.ticket_sync_comment_service.TicketCommentCoreService.upsert_synced_comment",
            side_effect=fake_upsert,
        ):
            summary = TicketSyncCommentService.sync_step_reason_comments(
                None, ticket=ticket_stub, sync_object=sync_object
            )
        self.assertIn("l1Response", summary.get("fields", {}))
        self.assertEqual(summary.get("created"), 1)
        self.assertFalse(summary.get("skipped"))
        # 一线回复标识：正文追加文案，attachments 带 sourceFieldLabel
        self.assertIn("【一线回复】", captured.get("content") or "")
        self.assertEqual((captured.get("attachments") or {}).get("sourceFieldLabel"), "一线回复")

    def test_sync_step_reason_comments_step_reason_no_label(self):
        """stepReason 评论不应追加一线回复标识。"""
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "source": {"system": "feishu_bitable_pull", "recordId": "rec1"},
                "ticketNo": "TK1",
                "stepReason": "20200101 李四：排查完成",
            }
        )
        captured: dict = {}

        def fake_upsert(db, **kwargs):
            captured.update(kwargs)
            return object(), "created"

        ticket_stub = SimpleNamespace(ticket_id=123)
        with patch(
            "modules.ticket.service.sync.ticket_sync_comment_service.TicketCommentCoreService.upsert_synced_comment",
            side_effect=fake_upsert,
        ):
            summary = TicketSyncCommentService.sync_step_reason_comments(
                None, ticket=ticket_stub, sync_object=sync_object
            )
        self.assertIn("stepReason", summary.get("fields", {}))
        self.assertNotIn("【一线回复】", captured.get("content") or "")
        # 无富文本片段且非一线回复时，attachments 保持 None（与既有行为一致）
        self.assertIsNone(captured.get("attachments"))


class FeishuBitableUtilTests(unittest.TestCase):
    """多维表格工具：附件提取与富文本分段。"""

    def test_extract_attachment_tokens(self):
        """附件字段应提取 fileToken 元信息并去重，忽略无 token 项。"""
        value = [
            {"file_token": "tok1", "name": "截图.png", "size": 123, "type": "png"},
            {"file_token": "tok1", "name": "重复.png"},
            {"name": "无token.png"},
            "非对象项",
        ]
        result = FeishuBitableUtil.extract_attachment_tokens(value)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fileToken"], "tok1")
        self.assertEqual(result[0]["name"], "截图.png")
        self.assertEqual(result[0]["size"], 123)

    def test_extract_attachment_tokens_empty(self):
        """空值与非列表应返回空列表。"""
        self.assertEqual(FeishuBitableUtil.extract_attachment_tokens(None), [])
        self.assertEqual(FeishuBitableUtil.extract_attachment_tokens("text"), [])

    def test_segment_target_fields_include_l1_response(self):
        """分段评论目标字段应包含 stepReason 与 l1Response。"""
        self.assertEqual(
            FeishuBitableUtil.SEGMENT_COMMENT_TARGET_FIELDS,
            {"stepReason", "l1Response"},
        )
        self.assertEqual(
            FeishuBitableUtil.ATTACHMENT_TARGET_FIELDS,
            {"ticketAttachments", "replyAttachments"},
        )

    def test_pull_field_mapping_extracts_attachments(self):
        """字段映射转换应把附件字段转为 fileToken 列表。"""
        fields = {"IT附件": [{"file_token": "tokA", "name": "日志.txt", "size": 10, "type": "txt"}]}
        mappings = [{"sourceField": "IT附件", "targetField": "ticketAttachments"}]
        payload = FeishuBitableUtil.build_pull_field_mapping_from_record(fields, field_mappings=mappings)
        self.assertEqual(payload["ticketAttachments"][0]["fileToken"], "tokA")

    def test_pull_field_mapping_l1_response_segments(self):
        """l1Response 富文本应产出 text 片段供评论沿用。"""
        fields = {"L1回复": [{"type": "text", "text": "已修复"}, {"type": "text", "text": "，请验证"}]}
        mappings = [{"sourceField": "L1回复", "targetField": "l1Response"}]
        payload = FeishuBitableUtil.build_pull_field_mapping_from_record(fields, field_mappings=mappings)
        self.assertEqual(payload["l1Response"], "已修复，请验证")
        extra_data = payload.get("extraData") or {}
        segments = (extra_data.get("_bitable_field_segments") or {}).get("l1Response")
        self.assertTrue(segments)
        self.assertEqual("".join(item["text"] for item in segments), "已修复，请验证")


class TicketBitableRecordCommentServiceTests(unittest.TestCase):
    """记录评论服务：幂等键、时间解析与内容解析。"""

    def test_comment_segment_key_stable_and_scoped(self):
        """幂等键应按 record+comment 隔离且可稳定重建。"""
        key1 = TicketBitableRecordCommentService.build_comment_segment_key(
            record_id="rec1", comment_id="cmt1"
        )
        key2 = TicketBitableRecordCommentService.build_comment_segment_key(
            record_id="rec1", comment_id="cmt1"
        )
        key3 = TicketBitableRecordCommentService.build_comment_segment_key(
            record_id="rec1", comment_id="cmt2"
        )
        key4 = TicketBitableRecordCommentService.build_comment_segment_key(
            record_id="rec2", comment_id="cmt1"
        )
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key1, key4)

    def test_parse_comment_time_millis_and_invalid(self):
        """毫秒时间戳应正确解析，非法值返回 None。"""
        parsed = TicketBitableRecordCommentService.parse_comment_time(1700000000000)
        self.assertIsInstance(parsed, datetime)
        self.assertIsNone(TicketBitableRecordCommentService.parse_comment_time("bad"))
        self.assertIsNone(TicketBitableRecordCommentService.parse_comment_time(None))

    def test_parse_comment_content_text_and_attachments(self):
        """评论解析应分离文本与附件元素。"""
        comment = {
            "comment_id": "cmt1",
            "content": {
                "elements": [
                    {"type": "text", "text": "第一行"},
                    {"type": "text", "text": "第二行"},
                    {
                        "type": "attachment",
                        "file_token": "tokX",
                        "name": "图.png",
                        "size": 2048,
                        "fileType": "png",
                    },
                ]
            },
        }
        content, attachments = TicketBitableRecordCommentService.parse_comment_content(comment)
        self.assertEqual(content, "第一行\n第二行")
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["fileToken"], "tokX")
        self.assertEqual(attachments[0]["type"], "png")

    def test_parse_comment_content_empty(self):
        """空评论解析应返回空文本与空附件。"""
        content, attachments = TicketBitableRecordCommentService.parse_comment_content({})
        self.assertEqual(content, "")
        self.assertEqual(attachments, [])


if __name__ == "__main__":
    unittest.main()
