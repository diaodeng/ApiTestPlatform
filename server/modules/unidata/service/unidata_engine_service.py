"""大数据查询引擎可用性探测服务。

Unidata 未提供"查询可用引擎"的接口，引擎是否真正可用只能通过实际执行来发现。
本服务用最小查询（SELECT 1）对各候选引擎做真实探测，并对结果做进程内 TTL 缓存，
前端引擎下拉只展示探测可用的引擎（如 UAT 不可用的 starrocks 不会出现）。

候选引擎全集来自 Unidata OpenAPI 契约（AssetQueryExecuteRequest.engine:
Supported values: starrocks / kyuubi），属协议约定而非业务硬编码。
"""
import threading
import time

from sqlalchemy.orm import Session

from modules.unidata.entity.vo.unidata_vo import UnidataEngineStatusModel
from modules.unidata.service.unidata_gateway_service import UnidataGatewayService
from utils.log_util import logger

# Unidata 契约定义的候选引擎全集（协议级约定）
CANDIDATE_ENGINES: tuple[str, ...] = ("kyuubi", "starrocks")
# 探测结果缓存时长（秒）：过期后下次访问重新探测，环境配置变更（如开通 StarRocks）后可自动恢复
_CACHE_TTL_SECONDS = 300


class UnidataEngineService:
    """查询引擎可用性探测与缓存。"""

    # 进程内缓存：key=(source_code, engine)，value=(过期时间, 探测结果)
    _cache: dict[tuple[str, str], tuple[float, UnidataEngineStatusModel]] = {}
    _lock = threading.Lock()

    @classmethod
    def list_engine_statuses(
        cls, db: Session, source_code: str, refresh: bool = False
    ) -> list[UnidataEngineStatusModel]:
        """探测数据源各候选引擎的可用性（带缓存）。

        :param db: 数据库会话
        :param source_code: 数据源编码
        :param refresh: True 时跳过缓存强制重新探测
        :return: 各引擎可用性状态列表（顺序与候选引擎一致）
        """
        client, source = UnidataGatewayService.build_source_client(db, source_code)
        try:
            statuses = [
                cls._get_status(client, source.code, source.workbench_code, engine, refresh)
                for engine in CANDIDATE_ENGINES
            ]
        finally:
            client.close()
        return statuses

    @classmethod
    def _get_status(
        cls, client, source_code: str, workbench_code: str, engine: str, refresh: bool
    ) -> UnidataEngineStatusModel:
        """读取单个引擎的探测状态：优先取未过期缓存，否则真实探测后写回。"""
        key = (source_code, engine)
        now = time.monotonic()
        with cls._lock:
            cached = cls._cache.get(key)
            if cached and not refresh and cached[0] > now:
                return cached[1]
        available, message = UnidataGatewayService.probe_engine(client, workbench_code, engine)
        status = UnidataEngineStatusModel(engine=engine, available=available, message=message)
        with cls._lock:
            cls._cache[key] = (now + _CACHE_TTL_SECONDS, status)
        logger.info(
            f"Unidata 引擎探测完成: source={source_code} engine={engine} "
            f"available={available} message={message}"
        )
        return status

    @classmethod
    def reset_cache(cls) -> None:
        """清空探测缓存（测试与运维用途）。"""
        with cls._lock:
            cls._cache.clear()
