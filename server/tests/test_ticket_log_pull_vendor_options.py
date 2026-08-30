from types import SimpleNamespace

from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService


def _patch_vendor_options_dependencies(monkeypatch):
    """屏蔽选项接口对数据库和外部环境配置的依赖，只测试商家/门店拼装逻辑。"""
    monkeypatch.setattr(TicketLogPullService, "ensure_param_config_rows", lambda db: None)
    monkeypatch.setattr(TicketLogPullService, "_get_environment_options", lambda db: [])
    monkeypatch.setattr(
        TicketLogPullDao,
        "get_vendor_config_row",
        lambda db: SimpleNamespace(
            config_value='[{"venderNo":"10001","vendorName":"华东商家"}]'
        ),
    )
    monkeypatch.setattr(
        TicketLogPullDao,
        "get_param_example_config_row",
        lambda db: SimpleNamespace(config_value="[]"),
    )


def test_vendor_options_are_read_from_parameter_config_and_stores_are_queried_by_vender_no(monkeypatch):
    """商家来自参数配置，门店只查询当前商户编号，并透传环境过滤。"""
    queried_vender_nos = []
    queried_environments = []

    _patch_vendor_options_dependencies(monkeypatch)

    def list_store_configs_by_vender_no(db, vender_no, environment=None):
        queried_vender_nos.append(vender_no)
        queried_environments.append(environment)
        return [
            SimpleNamespace(
                org_no="S001",
                sap_org_no="SAP001",
                org_name="上海门店",
            )
        ]

    monkeypatch.setattr(TicketLogPullDao, "list_store_configs_by_vender_no", list_store_configs_by_vender_no)

    result = TicketLogPullService.get_vendor_store_options_services(object(), vender_no="10001")

    assert [vendor.model_dump() for vendor in result.vendors] == [
        {"vender_no": "10001", "vendor_name": "华东商家"}
    ]
    assert queried_vender_nos == ["10001"]
    assert queried_environments == [None]
    assert [store.model_dump() for store in result.stores] == [
        {
            "store_id": "S001",
            "store_code": "S001",
            "sap_org_no": "SAP001",
            "store_name": "上海门店",
        }
    ]


def test_vendor_options_pass_environment_filter_to_store_query(monkeypatch):
    """传入环境分组 key 时，门店查询应带上环境过滤参数。"""
    captured_kwargs = {}

    _patch_vendor_options_dependencies(monkeypatch)

    def list_store_configs_by_vender_no(db, vender_no, environment=None):
        captured_kwargs["vender_no"] = vender_no
        captured_kwargs["environment"] = environment
        return []

    monkeypatch.setattr(TicketLogPullDao, "list_store_configs_by_vender_no", list_store_configs_by_vender_no)

    result = TicketLogPullService.get_vendor_store_options_services(
        object(), vender_no="10001", environment="uat"
    )

    assert captured_kwargs == {"vender_no": "10001", "environment": "uat"}
    assert result.stores == []


def test_vendor_options_do_not_query_store_table_when_vender_no_is_missing(monkeypatch):
    """首次打开弹窗只获取商家参数，不一次性加载门店。"""
    _patch_vendor_options_dependencies(monkeypatch)
    monkeypatch.setattr(
        TicketLogPullDao,
        "list_store_configs_by_vender_no",
        lambda db, vender_no, environment=None: (_ for _ in ()).throw(AssertionError("不应查询门店表")),
    )

    result = TicketLogPullService.get_vendor_store_options_services(object())

    assert len(result.vendors) == 1
    assert result.stores == []
