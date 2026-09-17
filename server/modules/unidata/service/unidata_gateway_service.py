"""Unidata OpenAPI HTTP 网关服务。

封装对 Unidata 网关的底层调用：客户端构造（凭证投影）、库权限清单、
库下表清单、只读 SQL 执行、引擎可用性探测。
只负责协议细节（鉴权头、分页、高亮剥离、业务错误转译），不做业务编排。
"""
import httpx

from modules.credential.service.credential_resolve_service import CredentialResolveService
from modules.unidata.service.unidata_config_service import UnidataConfigService
from utils.log_util import logger

from ..util.unidata_format_util import extract_payload_rows, strip_highlight

# 单次请求分页上限：Unidata 服务端限制 pageSize <= 100
_PAGE_SIZE_LIMIT = 100
# 权限/表清单翻页保护上限，防止异常死循环
_MAX_PAGES = 20
# 客户端 HTTP 超时缓冲：Unidata 侧查询超时上限 600 秒，客户端再留缓冲
_HTTP_TIMEOUT_BUFFER_SECONDS = 30
# 引擎探测用 SQL 的 Unidata 侧超时秒数（探测应快速失败）
_PROBE_TIMEOUT_SECONDS = 30


class UnidataGatewayService:
    """Unidata OpenAPI 调用网关。"""

    @classmethod
    def build_source_client(cls, db, source_code: str) -> tuple[httpx.Client, object]:
        """按数据源编码解析凭证并构造带鉴权的 HTTP 客户端，供各业务服务共享。

        :param db: 数据库会话
        :param source_code: 数据源编码
        :return: (httpx 客户端, 数据源模型)
        :raises ValueError: 数据源未配置、凭证未绑定、凭证不可用或域名不在白名单时抛出明确错误
        """
        source = UnidataConfigService.get_enabled_source(db, source_code)
        if not source.credential_binding_id:
            raise ValueError(
                f"大数据查询数据源 '{source.code}' 未绑定统一凭证，"
                "请在系统参数 unidata.query.sources 中维护 credentialBindingId"
            )
        auth_headers = CredentialResolveService.resolve_http_headers(db, source.credential_binding_id, source.base_url)
        timeout_seconds = 600.0 + _HTTP_TIMEOUT_BUFFER_SECONDS
        client = cls._build_client(source.base_url, auth_headers, timeout_seconds=timeout_seconds)
        return client, source

    @classmethod
    def _build_client(cls, base_url: str, auth_headers: dict[str, str], timeout_seconds: float) -> httpx.Client:
        """构造带鉴权头的 HTTP 客户端。"""
        return httpx.Client(
            base_url=base_url,
            headers=auth_headers,
            timeout=timeout_seconds,
        )

    @classmethod
    def _request_json(cls, client: httpx.Client, method: str, path: str, **kwargs) -> dict:
        """执行请求并把 Unidata 统一响应转译为业务结果。

        Unidata 业务失败会以 HTTP 502 + code=UPSTREAM_BAD_RESPONSE 返回，
        真实原因在 message 中（如权限不足、仅支持单条 SELECT），此处转译为
        带 cause 的 ValueError，由上层控制器转成友好错误。
        """
        response = cls._request_with_network_guard(client, method, path, **kwargs)
        if response.status_code != 200:
            message = cls._extract_error_message(response)
            logger.warning(
                f"Unidata 请求失败: url={response.request.url} status={response.status_code} message={message}"
            )
            raise ValueError(f"Unidata 接口调用失败（HTTP {response.status_code}）：{message}")
        payload = response.json()
        if isinstance(payload, dict) and payload.get("success") is False:
            message = str(payload.get("message") or "未知业务错误")
            logger.warning(f"Unidata 业务失败: url={response.request.url} code={payload.get('code')} message={message}")
            raise ValueError(f"Unidata 业务失败：{message}")
        return payload

    @staticmethod
    def _request_with_network_guard(client: httpx.Client, method: str, path: str, **kwargs):
        """执行请求并把网络层异常（连接失败/DNS/超时）翻译为带指引的业务错误。

        部署服务器与 Unidata 网关不在同一网络区域时会抛 httpx.ConnectError 等，
        不翻译的话控制器会返回 500，运维无法从提示定位是网络不通。
        """
        try:
            return client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            request_url = ""
            try:
                request_url = str(exc.request.url)
            except AttributeError:
                request_url = path
            logger.warning(f"Unidata 请求网络异常: url={request_url} error={type(exc).__name__}: {exc}")
            raise ValueError(
                f"无法访问 Unidata 网关（{type(exc).__name__}），"
                f"请检查部署服务器到 Unidata baseUrl 的网络连通性与 DNS：{exc}"
            ) from exc

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """从错误响应中提取可读信息，优先取统一结构的 message 字段。"""
        try:
            payload = response.json()
        except ValueError:
            return response.text[:300]
        if isinstance(payload, dict) and payload.get("message"):
            return str(payload.get("message"))
        return response.text[:300]

    @classmethod
    def list_database_permissions(cls, client: httpx.Client, workbench_code: str) -> list[dict]:
        """分页拉取当前账号的表权限清单（原始行，含 dbName/tableName/authType）。"""
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            payload = cls._request_json(client, "GET", "/api/v1/assets/table-privileges/my", params={
                "workbenchCode": workbench_code,
                "pageNo": page,
                "pageSize": _PAGE_SIZE_LIMIT,
            })
            page_rows = extract_payload_rows(payload)
            rows.extend(row for row in page_rows if isinstance(row, dict))
            if len(page_rows) < _PAGE_SIZE_LIMIT:
                break
        return rows

    @classmethod
    def list_databases(cls, client: httpx.Client, workbench_code: str, keyword: str = "") -> list[dict]:
        """分页拉取全量正式元数据库清单（不做权限过滤，仅供目录展示）。"""
        rows: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            params: dict = {
                "workbenchCode": workbench_code,
                "pageNo": page,
                "pageSize": _PAGE_SIZE_LIMIT,
            }
            if keyword:
                params["keyword"] = keyword
            payload = cls._request_json(client, "GET", "/api/v1/assets/databases", params=params)
            page_rows = extract_payload_rows(payload)
            rows.extend(row for row in page_rows if isinstance(row, dict))
            if len(page_rows) < _PAGE_SIZE_LIMIT:
                break
        return rows

    @classmethod
    def list_tables_by_database(
        cls,
        client: httpx.Client,
        workbench_code: str,
        db_name: str,
        max_rows: int = 1000,
    ) -> list[dict]:
        """按精确库名枚举表清单。

        Unidata 的 tables 接口只支持 keyword 子串搜索（searchScope=库名），
        且返回库名带 HTML 高亮，因此这里拉取候选页后按剥离高亮后的精确库名过滤。
        """
        collected: list[dict] = []
        for page in range(1, _MAX_PAGES + 1):
            params = {
                "workbenchCode": workbench_code,
                "keyword": db_name,
                "searchScope": "库名",
                "pageNo": page,
                "pageSize": _PAGE_SIZE_LIMIT,
            }
            payload = cls._request_json(client, "GET", "/api/v1/assets/tables", params=params)
            page_rows = extract_payload_rows(payload)
            if not page_rows:
                break
            for row in page_rows:
                if not isinstance(row, dict):
                    continue
                if strip_highlight(row.get("dbName") or row.get("databaseName")) == db_name:
                    collected.append(row)
                    if len(collected) >= max_rows:
                        return collected
            if len(page_rows) < _PAGE_SIZE_LIMIT:
                break
        return collected

    @classmethod
    def execute_query(
        cls,
        client: httpx.Client,
        workbench_code: str,
        sql: str,
        max_rows: int,
        timeout_seconds: int,
        engine: str | None,
    ) -> dict:
        """执行只读 SQL（仅支持单条 SELECT/WITH/EXPLAIN/SHOW CREATE TABLE）。"""
        body: dict = {"sql": sql, "maxRows": max_rows, "timeoutSeconds": timeout_seconds}
        if engine:
            body["engine"] = engine
        payload = cls._request_json(
            client,
            "POST",
            "/api/v1/assets/query/execute",
            params={"workbenchCode": workbench_code},
            json=body,
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("Unidata 查询响应缺少 data 结构，无法解析结果")
        return data

    @classmethod
    def probe_engine(cls, client: httpx.Client, workbench_code: str, engine: str) -> tuple[bool, str]:
        """用最小查询（SELECT 1）探测指定引擎是否真正可用。

        :param client: 已带鉴权的 HTTP 客户端
        :param workbench_code: 工作台编码
        :param engine: 引擎标识
        :return: (是否可用, 不可用原因)
        """
        try:
            cls.execute_query(client, workbench_code, "SELECT 1", 1, _PROBE_TIMEOUT_SECONDS, engine)
            return True, ""
        except ValueError as exc:
            return False, str(exc)

    @classmethod
    def get_table_detail(cls, client: httpx.Client, workbench_code: str, table_full_name: str) -> dict:
        """获取表详情（含字段清单 fields，字段含 name/type/comment）。"""
        payload = cls._request_json(
            client,
            "GET",
            "/api/v1/assets/table-detail",
            params={"workbenchCode": workbench_code, "tableFullName": table_full_name},
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("Unidata 表详情响应缺少 data 结构，无法解析")
        return data
