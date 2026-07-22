from __future__ import annotations

import json
from datetime import datetime
from typing import Any


class TicketLogPrepareProgressService:
    """
    工单日志查看准备进度服务。

    该服务将短生命周期进度保存到 Redis，供前端在远程下载归档时展示实时进度。
    """

    KEY_PREFIX = "ticket:log-prepare-progress"
    TTL_SECONDS = 30 * 60

    @classmethod
    async def start(cls, redis: Any, ticket_id: int, record_id: int | None) -> None:
        """
        创建或重置一次日志准备进度。
        :param redis: 应用生命周期初始化的异步 Redis 客户端
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :return: 无
        """
        await cls._save(
            redis,
            ticket_id,
            record_id,
            stage="preparing",
            downloading=False,
            percentage=0,
            downloaded=0,
            total=0,
            source="",
            message="正在准备日志",
        )

    @classmethod
    async def report_download(
        cls,
        redis: Any,
        ticket_id: int,
        record_id: int | None,
        downloaded: int,
        total: int | None,
        source: str,
    ) -> None:
        """
        更新远程归档下载进度。
        :param redis: 应用生命周期初始化的异步 Redis 客户端
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param downloaded: 已下载字节数
        :param total: 文件总字节数，未知时为 None
        :param source: 下载来源标识
        :return: 无
        """
        percentage = 0
        if total and total > 0:
            percentage = min(99, max(0, int(downloaded * 100 / total)))
        await cls._save(
            redis,
            ticket_id,
            record_id,
            stage="downloading",
            downloading=True,
            percentage=percentage,
            downloaded=max(downloaded, 0),
            total=max(total or 0, 0),
            source=source,
            message="正在下载日志",
        )

    @classmethod
    async def complete(
        cls,
        redis: Any,
        ticket_id: int,
        record_id: int | None,
        success: bool,
        message: str = "",
    ) -> None:
        """
        标记日志准备任务结束。
        :param redis: 应用生命周期初始化的异步 Redis 客户端
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param success: 是否准备成功
        :param message: 结束说明
        :return: 无
        """
        await cls._save(
            redis,
            ticket_id,
            record_id,
            stage="completed" if success else "failed",
            downloading=False,
            percentage=100 if success else 0,
            message=message or ("日志准备完成" if success else "日志准备失败"),
        )

    @classmethod
    async def get(cls, redis: Any, ticket_id: int, record_id: int | None) -> dict[str, Any]:
        """
        获取指定日志准备任务的最新进度快照。
        :param redis: 应用生命周期初始化的异步 Redis 客户端
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :return: 进度快照
        """
        value = await redis.get(cls._build_key(ticket_id, record_id))
        return cls._deserialize(value)

    @classmethod
    async def _save(cls, redis: Any, ticket_id: int, record_id: int | None, **payload: Any) -> None:
        """
        写入 Redis 进度快照，并刷新其过期时间。
        :param redis: 应用生命周期初始化的异步 Redis 客户端
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :param payload: 待保存的进度字段
        :return: 无
        """
        key = cls._build_key(ticket_id, record_id)
        previous = cls._deserialize(await redis.get(key))
        snapshot = {
            **previous,
            **payload,
            "updatedAt": datetime.now().isoformat(sep=" ", timespec="seconds"),
        }
        await redis.set(key, json.dumps(snapshot, ensure_ascii=False), ex=cls.TTL_SECONDS)

    @staticmethod
    def _deserialize(value: str | bytes | None) -> dict[str, Any]:
        """
        将 Redis 中的 JSON 进度快照转换为接口响应对象。
        :param value: Redis 返回的字符串或字节值
        :return: 有效进度快照；缺失或损坏时返回空闲状态
        """
        default_progress = {
            "stage": "idle",
            "downloading": False,
            "percentage": 0,
            "downloaded": 0,
            "total": 0,
            "source": "",
            "message": "",
            "updatedAt": None,
        }
        if not value:
            return default_progress
        try:
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            snapshot = json.loads(value)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return default_progress
        return {**default_progress, **snapshot} if isinstance(snapshot, dict) else default_progress

    @staticmethod
    def _build_key(ticket_id: int, record_id: int | None) -> str:
        """
        构造 Redis 进度快照使用的稳定键。
        :param ticket_id: 工单ID
        :param record_id: 日志拉取记录ID
        :return: 工单和记录组合键
        """
        return f"{TicketLogPrepareProgressService.KEY_PREFIX}:{ticket_id}:{record_id or 0}"
