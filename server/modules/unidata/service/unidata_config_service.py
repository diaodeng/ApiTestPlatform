"""大数据查询数据源配置服务：sys_config 键 unidata.query.sources 的读取、校验与懒初始化。

配置格式（参数设置页面维护，值本身不含任何密钥）：
{
    "sources": [
        {
            "code": "uat",
            "name": "UAT 大数据",
            "baseUrl": "https://uatopen-d.rta-os.com",
            "workbenchCode": "ddw_trade",
            "credentialBindingId": "3",
            "defaultEngine": "kyuubi",
            "enabled": true,
            "remark": "UAT 环境"
        }
    ]
}

凭证明文不入配置：baseUrl 指向的目标域名 + credentialBindingId 引用统一凭证绑定，
请求头由凭证投影服务解析。
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.dao.config_dao import ConfigDao
from module_admin.entity.do.config_do import SysConfig
from modules.unidata.entity.vo.unidata_vo import UnidataSourceModel
from utils.log_util import logger

# 系统参数键：大数据查询数据源配置
UNIDATA_SOURCES_CONFIG_KEY = "unidata.query.sources"


class UnidataConfigService:
    """大数据查询数据源配置的业务服务。"""

    @classmethod
    def _seed_config_row(cls, db: Session) -> SysConfig:
        """构造一条空的默认配置行（未提交），由调用方决定是否落库。"""
        now = datetime.now()
        payload = {"sources": []}
        return SysConfig(
            config_name="大数据查询数据源配置",
            config_key=UNIDATA_SOURCES_CONFIG_KEY,
            config_value=json.dumps(payload, ensure_ascii=False),
            config_type="Y",
            create_by="system",
            update_by="system",
            create_time=now,
            update_time=now,
            remark="大数据查询（Unidata）数据源清单，JSON：sources[].code/name/baseUrl/workbenchCode/credentialBindingId/defaultEngine/enabled",
        )

    @classmethod
    def _load_config_row(cls, db: Session) -> SysConfig | None:
        """读取配置行，不存在时返回 None。"""
        return ConfigDao.get_config_detail_by_key(db, UNIDATA_SOURCES_CONFIG_KEY)

    @classmethod
    def list_sources(cls, db: Session) -> list[UnidataSourceModel]:
        """读取全部已配置数据源；配置行不存在时懒初始化一条空配置。

        :param db: 数据库会话
        :return: 数据源模型列表（解析失败的条目跳过并记录告警，不做静默兜底掩盖配置错误）
        """
        row = cls._load_config_row(db)
        if row is None:
            row = cls._seed_config_row(db)
            db.add(row)
            db.commit()
            db.refresh(row)
            logger.info(f"已初始化大数据查询数据源默认配置: key={UNIDATA_SOURCES_CONFIG_KEY}")
        try:
            parsed = json.loads(row.config_value or "")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"大数据查询配置 JSON 解析失败，请检查系统参数 {UNIDATA_SOURCES_CONFIG_KEY}") from exc
        sources = parsed.get("sources") if isinstance(parsed, dict) else None
        if not isinstance(sources, list):
            sources = []
        result: list[UnidataSourceModel] = []
        for item in sources:
            if not isinstance(item, dict):
                continue
            try:
                result.append(UnidataSourceModel.model_validate(item))
            except Exception as exc:
                logger.warning(f"大数据查询数据源配置条目非法已跳过: item={item}，error={exc}")
        return result

    @classmethod
    def list_enabled_source_options(cls, db: Session) -> list[dict]:
        """返回启用数据源的下拉选项（仅 code/name/defaultEngine）。"""
        return [
            {"code": source.code, "name": source.name, "defaultEngine": source.default_engine}
            for source in cls.list_sources(db)
            if source.enabled
        ]

    @classmethod
    def get_enabled_source(cls, db: Session, source_code: str) -> UnidataSourceModel:
        """按编码取启用的数据源；未配置或停用时报明确错误。"""
        for source in cls.list_sources(db):
            if source.code == source_code:
                if not source.enabled:
                    raise ValueError(f"大数据查询数据源 '{source_code}' 已停用，请在参数设置中启用后再试")
                return source
        raise ValueError(f"大数据查询数据源 '{source_code}' 未配置，请在系统参数 {UNIDATA_SOURCES_CONFIG_KEY} 中维护")
