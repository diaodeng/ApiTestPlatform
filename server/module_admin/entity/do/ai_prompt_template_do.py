from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, UniqueConstraint

from config.database import Base
from config.sqlalchemy_types import long_text_type


class SysAiPromptTemplate(Base):
    """
    AI 提示词模板配置表，保存不同任务的提示词内容和分类。
    """

    __tablename__ = "sys_ai_prompt_template"
    __table_args__ = (UniqueConstraint("template_code", name="uq_sys_ai_prompt_template_template_code"),)

    template_id = Column(Integer, primary_key=True, autoincrement=True, comment="提示词模板主键")
    template_code = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="模板编码")
    template_name = Column(String(128, collation="utf8_general_ci"), nullable=False, comment="模板名称")
    template_category = Column(String(64, collation="utf8_general_ci"), nullable=False, comment="模板分类")
    provider_code = Column(String(64, collation="utf8_general_ci"), nullable=True, default="", comment="默认Provider编码")
    model_name = Column(String(128, collation="utf8_general_ci"), nullable=True, default="", comment="默认模型名称")
    prompt_content = Column(long_text_type(), nullable=False, comment="提示词内容")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    sort = Column(Integer, nullable=False, default=0, comment="排序")
    extra_config = Column(JSON, nullable=True, comment="扩展配置")
    create_by = Column(String(64, collation="utf8_general_ci"), default="", comment="创建者")
    create_time = Column(DateTime, comment="创建时间", default=datetime.now)
    update_by = Column(String(64, collation="utf8_general_ci"), default="", comment="更新者")
    update_time = Column(DateTime, comment="更新时间", default=datetime.now)
    remark = Column(String(500, collation="utf8_general_ci"), comment="备注")
    del_flag = Column(String(1, collation="utf8_general_ci"), default="0", comment="删除标志（0代表存在 2代表删除）")
