from datetime import datetime

from sqlalchemy import Integer, String, DateTime, BigInteger
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped

from config.database import Base, mapped_column
from module_hrm.entity.do.common_do import BaseModel
from utils.snowflake import snowIdWorker


class QtrJob(Base, BaseModel):
    """
    定时任务调度表
    """

    class Meta:
        verbose_name = '用例信息'

    __tablename__ = 'qtr_job'

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False, default=snowIdWorker.get_id,
                                        autoincrement=False, comment='任务ID')
    job_name: Mapped[str] = mapped_column(String(64, collation='utf8_general_ci'), nullable=False, comment='任务名称')
    job_group: Mapped[str] = mapped_column(String(64, collation='utf8_general_ci'), nullable=False, default='default',
                                           comment='任务组名')
    job_executor: Mapped[str] = mapped_column(String(64, collation='utf8_general_ci'), nullable=False,
                                              default='default',
                                              comment='任务执行器')
    invoke_target: Mapped[str] = mapped_column(String(500, collation='utf8_general_ci'), nullable=False,
                                               comment='调用目标字符串')
    job_args: Mapped[str] = mapped_column(LONGTEXT(collation='utf8_general_ci'), nullable=True, comment='位置参数')
    job_kwargs: Mapped[str] = mapped_column(LONGTEXT(collation='utf8_general_ci'), nullable=True, comment='关键字参数')
    cron_expression: Mapped[str] = mapped_column(String(255, collation='utf8_general_ci'), nullable=True, default='',
                                                 comment='cron执行表达式')
    misfire_policy: Mapped[str] = mapped_column(String(20, collation='utf8_general_ci'), nullable=True, default='3',
                                                comment='计划执行错误策略（1立即执行 2执行一次 3放弃执行）')
    concurrent: Mapped[str] = mapped_column(String(1, collation='utf8_general_ci'), nullable=True, default='1',
                                            comment='是否并发执行（0允许 1禁止）')
    status: Mapped[str] = mapped_column(String(1, collation='utf8_general_ci'), nullable=True, default='0',
                                        comment='状态（0正常 1暂停）')
    run_status: Mapped[int] = mapped_column(Integer, nullable=True, default=6,
                                        comment='任务最后一次执行状态，TaskStatusEnum')
    create_by: Mapped[str] = mapped_column(String(64, collation='utf8_general_ci'), nullable=True, default='',
                                           comment='创建者')
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_by: Mapped[str] = mapped_column(String(64, collation='utf8_general_ci'), nullable=True, default='',
                                           comment='更新者')
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=True, default=datetime.now, comment='更新时间')
    remark: Mapped[str] = mapped_column(String(500, collation='utf8_general_ci'), nullable=True, default='',
                                        comment='备注信息')


class QtrJobLog(Base, BaseModel):
    """
    定时任务调度日志表
    """
    __tablename__ = 'qtr_job_log'

    job_log_id = mapped_column(BigInteger, primary_key=True, nullable=False, default=snowIdWorker.get_id,
                               autoincrement=False, comment='任务日志ID')
    job_name = mapped_column(String(64, collation='utf8_general_ci'), nullable=False, comment='任务名称')
    job_group = mapped_column(String(64, collation='utf8_general_ci'), nullable=False, comment='任务组名')
    job_executor = mapped_column(String(64, collation='utf8_general_ci'), nullable=False, default='default',
                                 comment='任务执行器')
    invoke_target = mapped_column(String(500, collation='utf8_general_ci'), nullable=False, comment='调用目标字符串')
    job_args = mapped_column(LONGTEXT(collation='utf8_general_ci'), nullable=True, comment='位置参数')
    job_kwargs = mapped_column(LONGTEXT(collation='utf8_general_ci'), nullable=True, comment='关键字参数')
    job_trigger = mapped_column(String(255, collation='utf8_general_ci'), nullable=True, comment='任务触发器')
    job_message = mapped_column(String(500, collation='utf8_general_ci'), nullable=True, default='', comment='日志信息')
    status = mapped_column(String(1, collation='utf8_general_ci'), nullable=True, default='0',
                           comment='执行状态（0正常 1失败）')
    exception_info = mapped_column(String(2000, collation='utf8_general_ci'), nullable=True, default='',
                                   comment='异常信息')
    create_time = mapped_column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
