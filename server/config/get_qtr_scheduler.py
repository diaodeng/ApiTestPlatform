from apscheduler.events import EVENT_ALL, EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
import json
from datetime import datetime
from config.database import SessionLocal
from module_hrm.entity.vo.job_vo import EditJobModel
from module_hrm.service.job_log_service import JobLogService, JobLogModel
from module_hrm.dao.job_dao import Session, JobDao
from config.scheduler_common import SchedulerUtil, MyCronTrigger as QtrCronTrigger
from utils.log_util import logger
import module_task


class QtrSchedulerUtil(SchedulerUtil):
    """
    定时任务相关方法
    """

    async def init_qtr_scheduler(self, query_db: Session = SessionLocal()):
        """
        应用启动时初始化定时任务
        :return:
        """
        # if self.acquire_lock():
        logger.info("开始启动QTR定时任务...")
        job_list = JobDao.get_job_list_for_scheduler(query_db)
        for item in job_list:
            query_job = self.get_scheduler_job(job_id=str(item.job_id))
            if query_job:
                self.remove_scheduler_job(job_id=str(item.job_id))
            self.add_scheduler_job(item)
        query_db.close()
        self.scheduler.add_listener(self.qtr_scheduler_event_listener, EVENT_ALL)
        logger.info("QTR初始定时任务加载成功")

    def qtr_scheduler_event_listener(self, event):
        logger.info(f"任务执行了回调：{event.code}")
        try:
            # 获取事件类型和任务ID
            event_type = event.__class__.__name__
            if event_type not in ("JobSubmissionEvent", "JobExecutionEvent"):
                return
            if not event.job_id:
                return
            # 获取任务执行异常信息
            run_status, message = self.event_status(event)

            session = SessionLocal()

            job_info = EditJobModel()
            job_info.run_status = run_status
            job_info.job_id = event.job_id
            logger.debug(f"任务【{event.job_id}】,status:{run_status}")
            # JobService.edit_job_services(session, job_info)
            JobDao.edit_job_dao(session, job_info.model_dump(exclude_unset=True))
            session.commit()

            status = '0'
            exception_info = f"【{message}】"
            if event.code in (EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES):
                status = '1'
                exception_info += f"{str(event.exception if event.exception else '')}"
            job_id = event.job_id
            query_job = self.get_scheduler_job(job_id=job_id)
            if query_job:
                query_job_info = query_job.__getstate__()
                # 获取任务名称
                job_name = query_job_info.get('name')
                # 获取任务组名
                job_group = query_job._jobstore_alias
                # 获取任务执行器
                job_executor = query_job_info.get('executor')
                # 获取调用目标字符串
                invoke_target = query_job_info.get('func')
                # 获取调用函数位置参数
                job_args = ','.join(query_job_info.get('args'))
                # 获取调用函数关键字参数
                job_kwargs = json.dumps(query_job_info.get('kwargs'))
                # 获取任务触发器
                job_trigger = str(query_job_info.get('trigger'))
                # 构造日志消息
                job_message = f"事件类型: {event_type}, 任务ID: {job_id}, 任务名称: {job_name}, 执行于{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                job_log = JobLogModel(
                    jobName=job_name,
                    jobGroup=job_group,
                    jobExecutor=job_executor,
                    invokeTarget=invoke_target,
                    jobArgs=job_args,
                    jobKwargs=job_kwargs,
                    jobTrigger=job_trigger,
                    jobMessage=job_message,
                    status=status,
                    exceptionInfo=exception_info
                )

                JobLogService.add_job_log_services(session, job_log)

        except Exception as e:
            logger.exception(e)
            logger.error(f"任务回到异常了哦：{event.code}")
        finally:
            try:
                session.close()
            except:
                pass


qtr_scheduler_util = QtrSchedulerUtil(table_name="apscheduler_jobs_qtr", redis_db=3)
