"""大数据查询模块单元测试：格式化纯工具与查询服务编排（外部调用全部 mock）。"""
import pytest
from pydantic import ValidationError

from modules.unidata.entity.vo.unidata_vo import UnidataQueryRequestModel, UnidataQueryResultModel, UnidataSourceModel
from modules.unidata.service.unidata_config_service import UnidataConfigService
from modules.unidata.service.unidata_engine_service import UnidataEngineService
from modules.unidata.service.unidata_gateway_service import UnidataGatewayService
from modules.unidata.service.unidata_query_service import UnidataQueryService
from modules.unidata.util.unidata_format_util import extract_payload_rows, resolve_db_layer, strip_highlight


def _patch_build_client(monkeypatch, source=None):
    """统一打桩网关的客户端构造，避免单测触发真实凭证解析。"""
    monkeypatch.setattr(
        UnidataGatewayService,
        "build_source_client",
        classmethod(lambda cls, db, code: (_FakeClient(), source or _fake_source())),
    )


class _FakeClient:
    """替代 httpx.Client 的最小桩：仅提供 close 行为。"""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _fake_source(credential_binding_id: str = "3") -> UnidataSourceModel:
    return UnidataSourceModel(
        code="uat",
        name="UAT 大数据",
        base_url="https://uatopen-d.rta-os.com",
        workbench_code="ddw_trade",
        credential_binding_id=credential_binding_id,
        default_engine="kyuubi",
    )


def test_strip_highlight_removes_html_tags():
    assert strip_highlight("<span style='color:red' >dim_dm</span>.dim_supplier") == "dim_dm.dim_supplier"
    assert strip_highlight(None) == ""
    assert strip_highlight("  plain_name  ") == "plain_name"


def test_resolve_db_layer_matches_prefix_and_infix():
    assert resolve_db_layer("gray06_cpos_df") == "gray06"
    assert resolve_db_layer("ads_cockpit_data_gray06") == "gray06"
    assert resolve_db_layer("blaze_gray03_dim_dm") == "gray03"
    assert resolve_db_layer("dmall_order") == "stable"


def test_extract_payload_rows_supports_common_pagination_fields():
    assert extract_payload_rows({"data": {"list": [1]}}) == [1]
    assert extract_payload_rows({"data": {"records": [2]}}) == [2]
    assert extract_payload_rows({"data": [{"a": 1}]}) == [{"a": 1}]
    assert extract_payload_rows(None) == []


def test_build_client_rejects_missing_credential_binding(monkeypatch):
    monkeypatch.setattr(
        UnidataConfigService,
        "get_enabled_source",
        classmethod(lambda cls, db, code: _fake_source(credential_binding_id="")),
    )
    with pytest.raises(ValueError, match="未绑定统一凭证"):
        UnidataGatewayService.build_source_client(db=None, source_code="uat")


def test_list_databases_merges_privileges_and_sorts_stable_first(monkeypatch):
    privilege_rows = [
        {"dbName": "gray06_cpos_df", "tableName": "*", "authType": "RW"},
        {"dbName": "dmall_order", "tableName": "wm_order", "authType": "R"},
        {"dbName": "dmall_order", "tableName": "*", "authType": "R"},
        {"dbName": "dmall_order", "tableName": "wm_order_ware", "authType": "RW"},
        {"dbName": "<span style='color:red' >dim_dm</span>", "tableName": "*", "authType": "R"},
        {"dbName": "", "tableName": "*", "authType": "R"},
    ]
    _patch_build_client(monkeypatch)
    monkeypatch.setattr(
        UnidataGatewayService,
        "list_database_permissions",
        classmethod(lambda cls, client, wb: privilege_rows),
    )
    result = UnidataQueryService.list_databases(db=None, source_code="uat")
    names = [item.name for item in result]
    assert names == ["dim_dm", "dmall_order", "gray06_cpos_df"]
    dmall = result[1]
    assert dmall.layer == "stable" and dmall.wildcard is True and dmall.auth_types == ["R", "RW"]
    assert result[2].layer == "gray06" and result[2].auth_types == ["RW"]


def test_execute_query_normalizes_result(monkeypatch):
    captured = {}

    def fake_execute(cls, client, workbench_code, sql, max_rows, timeout_seconds, engine):
        captured.update({"sql": sql, "maxRows": max_rows, "engine": engine, "workbench": workbench_code})
        return {
            "sqlType": "SELECT",
            "columns": [{"name": "id", "type": "bigint"}, {"name": "pin", "type": "string"}],
            "rows": [{"id": 1, "pin": "a"}, {"id": 2, "pin": None}],
            "rowCount": 2,
            "truncated": False,
            "elapsedMs": 870,
        }

    _patch_build_client(monkeypatch)
    monkeypatch.setattr(UnidataGatewayService, "execute_query", classmethod(fake_execute))
    model = UnidataQueryRequestModel(sql="select 1", max_rows=50)
    result = UnidataQueryService.execute_query(db=None, source_code="uat", model=model)
    assert isinstance(result, UnidataQueryResultModel)
    assert captured["engine"] == "kyuubi" and captured["maxRows"] == 50 and captured["workbench"] == "ddw_trade"
    assert [column.name for column in result.columns] == ["id", "pin"]
    assert result.row_count == 2 and result.elapsed_ms == 870 and result.truncated is False


def test_query_request_rejects_blank_sql():
    with pytest.raises(ValidationError):
        UnidataQueryRequestModel(sql="   ")


def test_engine_service_probes_candidates_and_uses_cache(monkeypatch):
    """探测应覆盖全部候选引擎；缓存有效期内第二次调用不再真实探测。"""
    UnidataEngineService.reset_cache()
    probe_calls = []

    def fake_probe(cls, client, workbench_code, engine):
        probe_calls.append(engine)
        # kyuubi 可用，starrocks 未配置（模拟 UAT 现状）
        return (True, "") if engine == "kyuubi" else (False, "Unidata 业务失败：当前公司未配置可用的StarRocks资源")

    _patch_build_client(monkeypatch)
    monkeypatch.setattr(UnidataGatewayService, "probe_engine", classmethod(fake_probe))
    first = UnidataEngineService.list_engine_statuses(db=None, source_code="uat")
    second = UnidataEngineService.list_engine_statuses(db=None, source_code="uat")
    UnidataEngineService.reset_cache()
    assert [item.engine for item in first] == ["kyuubi", "starrocks"]
    assert first[0].available is True and first[1].available is False
    assert "StarRocks" in first[1].message
    assert probe_calls == ["kyuubi", "starrocks"]  # 第二次命中缓存，未新增探测
    assert first == second


def test_engine_service_refresh_forces_reprobe(monkeypatch):
    """refresh=True 应跳过缓存强制重新探测。"""
    UnidataEngineService.reset_cache()
    probe_calls = []

    def fake_probe(cls, client, workbench_code, engine):
        probe_calls.append(engine)
        return True, ""

    _patch_build_client(monkeypatch)
    monkeypatch.setattr(UnidataGatewayService, "probe_engine", classmethod(fake_probe))
    UnidataEngineService.list_engine_statuses(db=None, source_code="uat")
    UnidataEngineService.list_engine_statuses(db=None, source_code="uat", refresh=True)
    UnidataEngineService.reset_cache()
    assert probe_calls == ["kyuubi", "starrocks", "kyuubi", "starrocks"]


def test_list_columns_parses_table_detail(monkeypatch):
    """表字段清单应从 table-detail 的 fields 解析出名称/类型/备注。"""
    def fake_detail(cls, client, workbench_code, table_full_name):
        assert table_full_name == "dim_dm.dim_supplier"
        return {"fields": [
            {"name": "vender_id", "type": "bigint", "comment": "商家id"},
            {"name": "pin", "type": "string", "comment": None},
        ]}

    _patch_build_client(monkeypatch)
    monkeypatch.setattr(UnidataGatewayService, "get_table_detail", classmethod(fake_detail))
    result = UnidataQueryService.list_columns(db=None, source_code="uat", table_full_name="dim_dm.dim_supplier")
    assert [column.name for column in result] == ["vender_id", "pin"]
    assert result[0].type == "bigint" and result[0].comment == "商家id"
    assert result[1].comment == ""


def test_list_columns_rejects_invalid_full_name():
    with pytest.raises(ValueError, match="db.table"):
        UnidataQueryService.list_columns(db=None, source_code="uat", table_full_name="dim_supplier")


def test_gateway_translates_network_error():
    """部署服务器连不上 Unidata 网关时应转为带指引的业务错误，而不是裸 500。"""
    import httpx

    request = httpx.Request("GET", "https://uatopen-d.rta-os.com/api/v1/assets/table-privileges/my")

    class _BrokenTransport(httpx.BaseTransport):
        def handle_request(self, inner_request):
            raise httpx.ConnectError("connection refused", request=inner_request)

    client = httpx.Client(transport=_BrokenTransport(), base_url="https://uatopen-d.rta-os.com")
    try:
        with pytest.raises(ValueError, match="无法访问 Unidata 网关"):
            UnidataGatewayService.list_database_permissions(client, "ddw_trade")
    finally:
        client.close()


def test_gateway_translates_upstream_error():
    import httpx

    request = httpx.Request("GET", "https://uatopen-d.rta-os.com/api/v1/assets/databases")
    response = httpx.Response(
        502,
        json={
            "success": False,
            "code": "UPSTREAM_BAD_RESPONSE",
            "message": "当前用户无权限查看表样例数据",
            "data": None,
        },
        request=request,
    )

    class _StubTransport(httpx.BaseTransport):
        def handle_request(self, request):
            return response

    client = httpx.Client(transport=_StubTransport(), base_url="https://uatopen-d.rta-os.com")
    try:
        with pytest.raises(ValueError, match="当前用户无权限"):
            UnidataGatewayService.list_database_permissions(client, "ddw_trade")
    finally:
        client.close()
