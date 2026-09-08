"""内存诊断快照配置管理：sys_config JSON 配置的读取、校验与保存。

配置存储在 sys_config 表（键 monitor.memory_snapshot.config），采集线程
通过运行时服务的轮询通道热加载。本服务只负责配置这一件事；快照执行
逻辑在 utils/metrics/memory_snapshot.py。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig
from utils.metrics.memory_snapshot import (
    MEMORY_SNAPSHOT_CONFIG_KEY,
    MemorySnapshotConfig,
    config_from_payload,
    load_memory_snapshot_config,
)


class MemorySnapshotConfigService:
    """内存诊断快照的可视化配置业务编排。"""

    @classmethod
    def _seed_config_row(cls, db: Session) -> SysConfig:
        """按当前默认值构造一条新的 sys_config 配置行（未提交）。"""
        defaults = asdict(load_memory_snapshot_config())
        payload = {
            "enabled": defaults["enabled"],
            "rssThresholdMb": defaults["rss_threshold_mb"],
            "topLines": defaults["top_lines"],
            "cooldownSeconds": defaults["cooldown_seconds"],
        }
        now = datetime.now()
        return SysConfig(
            config_name="内存诊断快照配置",
            config_key=MEMORY_SNAPSHOT_CONFIG_KEY,
            config_value=json.dumps(payload, ensure_ascii=False),
            config_type="Y",
            create_by="system",
            update_by="system",
            create_time=now,
            update_time=now,
            remark="RSS 阈值触发的 tracemalloc 诊断快照配置（JSON）",
        )

    @classmethod
    def _load_config_row(cls, db: Session) -> SysConfig | None:
        """读取配置行，不存在时返回 None。"""
        return ConfigDao.get_config_detail_by_key(db, MEMORY_SNAPSHOT_CONFIG_KEY)

    @classmethod
    def _row_to_payload(cls, row: SysConfig) -> dict:
        """把配置行的 JSON 值解析为 dict，解析失败或非 dict 时回退空字典。"""
        try:
            parsed = json.loads(row.config_value or "")
        except (TypeError, ValueError):
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def get_config(cls, db: Session) -> dict:
        """
        读取诊断快照配置，不存在时自动初始化默认行。

        :param db: 数据库会话
        :return: 响应 payload（camelCase 字段 + 更新时间/操作人）
        """
        row = cls._load_config_row(db)
        if row is None:
            row = cls._seed_config_row(db)
            db.add(row)
            db.commit()
            db.refresh(row)
            logger.info(f"初始化内存诊断快照默认配置: key={MEMORY_SNAPSHOT_CONFIG_KEY}")
        parsed = cls._row_to_payload(row)
        payload = config_from_payload(parsed)
        return {
            "enabled": payload.enabled,
            "rssThresholdMb": payload.rss_threshold_mb,
            "topLines": payload.top_lines,
            "cooldownSeconds": payload.cooldown_seconds,
            "updateTime": row.update_time,
            "updateBy": row.update_by,
        }

    @classmethod
    def update_config(cls, db: Session, payload: dict, operator: str) -> dict:
        """
        保存诊断快照配置（不存在时初始化），返回保存后的生效值。

        :param db: 数据库会话
        :param payload: 页面提交的字段（enabled/rssThresholdMb/topLines/cooldownSeconds）
        :param operator: 操作人
        :return: 保存后的响应 payload
        """
        # 先经 config_from_payload 校验并钳制范围，落库与生效使用同一份值。
        validated = config_from_payload(payload)
        store_payload = {
            "enabled": validated.enabled,
            "rssThresholdMb": validated.rss_threshold_mb,
            "topLines": validated.top_lines,
            "cooldownSeconds": validated.cooldown_seconds,
        }
        row = cls._load_config_row(db)
        if row is None:
            row = cls._seed_config_row(db)
            db.add(row)
        row.config_value = json.dumps(store_payload, ensure_ascii=False)
        row.update_by = operator
        row.update_time = datetime.now()
        db.commit()
        db.refresh(row)
        logger.info(
            f"修改内存诊断快照配置: enabled={validated.enabled}, thresholdMb={validated.rss_threshold_mb}, "
            f"topLines={validated.top_lines}, cooldownSeconds={validated.cooldown_seconds}, operator={operator}"
        )
        return {
            "enabled": validated.enabled,
            "rssThresholdMb": validated.rss_threshold_mb,
            "topLines": validated.top_lines,
            "cooldownSeconds": validated.cooldown_seconds,
            "updateTime": row.update_time,
            "updateBy": row.update_by,
        }

    @classmethod
    def load_runtime_config(cls, db: Session) -> MemorySnapshotConfig:
        """
        加载采集线程使用的生效配置。

        数据库配置行存在时按行值构造（钳制范围），否则回退环境变量默认。
        数据库异常由调用方（轮询通道）捕获，此处向上抛出。

        :param db: 数据库会话
        :return: 生效配置对象
        """
        row = cls._load_config_row(db)
        if row is None:
            return load_memory_snapshot_config()
        return config_from_payload(cls._row_to_payload(row))
