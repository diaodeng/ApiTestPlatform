from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from dns.e164 import query
from loguru import logger
from sqlalchemy import or_
from sqlalchemy.orm import Session, defer

from module_admin.entity.do.config_do import SysConfig
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullQueryModel
from utils.page_util import PageUtil


class TicketLogPullDao:
    """
    工单日志拉取数据库访问层。
    """

    CONFIG_KEY = "ticket.logPull.storage"
    CONFIG_NAME = "工单日志拉取存储配置"
    EXTERNAL_CONFIG_KEY = "ticket.logPull.external"
    EXTERNAL_CONFIG_NAME = "工单日志拉取外部接口配置"

    @classmethod
    def add_record(cls, db: Session, record: TicketLogPullRecord) -> TicketLogPullRecord:
        """
        新增日志拉取记录。
        :param db: 数据库会话
        :param record: 日志拉取记录对象
        :return: 保存后的记录
        """
        db.add(record)
        db.flush()
        return record

    @classmethod
    def get_record_by_id(cls, db: Session, record_id: int) -> TicketLogPullRecord | None:
        """
        根据记录ID查询日志拉取记录。
        :param db: 数据库会话
        :param record_id: 记录ID
        :return: 记录对象
        """
        return db.query(TicketLogPullRecord).filter(TicketLogPullRecord.id == record_id).first()

    @classmethod
    def update_record(cls, db: Session, record_id: int, data: dict) -> None:
        """
        更新日志拉取记录字段。
        :param db: 数据库会话
        :param record_id: 记录ID
        :param data: 待更新字段
        :return: 无
        """
        db.query(TicketLogPullRecord).filter(TicketLogPullRecord.id == record_id).update(data)

    @classmethod
    def list_ticket_records(cls, db: Session, query: TicketLogPullQueryModel):
        """
        分页查询指定工单的日志拉取记录。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果
        """
        record_query = (
            db.query(TicketLogPullRecord)
            .options(
                defer(TicketLogPullRecord.compressed_content),
                defer(TicketLogPullRecord.exception_detail),
            )
            .filter(
                TicketLogPullRecord.ticket_id == query.ticket_id,
                TicketLogPullRecord.status == query.status if query.status else True,
            )
            .order_by(TicketLogPullRecord.create_time.desc(), TicketLogPullRecord.id.desc())
        )
        return PageUtil.paginate(record_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_log_pull_records(cls, db: Session, query: TicketLogPullQueryModel):
        """
        分页查询日志拉取管理记录。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        keyword = str(query.keyword or "").strip()
        ticket_no = str(query.ticket_no or "").strip()
        search_texts = [text for text in (keyword, ticket_no) if text]
        search_filters = []
        for text in search_texts:
            search_filters.extend(
                [
                    TicketLogPullRecord.status_desc.like(f"%{text}%"),
                    TicketLogPullRecord.error_message.like(f"%{text}%"),
                    TicketLogPullRecord.content_summary.like(f"%{text}%"),
                    TicketLogPullRecord.storage_path.like(f"%{text}%"),
                    TicketLogPullRecord.command_result_url.like(f"%{text}%"),
                    TicketLogPullRecord.external_serial_number.like(f"%{text}%"),
                    Ticket.ticket_no.like(f"%{text}%"),
                    Ticket.title.like(f"%{text}%"),
                    Ticket.merchant_name.like(f"%{text}%"),
                ]
            )

        record_query = (
            db.query(TicketLogPullRecord)
            .options(
                defer(TicketLogPullRecord.compressed_content),
                defer(TicketLogPullRecord.exception_detail),
            )
            .outerjoin(Ticket, Ticket.ticket_id == TicketLogPullRecord.ticket_id)
            .filter(
                TicketLogPullRecord.ticket_id == query.ticket_id if query.ticket_id is not None else True,
                TicketLogPullRecord.status == query.status if query.status else True,
            )
            .filter(or_(*search_filters) if search_filters else True)
            .order_by(TicketLogPullRecord.create_time.desc(), TicketLogPullRecord.id.desc())
        )
        return PageUtil.paginate(record_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_latest_records_by_ticket_ids(
        cls, db: Session, ticket_ids: Iterable[int]
    ) -> dict[int, TicketLogPullRecord]:
        """
        查询工单最新一条日志拉取记录。
        :param db: 数据库会话
        :param ticket_ids: 工单ID集合
        :return: 以工单ID为键的最新记录映射
        """
        ticket_id_list = [ticket_id for ticket_id in ticket_ids if ticket_id]
        if not ticket_id_list:
            return {}
        rows = (
            db.query(TicketLogPullRecord)
            .options(
                defer(TicketLogPullRecord.compressed_content),
                defer(TicketLogPullRecord.exception_detail),
            )
            .filter(TicketLogPullRecord.ticket_id.in_(ticket_id_list))
            .order_by(TicketLogPullRecord.create_time.desc(), TicketLogPullRecord.id.desc())
            .all()
        )
        record_map: dict[int, TicketLogPullRecord] = {}
        for row in rows:
            record_map.setdefault(row.ticket_id, row)
        return record_map

    @classmethod
    def list_recoverable_records(cls, db: Session, statuses: Iterable[str]) -> list[TicketLogPullRecord]:
        """
        查询需要恢复执行的日志拉取记录。
        :param db: 数据库会话
        :param statuses: 可恢复状态列表
        :return: 记录列表
        """
        status_list = [status for status in statuses if status]
        if not status_list:
            return []
        return (
            db.query(TicketLogPullRecord)
            .options(
                defer(TicketLogPullRecord.compressed_content),
                defer(TicketLogPullRecord.exception_detail),
            )
            .filter(TicketLogPullRecord.status.in_(status_list))
            .order_by(TicketLogPullRecord.create_time.asc(), TicketLogPullRecord.id.asc())
            .all()
        )

    @classmethod
    def get_storage_config_row(cls, db: Session) -> SysConfig | None:
        """
        获取日志拉取存储配置记录。
        :param db: 数据库会话
        :return: 系统参数记录
        """
        return cls.get_config_row(db, cls.CONFIG_KEY)

    @classmethod
    def get_external_config_row(cls, db: Session) -> SysConfig | None:
        """
        获取日志拉取外部接口配置记录。
        :param db: 数据库会话
        :return: 系统参数记录
        """
        return cls.get_config_row(db, cls.EXTERNAL_CONFIG_KEY)

    @classmethod
    def get_config_row(cls, db: Session, config_key: str) -> SysConfig | None:
        """
        按参数键获取系统参数记录。
        :param db: 数据库会话
        :param config_key: 参数键名
        :return: 系统参数记录
        """
        config_row = db.query(SysConfig).filter(SysConfig.config_key == config_key).first()
        logger.info(f"获取到的外部配置：{config_key}:{config_row.config_value if config_row else None}")
        return config_row

    @classmethod
    def save_storage_config_row(
        cls,
        db: Session,
        *,
        config_value: str,
        user_name: str,
        remark: str = "工单日志拉取存储与轮询配置",
    ) -> None:
        """
        新增或更新日志拉取存储配置。
        :param db: 数据库会话
        :param config_value: JSON配置值
        :param user_name: 当前操作用户名
        :param remark: 配置备注
        :return: 无
        """
        cls.save_config_row(
            db,
            config_key=cls.CONFIG_KEY,
            config_name=cls.CONFIG_NAME,
            config_value=config_value,
            user_name=user_name,
            remark=remark,
        )

    @classmethod
    def save_external_config_row(
        cls,
        db: Session,
        *,
        config_value: str,
        user_name: str,
        remark: str = "工单日志拉取外部地址、Cookie 和请求头配置",
    ) -> None:
        """
        新增或更新日志拉取外部接口配置。
        :param db: 数据库会话
        :param config_value: JSON配置值
        :param user_name: 当前操作用户名
        :param remark: 配置备注
        :return: 无
        """
        cls.save_config_row(
            db,
            config_key=cls.EXTERNAL_CONFIG_KEY,
            config_name=cls.EXTERNAL_CONFIG_NAME,
            config_value=config_value,
            user_name=user_name,
            remark=remark,
        )

    @classmethod
    def save_config_row(
        cls,
        db: Session,
        *,
        config_key: str,
        config_name: str,
        config_value: str,
        user_name: str,
        remark: str,
    ) -> None:
        """
        新增或更新指定系统参数配置。
        :param db: 数据库会话
        :param config_key: 参数键名
        :param config_name: 参数名称
        :param config_value: 参数值
        :param user_name: 当前操作用户名
        :param remark: 配置备注
        :return: 无
        """
        existing = cls.get_config_row(db, config_key)
        now = datetime.now()
        if existing:
            existing.config_name = existing.config_name or config_name
            existing.config_value = config_value
            existing.update_by = user_name
            existing.update_time = now
            existing.remark = remark
            db.flush()
            return
        db.add(
            SysConfig(
                config_name=config_name,
                config_key=config_key,
                config_value=config_value,
                config_type="N",
                create_by=user_name,
                update_by=user_name,
                create_time=now,
                update_time=now,
                remark=remark,
            )
        )
        db.flush()
