from datetime import timedelta

from celery.schedules import crontab, schedule


def _normalize_day_of_month(day_of_month: str) -> str:
    """
    归一化 day-of-month 字段，过滤 Celery 不支持的 Quartz 语法。

    :param day_of_month: 日字段表达式。
    :return: Celery 支持的日字段。
    """
    normalized = (day_of_month or "*").strip()
    if normalized == "?":
        return "*"
    for token in ("L", "W", "#"):
        if token in normalized:
            raise ValueError("当前不支持 day 字段 L/W/# 语法")
    return normalized


def _normalize_day_of_week(day_of_week: str) -> str:
    """
    将 Quartz 风格星期字段转换为 Celery crontab 格式。

    :param day_of_week: 星期表达式。
    :return: Celery 支持的星期字段。
    """
    normalized = (day_of_week or "*").strip()
    if normalized in {"?", "*"}:
        return "*"
    for token in ("L", "W", "#"):
        if token in normalized:
            raise ValueError(f"不支持的星期语法: {day_of_week}")

    def convert_token(token: str) -> str:
        if not token.isdigit():
            return token
        number = int(token)
        if number in (0, 7):
            return "0"
        if 1 <= number <= 6:
            return str(number - 1)
        return token

    parts = []
    for piece in normalized.split(","):
        value = piece.strip()
        if "-" in value:
            start, end = [item.strip() for item in value.split("-", 1)]
            parts.append(f"{convert_token(start)}-{convert_token(end)}")
        else:
            parts.append(convert_token(value))
    return ",".join(parts)


def _normalize_celery_day_of_week(day_of_week: str) -> str:
    """
    归一化 Celery 5 位 cron 的星期字段（0-6，0 表示周日）。

    :param day_of_week: 星期表达式。
    :return: Celery 兼容星期字段。
    """
    normalized = (day_of_week or "*").strip()
    if normalized in {"?", "*"}:
        return "*"
    for token in ("L", "W", "#"):
        if token in normalized:
            raise ValueError(f"不支持的星期语法: {day_of_week}")

    def normalize_token(token: str) -> str:
        if token == "7":
            return "0"
        return token

    parts = []
    for piece in normalized.split(","):
        value = piece.strip()
        if "-" in value:
            start, end = [item.strip() for item in value.split("-", 1)]
            parts.append(f"{normalize_token(start)}-{normalize_token(end)}")
        elif "/" in value:
            base, step = [item.strip() for item in value.split("/", 1)]
            parts.append(f"{normalize_token(base)}/{step}")
        else:
            parts.append(normalize_token(value))
    return ",".join(parts)


def _parse_quartz_cron(expression: str):
    """
    解析 6/7 位 Quartz cron 并转换成 Celery schedule。

    :param expression: Quartz cron 表达式。
    :return: Celery schedule 对象。
    """
    values = expression.split()
    if len(values) not in (6, 7):
        raise ValueError(f"Quartz cron 字段数量错误: {len(values)}")

    second, minute, hour, day, month, day_of_week = values[:6]
    year = values[6] if len(values) == 7 else "*"
    if year not in {"*", "?"}:
        raise ValueError("当前不支持按年份调度")

    day = _normalize_day_of_month(day)
    month = "*" if month == "?" else month
    day_of_week = _normalize_day_of_week(day_of_week)

    all_wildcard = minute == hour == day == month == day_of_week == "*"
    if "/" in second and all_wildcard:
        base, step = second.split("/", 1)
        if base in {"0", "*"} and step.isdigit() and int(step) > 0:
            return schedule(run_every=timedelta(seconds=int(step)))

    if second != "0":
        raise ValueError("Celery crontab 不支持秒字段，需固定为 0 或使用 interval")

    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day,
        month_of_year=month,
        day_of_week=day_of_week,
    )


def normalize_cron_expression(expression: str) -> str:
    """
    归一化 cron 字符串为 Celery 原生 5 位表达式（min hour day month week）。

    :param expression: 原始 cron 表达式，支持 5/6/7 位输入。
    :return: 归一化后的 5 位表达式。
    """
    if not expression:
        raise ValueError("cron 表达式不能为空")
    values = expression.split()
    if len(values) == 5:
        minute, hour, day, month, day_of_week = values
        day = _normalize_day_of_month(day)
        month = "*" if month == "?" else month
        day_of_week = _normalize_celery_day_of_week(day_of_week)
        return f"{minute} {hour} {day} {month} {day_of_week}"

    if len(values) not in (6, 7):
        raise ValueError("cron 表达式字段数量错误，仅支持 5/6/7 位")

    second, minute, hour, day, month, day_of_week = values[:6]
    year = values[6] if len(values) == 7 else "*"
    if year not in {"*", "?"}:
        raise ValueError("当前不支持按年份调度")
    if second != "0":
        raise ValueError("Celery crontab 不支持秒字段，需固定为 0 或使用 interval")

    day = _normalize_day_of_month(day)
    month = "*" if month == "?" else month
    day_of_week = _normalize_day_of_week(day_of_week)
    return f"{minute} {hour} {day} {month} {day_of_week}"


def parse_cron_to_schedule(expression: str):
    """
    解析 cron 表达式为 Celery schedule，支持 5 位 crontab 与 6/7 位 Quartz。

    :param expression: cron 表达式。
    :return: Celery schedule 对象。
    """
    if not expression:
        raise ValueError("cron 表达式不能为空")
    values = expression.split()
    if len(values) == 5:
        minute, hour, day, month, day_of_week = values
        day = _normalize_day_of_month(day)
        month = "*" if month == "?" else month
        day_of_week = _normalize_celery_day_of_week(day_of_week)
        return crontab(
            minute=minute,
            hour=hour,
            day_of_month=day,
            month_of_year=month,
            day_of_week=day_of_week,
        )
    return _parse_quartz_cron(expression)


def build_interval_schedule(every: int, period: str):
    """
    构建间隔调度对象。

    :param every: 间隔步长。
    :param period: 间隔单位，支持 seconds/minutes/hours/days。
    :return: Celery interval schedule。
    """
    if every <= 0:
        raise ValueError("interval_every 必须大于 0")
    normalized_period = (period or "").strip().lower()
    if normalized_period == "seconds":
        return schedule(run_every=timedelta(seconds=every))
    if normalized_period == "minutes":
        return schedule(run_every=timedelta(minutes=every))
    if normalized_period == "hours":
        return schedule(run_every=timedelta(hours=every))
    if normalized_period == "days":
        return schedule(run_every=timedelta(days=every))
    raise ValueError(f"不支持的 interval_period: {period}")
