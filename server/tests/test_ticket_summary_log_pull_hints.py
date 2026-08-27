from modules.ticket.entity.vo.ticket_read_vo import TicketSummaryModel


def test_ticket_summary_keeps_log_pull_extra_data():
    """工单轻量概览必须保留日志拉取回填所需的扩展门店信息。"""
    result = TicketSummaryModel.model_validate(
        {
            "ticketId": "1001",
            "ticketNo": "T-1001",
            "title": "门店日志异常",
            "extraData": {
                "log_pull_hints": {
                    "vendorId": 10001,
                    "storeId": "SAP001",
                    "posNo": 3,
                },
                "external_sync": {
                    "source": {
                        "storeId": "ORG001",
                        "storeName": "上海门店",
                    }
                },
            },
        }
    )

    assert result.extra_data == {
        "log_pull_hints": {
            "vendorId": 10001,
            "storeId": "SAP001",
            "posNo": 3,
        },
        "external_sync": {
            "source": {
                "storeId": "ORG001",
                "storeName": "上海门店",
            }
        },
    }


def test_ticket_summary_keeps_top_level_external_store_mapping():
    """轻量概览应保留历史同步数据中的原始 ticketStore。"""
    result = TicketSummaryModel.model_validate(
        {
            "ticketId": "1002",
            "extraData": {
                "external_field_mapping": {
                    "ticketStore": "SAP-UNKNOWN-001",
                }
            },
        }
    )

    assert result.extra_data["external_field_mapping"]["ticketStore"] == "SAP-UNKNOWN-001"
