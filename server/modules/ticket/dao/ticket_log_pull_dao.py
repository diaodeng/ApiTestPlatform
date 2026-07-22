from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from loguru import logger
from sqlalchemy import Date, cast, func, or_
from sqlalchemy.orm import Session, defer

from module_admin.entity.do.config_do import SysConfig
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.do.ticket_log_pull_do import (
    TicketLogPullProjectVendorMap,
    TicketLogPullRecord,
    TicketLogPullStoreConfig,
)
from modules.ticket.entity.vo.ticket_log_pull_vo import (
    TicketLogPullProjectVendorMapQueryModel,
    TicketLogPullQueryModel,
    TicketLogPullStoreConfigQueryModel,
)
from utils.page_util import PageUtil


class TicketLogPullDao:
    """
    工单日志拉取数据库访问层。
    """

    CONFIG_KEY = "ticket.logPull.storage"
    CONFIG_NAME = "工单日志拉取存储配置"
    EXTERNAL_CONFIG_KEY = "ticket.logPull.external"
    PARAM_EXAMPLE_CONFIG_KEY = "ticket.logPull.parameterExamples"
    PARAM_EXAMPLE_CONFIG_NAME = "工单日志拉取参数示例配置"
    EXTERNAL_CONFIG_NAME = "工单日志拉取外部接口配置"
    VENDOR_CONFIG_KEY = "ticket.logPull.vendors"
    VENDOR_CONFIG_NAME = "工单日志拉取商家配置"

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
    def get_latest_success_record_by_ticket_id(cls, db: Session, ticket_id: int) -> TicketLogPullRecord | None:
        """
        查询指定工单最近一条成功的日志拉取记录。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 成功的日志拉取记录，未命中返回 None
        """
        return (
            db.query(TicketLogPullRecord)
            .filter(
                TicketLogPullRecord.ticket_id == ticket_id,
                TicketLogPullRecord.status == "success",
            )
            .order_by(TicketLogPullRecord.create_time.desc(), TicketLogPullRecord.id.desc())
            .first()
        )

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
        modify_time = query.modify_time
        if isinstance(modify_time, str):
            modify_time = modify_time.strip() or None
            if modify_time:
                modify_time = date.fromisoformat(modify_time)
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
                TicketLogPullRecord.vendor_id == query.vendor_id if query.vendor_id is not None else True,
                TicketLogPullRecord.store_id == query.store_id if query.store_id is not None else True,
                TicketLogPullRecord.pos_no == query.pos_no if query.pos_no is not None else True,
                cast(TicketLogPullRecord.command_content["modifyTime"].as_string(), Date) == modify_time
                if modify_time
                else True,
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
    def get_param_example_config_row(cls, db: Session) -> SysConfig | None:
        """
        获取日志拉取参数示例配置记录。
        :param db: 数据库会话
        :return: 系统参数记录
        """
        return cls.get_config_row(db, cls.PARAM_EXAMPLE_CONFIG_KEY)

    @classmethod
    def get_vendor_config_row(cls, db: Session) -> SysConfig | None:
        """
        获取日志拉取商家参数配置记录。
        :param db: 数据库会话
        :return: 系统参数记录
        """
        return cls.get_config_row(db, cls.VENDOR_CONFIG_KEY)

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

    @classmethod
    def list_store_configs(cls, db: Session, query: TicketLogPullStoreConfigQueryModel):
        """
        分页查询门店配置。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果
        """
        keyword = str(query.keyword or "").strip()
        filters = []
        if keyword:
            filters.extend(
                [
                    TicketLogPullStoreConfig.group_no.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.vender_no.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.org_no.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.sap_org_no.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.org_name.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.platform_no.like(f"%{keyword}%"),
                    TicketLogPullStoreConfig.company_no.like(f"%{keyword}%"),
                ]
            )
        record_query = db.query(TicketLogPullStoreConfig).filter(
            TicketLogPullStoreConfig.group_no == query.group_no if query.group_no else True,
            TicketLogPullStoreConfig.vender_no == query.vender_no if query.vender_no else True,
            TicketLogPullStoreConfig.org_no == query.org_no if query.org_no else True,
            TicketLogPullStoreConfig.sap_org_no == query.sap_org_no if query.sap_org_no else True,
        )
        if filters:
            record_query = record_query.filter(or_(*filters))
        record_query = record_query.order_by(
            TicketLogPullStoreConfig.modifid.desc(), TicketLogPullStoreConfig.id.desc()
        )
        return PageUtil.paginate(record_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_all_store_configs(cls, db: Session) -> list[TicketLogPullStoreConfig]:
        """
        查询全部门店配置。
        :param db: 数据库会话
        :return: 配置列表
        """
        return (
            db.query(TicketLogPullStoreConfig)
            .order_by(TicketLogPullStoreConfig.modifid.desc(), TicketLogPullStoreConfig.id.desc())
            .all()
        )

    @classmethod
    def list_store_configs_by_vender_no(cls, db: Session, vender_no: str) -> list[TicketLogPullStoreConfig]:
        """
        按商户编号查询门店配置，供日志拉取弹窗按需加载门店。
        :param db: 数据库会话
        :param vender_no: 商户编号
        :return: 当前商户下的门店配置列表
        """
        resolved_vender_no = str(vender_no or "").strip()
        if not resolved_vender_no:
            return []
        return (
            db.query(TicketLogPullStoreConfig)
            .filter(TicketLogPullStoreConfig.vender_no == resolved_vender_no)
            .order_by(TicketLogPullStoreConfig.org_name.asc(), TicketLogPullStoreConfig.id.asc())
            .all()
        )

    @classmethod
    def get_store_config_by_match(
        cls, db: Session, *, vender_no: str = "", org_no: str = "", sap_org_no: str = ""
    ) -> TicketLogPullStoreConfig | None:
        """
        按 vender_no + org_no + sap_org_no 联合唯一键查找门店配置。
        :param db: 数据库会话
        :param vender_no: 商户编号
        :param org_no: 机构编号
        :param sap_org_no: SAP机构编号
        :return: 匹配到的配置
        """
        query = db.query(TicketLogPullStoreConfig)
        vender_no = str(vender_no or "").strip()
        org_no = str(org_no or "").strip()
        sap_org_no = str(sap_org_no or "").strip()
        return (
            query.filter(
                func.coalesce(TicketLogPullStoreConfig.vender_no, "") == vender_no,
                func.coalesce(TicketLogPullStoreConfig.org_no, "") == org_no,
                func.coalesce(TicketLogPullStoreConfig.sap_org_no, "") == sap_org_no,
            )
            .order_by(TicketLogPullStoreConfig.modifid.desc())
            .first()
        )

    @classmethod
    def save_store_config(cls, db: Session, store: TicketLogPullStoreConfig) -> TicketLogPullStoreConfig:
        """
        新增或更新门店配置。
        :param db: 数据库会话
        :param store: 门店配置对象
        :return: 保存后的对象
        """
        existing = None
        if store.org_no or store.sap_org_no or store.vender_no:
            existing = cls.get_store_config_by_match(
                db,
                vender_no=store.vender_no,
                org_no=store.org_no or "",
                sap_org_no=store.sap_org_no or "",
            )
        if existing:
            for field in (
                "group_no",
                "vender_no",
                "region_no",
                "org_no",
                "org_name",
                "sap_org_no",
                "platform_no",
                "parent_org_no",
                "perm_node_id",
                "org_type",
                "company_no",
                "city_no",
                "biz_type_no",
                "status",
                "created",
                "modifid",
                "open_date",
                "language_desc",
            ):
                setattr(existing, field, getattr(store, field))
            db.flush()
            return existing
        db.add(store)
        db.flush()
        return store

    @classmethod
    def delete_all_store_configs(cls, db: Session) -> int:
        """
        清空门店配置表。
        :param db: 数据库会话
        :return: 受影响行数
        """
        return db.query(TicketLogPullStoreConfig).delete(synchronize_session=False)

    @classmethod
    def list_project_vendor_maps(
        cls, db: Session, query: TicketLogPullProjectVendorMapQueryModel
    ) -> list[TicketLogPullProjectVendorMap] | PageUtil:
        """
        查询项目商家映射。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 列表或分页结果
        """
        keyword = str(query.keyword or "").strip()
        record_query = db.query(TicketLogPullProjectVendorMap).filter(
            TicketLogPullProjectVendorMap.project_id == query.project_id if query.project_id else True
        )
        if keyword:
            record_query = record_query.filter(
                or_(
                    TicketLogPullProjectVendorMap.project_name.like(f"%{keyword}%"),
                    TicketLogPullProjectVendorMap.vender_no.like(f"%{keyword}%"),
                )
            )
        record_query = record_query.order_by(
            TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc()
        )
        return PageUtil.paginate(record_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_all_project_vendor_maps(cls, db: Session) -> list[TicketLogPullProjectVendorMap]:
        """
        查询全部项目商家映射。
        :param db: 数据库会话
        :return: 映射列表
        """
        return (
            db.query(TicketLogPullProjectVendorMap)
            .order_by(TicketLogPullProjectVendorMap.modifid.desc(), TicketLogPullProjectVendorMap.id.desc())
            .all()
        )

    @classmethod
    def get_project_vendor_map_by_project_id(
        cls, db: Session, project_id: int
    ) -> TicketLogPullProjectVendorMap | None:
        """
        根据项目ID获取商家映射。
        :param db: 数据库会话
        :param project_id: 项目ID
        :return: 映射对象
        """
        return (
            db.query(TicketLogPullProjectVendorMap)
            .filter(TicketLogPullProjectVendorMap.project_id == project_id)
            .first()
        )

    @classmethod
    def save_project_vendor_map(
        cls, db: Session, project_vendor_map: TicketLogPullProjectVendorMap
    ) -> TicketLogPullProjectVendorMap:
        """
        新增或更新项目商家映射。
        :param db: 数据库会话
        :param project_vendor_map: 映射对象
        :return: 保存后的对象
        """
        existing = cls.get_project_vendor_map_by_project_id(db, project_vendor_map.project_id)
        if existing:
            existing.project_name = project_vendor_map.project_name
            existing.vender_no = project_vendor_map.vender_no
            existing.modifid = project_vendor_map.modifid
            db.flush()
            return existing
        db.add(project_vendor_map)
        db.flush()
        return project_vendor_map
