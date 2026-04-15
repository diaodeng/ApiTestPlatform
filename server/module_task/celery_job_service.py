from datetime import datetime, time

from sqlalchemy.orm import Session

from config.celery_app import celery_app
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_task.celery_contract import (
    CELERY_EXECUTE_JOB_TASK,
    build_task_payload,
    normalize_args_json,
    normalize_kwargs_json,
)
from module_task.celery_job_models import CeleryPeriodicTask, CeleryTaskExecutionLog
from module_task.celery_job_vo import (
    DeleteJobLogModel,
    DeleteJobModel,
    EditJobModel,
    JobLogPageQueryModel,
    JobModel,
    JobPageQueryModel,
    RunJobModel,
)
from utils.common_util import CamelCaseUtil, export_list2excel
from utils.page_util import PageResponseModel


class CeleryJobService:
    """
    Celery 原生任务服务。
    """

    SCHEDULE_TYPES = {"crontab", "interval", "once"}
    INTERVAL_PERIODS = {"seconds", "minutes", "hours", "days"}

    @classmethod
    def _validate_owner_type(cls, owner_type: str) -> str:
        """
        校验任务归属类型。

        :param owner_type: 任务归属类型。
        :return: 归一化后的归属类型。
        """
        normalized = (owner_type or "").strip().lower()
        if normalized not in {"sys", "qtr"}:
            raise ValueError("owner_type 仅支持 sys 或 qtr")
        return normalized

    @classmethod
    def _parse_range(cls, begin_time: str | None, end_time: str | None) -> tuple[datetime, datetime] | None:
        """
        解析日期区间查询参数。

        :param begin_time: 开始日期（YYYY-MM-DD）。
        :param end_time: 结束日期（YYYY-MM-DD）。
        :return: datetime 区间元组或 None。
        """
        if not begin_time or not end_time:
            return None
        begin = datetime.combine(datetime.strptime(begin_time, "%Y-%m-%d"), time(0, 0, 0))
        end = datetime.combine(datetime.strptime(end_time, "%Y-%m-%d"), time(23, 59, 59))
        return begin, end

    @classmethod
    def _serialize_task(cls, row: CeleryPeriodicTask | dict) -> dict:
        """
        序列化任务数据为前端使用结构。

        :param row: ORM 行对象或字典。
        :return: 前端响应字典。
        """
        item = CamelCaseUtil.transform_result(row) if not isinstance(row, dict) else dict(row)
        item["taskArgs"] = item.pop("taskArgsJson", "[]") or "[]"
        item["taskKwargs"] = item.pop("taskKwargsJson", "{}") or "{}"
        return item

    @classmethod
    def _serialize_log(cls, row: CeleryTaskExecutionLog | dict) -> dict:
        """
        序列化执行日志数据为前端使用结构。

        :param row: ORM 行对象或字典。
        :return: 前端响应字典。
        """
        item = CamelCaseUtil.transform_result(row) if not isinstance(row, dict) else dict(row)
        item["taskArgs"] = item.pop("argsJson", "[]") or "[]"
        item["taskKwargs"] = item.pop("kwargsJson", "{}") or "{}"
        return item

    @classmethod
    def _build_task_page(
        cls,
        query,
        page_num: int,
        page_size: int,
        is_page: bool,
    ) -> PageResponseModel | list[dict]:
        """
        构建任务分页结果。

        :param query: SQLAlchemy 查询对象。
        :param page_num: 页码。
        :param page_size: 每页大小。
        :param is_page: 是否分页。
        :return: 分页模型或列表。
        """
        if not is_page:
            rows = query.all()
            return [cls._serialize_task(row) for row in rows]
        total = query.count()
        rows = query.offset((page_num - 1) * page_size).limit(page_size).all()
        return PageResponseModel(
            rows=[cls._serialize_task(row) for row in rows],
            page_num=page_num,
            page_size=page_size,
            total=total,
            has_next=(page_num * page_size) < total,
        )

    @classmethod
    def _build_log_page(
        cls,
        query,
        page_num: int,
        page_size: int,
        is_page: bool,
    ) -> PageResponseModel | list[dict]:
        """
        构建日志分页结果。

        :param query: SQLAlchemy 查询对象。
        :param page_num: 页码。
        :param page_size: 每页大小。
        :param is_page: 是否分页。
        :return: 分页模型或列表。
        """
        if not is_page:
            rows = query.all()
            return [cls._serialize_log(row) for row in rows]
        total = query.count()
        rows = query.offset((page_num - 1) * page_size).limit(page_size).all()
        return PageResponseModel(
            rows=[cls._serialize_log(row) for row in rows],
            page_num=page_num,
            page_size=page_size,
            total=total,
            has_next=(page_num * page_size) < total,
        )

    @classmethod
    def _build_task_payload_dict(cls, model_data: dict, owner_type: str) -> dict:
        """
        构建落库任务字段字典并完成调度配置校验。

        :param model_data: 请求模型字典。
        :param owner_type: 任务归属类型。
        :return: 可直接写入数据库的字段字典。
        """
        task_name = (model_data.get("task_name") or "").strip()
        task_key = (model_data.get("task_key") or "").strip()
        if not task_name:
            raise ValueError("任务名称不能为空")
        if not task_key:
            raise ValueError("任务注册键不能为空")

        schedule_type = (model_data.get("schedule_type") or "crontab").strip().lower()
        if schedule_type not in cls.SCHEDULE_TYPES:
            raise ValueError("schedule_type 仅支持 crontab/interval/once")

        payload = {
            "owner_type": owner_type,
            "owner_user_id": model_data.get("owner_user_id"),
            "owner_dept_id": model_data.get("owner_dept_id"),
            "task_name": task_name,
            "task_key": task_key,
            "queue_name": (model_data.get("queue_name") or owner_type).strip() or owner_type,
            "schedule_type": schedule_type,
            "task_args_json": normalize_args_json(model_data.get("task_args")),
            "task_kwargs_json": normalize_kwargs_json(model_data.get("task_kwargs")),
            "enabled": bool(model_data.get("enabled", True)),
            "allow_concurrent": bool(model_data.get("allow_concurrent", False)),
            "lock_ttl_seconds": int(model_data.get("lock_ttl_seconds") or 3600),
            "timezone": (model_data.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
            "create_by": model_data.get("create_by") or "",
            "update_by": model_data.get("update_by") or "",
            "remark": model_data.get("remark") or "",
        }
        if payload["lock_ttl_seconds"] <= 0:
            raise ValueError("lock_ttl_seconds 必须大于 0")

        if schedule_type == "crontab":
            cron_expression = (model_data.get("cron_expression") or "").strip()
            if not cron_expression:
                raise ValueError("crontab 类型任务必须填写 cron_expression")
            payload["cron_expression"] = cron_expression
            payload["interval_every"] = None
            payload["interval_period"] = None
            payload["one_off_eta"] = None
            payload["one_off_consumed"] = False
        elif schedule_type == "interval":
            every = int(model_data.get("interval_every") or 0)
            period = (model_data.get("interval_period") or "").strip().lower()
            if every <= 0:
                raise ValueError("interval_every 必须大于 0")
            if period not in cls.INTERVAL_PERIODS:
                raise ValueError("interval_period 仅支持 seconds/minutes/hours/days")
            payload["cron_expression"] = None
            payload["interval_every"] = every
            payload["interval_period"] = period
            payload["one_off_eta"] = None
            payload["one_off_consumed"] = False
        else:
            one_off_eta = model_data.get("one_off_eta")
            if not one_off_eta:
                raise ValueError("once 类型任务必须填写 one_off_eta")
            payload["cron_expression"] = None
            payload["interval_every"] = None
            payload["interval_period"] = None
            payload["one_off_eta"] = one_off_eta
            payload["one_off_consumed"] = False

        return payload

    @classmethod
    def get_job_list_services(
        cls,
        query_db: Session,
        owner_type: str,
        query_object: JobPageQueryModel,
        data_scope_sql=True,
        is_page: bool = False,
    ):
        """
        查询任务列表。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param query_object: 查询模型。
        :param data_scope_sql: 数据权限表达式。
        :param is_page: 是否分页。
        :return: 分页模型或列表。
        """
        owner_type = cls._validate_owner_type(owner_type)
        query = query_db.query(CeleryPeriodicTask).filter(
            CeleryPeriodicTask.owner_type == owner_type,
            data_scope_sql,
        )
        if query_object.task_name:
            query = query.filter(CeleryPeriodicTask.task_name.like(f"%{query_object.task_name}%"))
        if query_object.task_key:
            query = query.filter(CeleryPeriodicTask.task_key.like(f"%{query_object.task_key}%"))
        if query_object.schedule_type:
            query = query.filter(CeleryPeriodicTask.schedule_type == query_object.schedule_type)
        if query_object.enabled is not None:
            query = query.filter(CeleryPeriodicTask.enabled == query_object.enabled)
        if query_object.last_status:
            query = query.filter(CeleryPeriodicTask.last_status == query_object.last_status)
        date_range = cls._parse_range(query_object.begin_time, query_object.end_time)
        if date_range:
            query = query.filter(CeleryPeriodicTask.create_time.between(date_range[0], date_range[1]))

        query = query.order_by(CeleryPeriodicTask.create_time.desc(), CeleryPeriodicTask.task_id.desc())
        return cls._build_task_page(query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    def add_job_services(cls, query_db: Session, owner_type: str, page_object: JobModel) -> CrudResponseModel:
        """
        新增任务。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param page_object: 新增请求模型。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        model_data = page_object.model_dump(exclude_unset=True)
        payload = cls._build_task_payload_dict(model_data, owner_type=owner_type)

        existed = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_name == payload["task_name"],
            )
            .first()
        )
        if existed:
            return CrudResponseModel(is_success=False, message="同名任务已存在")

        try:
            now = datetime.now()
            payload["create_time"] = now
            payload["update_time"] = now
            query_db.add(CeleryPeriodicTask(**payload))
            query_db.commit()
            return CrudResponseModel(is_success=True, message="新增成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def edit_job_services(cls, query_db: Session, owner_type: str, page_object: EditJobModel) -> CrudResponseModel:
        """
        编辑任务。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param page_object: 编辑请求模型。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        task = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_id == page_object.task_id,
            )
            .first()
        )
        if not task:
            return CrudResponseModel(is_success=False, message="任务不存在")

        model_data = page_object.model_dump(exclude_unset=True)
        payload = cls._build_task_payload_dict(
            {
                "task_name": model_data.get("task_name", task.task_name),
                "task_key": model_data.get("task_key", task.task_key),
                "queue_name": model_data.get("queue_name", task.queue_name),
                "schedule_type": model_data.get("schedule_type", task.schedule_type),
                "cron_expression": model_data.get("cron_expression", task.cron_expression),
                "interval_every": model_data.get("interval_every", task.interval_every),
                "interval_period": model_data.get("interval_period", task.interval_period),
                "one_off_eta": model_data.get("one_off_eta", task.one_off_eta),
                "task_args": model_data.get("task_args", task.task_args_json),
                "task_kwargs": model_data.get("task_kwargs", task.task_kwargs_json),
                "enabled": model_data.get("enabled", task.enabled),
                "allow_concurrent": model_data.get("allow_concurrent", task.allow_concurrent),
                "lock_ttl_seconds": model_data.get("lock_ttl_seconds", task.lock_ttl_seconds),
                "timezone": model_data.get("timezone", task.timezone),
                "owner_user_id": model_data.get("owner_user_id", task.owner_user_id),
                "owner_dept_id": model_data.get("owner_dept_id", task.owner_dept_id),
                "create_by": task.create_by,
                "update_by": model_data.get("update_by", task.update_by),
                "remark": model_data.get("remark", task.remark),
            },
            owner_type=owner_type,
        )
        payload["update_time"] = datetime.now()
        payload.pop("create_by", None)
        payload.pop("create_time", None)

        duplicated = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_name == payload["task_name"],
                CeleryPeriodicTask.task_id != task.task_id,
            )
            .first()
        )
        if duplicated:
            return CrudResponseModel(is_success=False, message="同名任务已存在")

        try:
            query_db.query(CeleryPeriodicTask).filter(CeleryPeriodicTask.task_id == task.task_id).update(payload)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="更新成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def change_status_services(
        cls,
        query_db: Session,
        owner_type: str,
        task_id: int,
        enabled: bool,
        update_by: str = "",
    ) -> CrudResponseModel:
        """
        切换任务启停状态。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param task_id: 任务ID。
        :param enabled: 是否启用。
        :param update_by: 更新人。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        task = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_id == task_id,
            )
            .first()
        )
        if not task:
            return CrudResponseModel(is_success=False, message="任务不存在")

        update_payload = {
            "enabled": bool(enabled),
            "update_time": datetime.now(),
            "update_by": update_by or task.update_by or "",
        }
        if task.schedule_type == "once" and enabled:
            update_payload["one_off_consumed"] = False
        try:
            query_db.query(CeleryPeriodicTask).filter(CeleryPeriodicTask.task_id == task_id).update(update_payload)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="状态更新成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def execute_job_once_services(
        cls,
        query_db: Session,
        owner_type: str,
        page_object: RunJobModel,
    ) -> CrudResponseModel:
        """
        手动立即执行一次任务。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param page_object: 手动执行请求模型。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        task = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_id == page_object.task_id,
            )
            .first()
        )
        if not task:
            return CrudResponseModel(is_success=False, message="任务不存在")

        payload = build_task_payload(task_row=task, trigger_type="manual")
        celery_app.send_task(
            CELERY_EXECUTE_JOB_TASK,
            args=[payload],
            queue=payload["queue_name"],
        )

        try:
            query_db.query(CeleryPeriodicTask).filter(CeleryPeriodicTask.task_id == task.task_id).update(
                {
                    "last_status": "queued",
                    "last_message": "已提交手动执行",
                    "update_time": datetime.now(),
                }
            )
            query_db.commit()
        except Exception:
            query_db.rollback()
        return CrudResponseModel(is_success=True, message="任务已提交执行")

    @classmethod
    def delete_job_services(cls, query_db: Session, owner_type: str, page_object: DeleteJobModel) -> CrudResponseModel:
        """
        删除任务。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param page_object: 删除模型。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        id_list = [int(item) for item in page_object.job_ids.split(",") if item.strip()]
        if not id_list:
            return CrudResponseModel(is_success=False, message="任务ID不能为空")

        try:
            query_db.query(CeleryTaskExecutionLog).filter(
                CeleryTaskExecutionLog.owner_type == owner_type,
                CeleryTaskExecutionLog.task_id.in_(id_list),
            ).delete(synchronize_session=False)
            query_db.query(CeleryPeriodicTask).filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_id.in_(id_list),
            ).delete(synchronize_session=False)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def job_detail_services(cls, query_db: Session, owner_type: str, task_id: int) -> dict | None:
        """
        查询任务详情。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param task_id: 任务ID。
        :return: 任务详情字典。
        """
        owner_type = cls._validate_owner_type(owner_type)
        row = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.task_id == task_id,
            )
            .first()
        )
        if not row:
            return None
        return cls._serialize_task(row)

    @classmethod
    def get_job_log_list_services(
        cls,
        query_db: Session,
        owner_type: str,
        query_object: JobLogPageQueryModel,
        data_scope_sql=True,
        is_page: bool = False,
    ):
        """
        查询任务执行日志列表。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param query_object: 日志查询参数。
        :param data_scope_sql: 数据权限表达式。
        :param is_page: 是否分页。
        :return: 分页模型或列表。
        """
        owner_type = cls._validate_owner_type(owner_type)
        task_id_scope_query = query_db.query(CeleryPeriodicTask.task_id).filter(
            CeleryPeriodicTask.owner_type == owner_type,
            data_scope_sql,
        )
        query = query_db.query(CeleryTaskExecutionLog).filter(
            CeleryTaskExecutionLog.owner_type == owner_type,
            CeleryTaskExecutionLog.task_id.in_(task_id_scope_query),
        )

        if query_object.task_id:
            query = query.filter(CeleryTaskExecutionLog.task_id == query_object.task_id)
        if query_object.task_name:
            query = query.filter(CeleryTaskExecutionLog.task_name.like(f"%{query_object.task_name}%"))
        if query_object.status:
            query = query.filter(CeleryTaskExecutionLog.status == query_object.status)
        if query_object.trigger_type:
            query = query.filter(CeleryTaskExecutionLog.trigger_type == query_object.trigger_type)
        date_range = cls._parse_range(query_object.begin_time, query_object.end_time)
        if date_range:
            query = query.filter(CeleryTaskExecutionLog.create_time.between(date_range[0], date_range[1]))

        query = query.order_by(CeleryTaskExecutionLog.create_time.desc(), CeleryTaskExecutionLog.log_id.desc())
        return cls._build_log_page(query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    def delete_job_log_services(
        cls,
        query_db: Session,
        owner_type: str,
        page_object: DeleteJobLogModel,
    ) -> CrudResponseModel:
        """
        删除指定日志记录。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param page_object: 删除日志请求模型。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        id_list = [int(item) for item in page_object.job_log_ids.split(",") if item.strip()]
        if not id_list:
            return CrudResponseModel(is_success=False, message="日志ID不能为空")
        try:
            query_db.query(CeleryTaskExecutionLog).filter(
                CeleryTaskExecutionLog.owner_type == owner_type,
                CeleryTaskExecutionLog.log_id.in_(id_list),
            ).delete(synchronize_session=False)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def clear_job_log_services(cls, query_db: Session, owner_type: str, data_scope_sql=True) -> CrudResponseModel:
        """
        清空当前归属类型的日志。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :param data_scope_sql: 数据权限表达式。
        :return: CRUD 响应。
        """
        owner_type = cls._validate_owner_type(owner_type)
        task_id_scope_query = query_db.query(CeleryPeriodicTask.task_id).filter(
            CeleryPeriodicTask.owner_type == owner_type,
            data_scope_sql,
        )
        try:
            query_db.query(CeleryTaskExecutionLog).filter(
                CeleryTaskExecutionLog.owner_type == owner_type,
                CeleryTaskExecutionLog.task_id.in_(task_id_scope_query),
            ).delete(synchronize_session=False)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="清空成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    async def export_job_list_services(cls, job_list: list[dict]) -> bytes:
        """
        导出任务列表。

        :param job_list: 任务数据列表。
        :return: Excel 二进制内容。
        """
        mapping_dict = {
            "taskId": "任务ID",
            "taskName": "任务名称",
            "taskKey": "任务注册键",
            "queueName": "队列",
            "scheduleType": "调度类型",
            "cronExpression": "Cron表达式",
            "intervalEvery": "间隔步长",
            "intervalPeriod": "间隔单位",
            "oneOffEta": "单次触发时间",
            "enabled": "是否启用",
            "allowConcurrent": "允许并发",
            "lastStatus": "最近状态",
            "lastRunAt": "最近执行时间",
            "runCount": "累计次数",
            "createBy": "创建人",
            "createTime": "创建时间",
            "updateBy": "更新人",
            "updateTime": "更新时间",
            "remark": "备注",
        }
        normalized = []
        for item in job_list:
            row = dict(item)
            row["enabled"] = "启用" if row.get("enabled") else "停用"
            row["allowConcurrent"] = "是" if row.get("allowConcurrent") else "否"
            normalized.append({mapping_dict.get(k): v for k, v in row.items() if mapping_dict.get(k)})
        return export_list2excel(normalized)

    @classmethod
    async def export_job_log_list_services(cls, job_log_list: list[dict]) -> bytes:
        """
        导出任务日志列表。

        :param job_log_list: 日志数据列表。
        :return: Excel 二进制内容。
        """
        mapping_dict = {
            "logId": "日志ID",
            "taskId": "任务ID",
            "taskName": "任务名称",
            "taskKey": "任务注册键",
            "queueName": "队列",
            "triggerType": "触发方式",
            "status": "执行状态",
            "message": "执行消息",
            "exceptionInfo": "异常信息",
            "startedAt": "开始时间",
            "finishedAt": "结束时间",
            "durationMs": "耗时(ms)",
            "createTime": "记录时间",
        }
        normalized = []
        for item in job_log_list:
            row = dict(item)
            normalized.append({mapping_dict.get(k): v for k, v in row.items() if mapping_dict.get(k)})
        return export_list2excel(normalized)

    @classmethod
    def copy_task_for_scheduler(cls, query_db: Session, owner_type: str):
        """
        获取用于调度器展示的启用任务快照。

        :param query_db: 数据库会话。
        :param owner_type: 任务归属类型。
        :return: 启用任务列表。
        """
        owner_type = cls._validate_owner_type(owner_type)
        rows = (
            query_db.query(CeleryPeriodicTask)
            .filter(
                CeleryPeriodicTask.owner_type == owner_type,
                CeleryPeriodicTask.enabled.is_(True),
            )
            .order_by(CeleryPeriodicTask.task_id.desc())
            .all()
        )
        return [cls._serialize_task(row) for row in rows]
