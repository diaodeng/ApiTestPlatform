import json
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, model_validator, field_serializer
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.entity.vo.common_vo import CommonDataModel


class JobModelBase(CommonDataModel):
    """
    定时任务基础模型
    """
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True,
                              populate_by_name=True
                              )

    job_id: Optional[int|str] = None
    job_name: Optional[str] = None
    job_group: Optional[str] = None
    job_executor: Optional[str] = None
    invoke_target: Optional[str] = None
    job_args: Optional[str] = None
    cron_expression: Optional[str] = None
    misfire_policy: Optional[str] = None
    concurrent: Optional[str] = None
    status: Optional[str] = None
    run_status: Optional[int] = None
    remark: Optional[str] = None


class JobModel(JobModelBase):
    """
    定时任务调度表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True,
                              populate_by_name=True
                              )

    job_kwargs: Optional[CaseRunModel|str] = CaseRunModel()

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # values = CamelCaseUtil.transform_result(values)
        request_data = values.get('jobKwargs')
        if isinstance(request_data, str):
            values["jobKwargs"] = CaseRunModel(**json.loads(request_data))

        return values

    @field_serializer('job_kwargs')
    def request_data(self, job_kwargs: Any):
        if isinstance(job_kwargs, str):
            return job_kwargs
        elif isinstance(job_kwargs, (dict, list)):
            return json.dumps(job_kwargs, ensure_ascii=False)
        elif isinstance(job_kwargs, CaseRunModel):
            return job_kwargs.model_dump_json(by_alias=True, exclude_unset=False)
        else:
            return job_kwargs


class JobLogModel(CommonDataModel):
    """
    定时任务调度日志表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    job_log_id: Optional[int] = None
    job_name: Optional[str] = None
    job_group: Optional[str] = None
    job_executor: Optional[str] = None
    invoke_target: Optional[str] = None
    job_args: Optional[str] = None
    job_kwargs: Optional[str] = None
    job_trigger: Optional[str] = None
    job_message: Optional[str] = None
    status: Optional[str] = None
    exception_info: Optional[str] = None
    create_time: Optional[datetime] = None


class JobQueryModel(JobModelBase):
    """
    定时任务管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class JobPageQueryModel(JobQueryModel):
    """
    定时任务管理分页查询模型
    """
    page_num: int = 1
    page_size: int = 10


class EditJobModel(JobModel):
    """
    编辑定时任务模型
    """
    pass


class DeleteJobModel(BaseModel):
    """
    删除定时任务模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    job_ids: str


class JobLogQueryModel(JobLogModel):
    """
    定时任务日志不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class JobLogPageQueryModel(JobLogQueryModel):
    """
    定时任务日志管理分页查询模型
    """
    page_num: int = 1
    page_size: int = 10


class DeleteJobLogModel(BaseModel):
    """
    删除定时任务日志模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    job_log_ids: str
