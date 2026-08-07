import json
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig


class TicketStatisticsTimeUtil:
    """
    工单统计时间配置工具，只负责系统参数归一化和默认时间范围计算。
    """

    CONFIG_KEY = "ticket.statistics.time.config"
    DEFAULT_CONFIG: dict[str, Any] = {
        "defaultRangeMode": "business_week",
        "rollingDays": 7,
        "businessWeekStartWeekday": 4,
        "businessWeekStartTime": "18:00:00",
        "businessWeekDefaultWindow": "current",
        "trendWeekBucketMode": "business_week",
    }

    @classmethod
    def ensure_default_config(cls, query_db: Session, now: datetime | None = None) -> dict[str, Any]:
        """
        确保统计时间配置存在，并返回当前默认时间范围。
        :param query_db: 数据库会话。
        :param now: 可选当前时间，单测可注入。
        :return: 配置、默认范围和展示文案。
        """
        config_info = ConfigDao.get_config_detail_by_key(query_db, cls.CONFIG_KEY)
        if not config_info:
            query_db.add(
                SysConfig(
                    config_name="工单统计默认时间配置",
                    config_key=cls.CONFIG_KEY,
                    config_value=json.dumps(cls.DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                    config_type="Y",
                    create_by="system",
                    update_by="system",
                    remark="配置工单统计页默认时间范围和周趋势分桶口径",
                )
            )
            query_db.flush()
            query_db.commit()
        config = cls.get_config(query_db)
        default_range = cls.get_default_range(config, now=now)
        return {
            "config": config,
            "defaultRange": default_range,
            "rangeLabel": cls.get_range_label(config, default_range),
            "snapshotBusinessWeekSupported": True,
        }

    @classmethod
    def get_config(cls, query_db: Session) -> dict[str, Any]:
        """
        读取并规范化统计时间配置。
        :param query_db: 数据库会话。
        :return: 规范化配置。
        """
        config = dict(cls.DEFAULT_CONFIG)
        config_info = ConfigDao.get_config_detail_by_key(query_db, cls.CONFIG_KEY)
        raw_value = getattr(config_info, "config_value", None)
        if raw_value:
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, dict):
                    config.update(parsed)
            except Exception:
                pass
        return cls.normalize_config(config)

    @classmethod
    def normalize_config(cls, config: dict[str, Any] | None) -> dict[str, Any]:
        """
        规范化配置字段，避免非法参数影响统计页初始化。
        :param config: 原始配置。
        :return: 规范化配置。
        """
        source = config if isinstance(config, dict) else {}
        result = dict(cls.DEFAULT_CONFIG)
        result.update(source)
        if result.get("defaultRangeMode") not in {"rolling_days", "business_week"}:
            result["defaultRangeMode"] = cls.DEFAULT_CONFIG["defaultRangeMode"]
        if result.get("businessWeekDefaultWindow") not in {"current", "previous_completed"}:
            result["businessWeekDefaultWindow"] = cls.DEFAULT_CONFIG["businessWeekDefaultWindow"]
        if result.get("trendWeekBucketMode") not in {"calendar_week", "business_week"}:
            result["trendWeekBucketMode"] = cls.DEFAULT_CONFIG["trendWeekBucketMode"]
        result["rollingDays"] = cls.safe_int(result.get("rollingDays"), 7, 1, 366)
        result["businessWeekStartWeekday"] = cls.safe_int(result.get("businessWeekStartWeekday"), 4, 1, 7)
        result["businessWeekStartTime"] = cls.normalize_time_text(result.get("businessWeekStartTime"))
        return result

    @classmethod
    def get_default_range(cls, config: dict[str, Any] | None, now: datetime | None = None) -> dict[str, str]:
        """
        根据配置计算默认日期范围。
        :param config: 规范化配置。
        :param now: 可选当前时间。
        :return: beginTime/endTime 日期字符串。
        """
        active_config = cls.normalize_config(config)
        current = now or datetime.now()
        if active_config["defaultRangeMode"] == "rolling_days":
            rolling_days = cls.safe_int(active_config.get("rollingDays"), 7, 1, 366)
            begin_date = current.date() - timedelta(days=rolling_days - 1)
            end_date = current.date()
            return {
                "beginTime": datetime.combine(begin_date, time.min).strftime("%Y-%m-%d %H:%M:%S"),
                "endTime": datetime.combine(end_date, time.max).strftime("%Y-%m-%d %H:%M:%S"),
            }
        window = str(active_config.get("businessWeekDefaultWindow") or "current")
        start_dt, end_dt = cls.get_business_week_range(active_config, current, window)
        return {
            "beginTime": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def get_range_label(cls, config: dict[str, Any] | None, default_range: dict[str, str]) -> str:
        """
        生成默认范围展示文案，区分滚动天数和业务周。
        :param config: 规范化配置。
        :param default_range: 默认时间范围。
        :return: 中文文案。
        """
        active_config = cls.normalize_config(config)
        begin_time = default_range.get("beginTime")
        end_time = default_range.get("endTime")
        if active_config["defaultRangeMode"] == "rolling_days":
            return f"最近 {active_config['rollingDays']} 天（{begin_time} 至 {end_time}）"
        if active_config.get("businessWeekDefaultWindow") == "previous_completed":
            return f"上一完整业务周（{begin_time} 至 {end_time}）"
        return f"当前业务周（{begin_time} 至 {end_time}）"

    @classmethod
    def get_business_week_range(
        cls,
        config: dict[str, Any] | None,
        now: datetime,
        window: str = "current",
    ) -> tuple[datetime, datetime]:
        """
        计算当前或上一完整业务周的起止时间。
        :param config: 规范化配置。
        :param now: 当前时间。
        :param window: current 或 previous_completed。
        :return: 起止 datetime，结束时间为业务周结束前一秒。
        """
        start_dt = cls.business_week_start_for_time(now, config)
        if window == "previous_completed":
            start_dt = start_dt - timedelta(days=7)
        end_dt = start_dt + timedelta(days=7) - timedelta(seconds=1)
        return start_dt, end_dt

    @classmethod
    def business_week_start_for_time(cls, value: datetime, config: dict[str, Any] | None) -> datetime:
        """
        计算指定时间所属业务周的开始时间。
        :param value: 事件时间。
        :param config: 规范化配置。
        :return: 业务周开始时间。
        """
        active_config = cls.normalize_config(config)
        # 配置对用户使用 1-7 表示周一到周日，计算时转换为 Python weekday 的 0-6。
        weekday = active_config["businessWeekStartWeekday"] - 1
        start_time = time.fromisoformat(active_config["businessWeekStartTime"])
        days_since_start = (value.weekday() - weekday) % 7
        candidate_date = value.date() - timedelta(days=days_since_start)
        candidate = datetime.combine(candidate_date, start_time)
        if value < candidate:
            candidate -= timedelta(days=7)
        return candidate

    @classmethod
    def business_week_bucket_key(cls, value: datetime, config: dict[str, Any] | None) -> date:
        """
        获取业务周趋势桶日期键。
        :param value: 事件时间。
        :param config: 规范化配置。
        :return: 业务周开始日期。
        """
        return cls.business_week_start_for_time(value, config).date()

    @staticmethod
    def normalize_time_text(value: Any) -> str:
        """
        规范化时间文本，非法值回退到 18:00:00。
        :param value: 原始时间。
        :return: HH:MM:SS。
        """
        text = str(value or "").strip()
        try:
            return time.fromisoformat(text).strftime("%H:%M:%S")
        except Exception:
            return "18:00:00"

    @staticmethod
    def safe_int(value: Any, default: int, min_value: int, max_value: int) -> int:
        """
        安全解析整数并限制范围。
        :param value: 原始值。
        :param default: 默认值。
        :param min_value: 最小值。
        :param max_value: 最大值。
        :return: 整数。
        """
        try:
            parsed = int(value)
        except Exception:
            parsed = default
        return min(max(parsed, min_value), max_value)
