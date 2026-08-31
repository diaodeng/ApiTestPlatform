"""
工单轻量 AI 手动测试接口契约模型。

测试工作台允许选择工单、Provider、模型和提示词（可临时编辑），对信息提取、
分类统计、翻译、标题总结和知识提炼五类轻量 AI 任务做试运行，不回写工单业务字段。
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

TicketAiTestTaskType = Literal["sync_extract", "classification", "translate", "title_summary", "knowledge"]


class TicketAiTestOptionsModel(BaseModel):
    """
    手动测试工作台选项响应模型。
    """

    task_types: list[dict[str, str]] = Field(
        default_factory=list, description="支持的任务类型列表（value/label/description）"
    )
    providers: list[dict[str, Any]] = Field(default_factory=list, description="轻量 AI 可用 Provider 选项")
    provider_models: dict[str, list[dict[str, str]]] = Field(
        default_factory=dict, description="Provider 编码到模型选项列表的映射"
    )
    prompt_templates: list[dict[str, Any]] = Field(
        default_factory=list, description="轻量 AI 相关提示词模板选项（含任务类型归属）"
    )


class TicketAiTestTicketSearchItemModel(BaseModel):
    """
    测试工作台工单搜索结果项。
    """

    ticket_id: str = Field(description="工单内部ID（BIGINT 序列化为字符串）")
    ticket_no: str = Field(description="工单编号")
    title: str = Field(default="", description="工单标题")
    module_name: str = Field(default="", description="模块名称")
    create_time: str = Field(default="", description="创建时间")


class TicketAiTestTicketSearchResponseModel(BaseModel):
    """
    测试工作台工单搜索响应模型。
    """

    rows: list[TicketAiTestTicketSearchItemModel] = Field(default_factory=list, description="工单列表")


class TicketAiTestRunModel(BaseModel):
    """
    手动测试执行请求模型。
    """

    task_type: TicketAiTestTaskType = Field(
        description="任务类型：sync_extract/classification/translate/title_summary/knowledge"
    )
    ticket_no: str = Field(description="工单编号")
    provider_code: str = Field(min_length=1, description="Provider 编码")
    model_name: str = Field(default="", description="模型名称，留空使用 Provider 默认模型")
    prompt_code: str = Field(default="", description="提示词模板编码，测试记录留痕用")
    prompt_override: str = Field(default="", description="临时编辑后的提示词内容，为空时使用模板原文")
    use_ticket_description_only: bool = Field(
        default=False,
        description="信息提取测试是否只用工单标题+描述（不含原始入参），默认包含原始入参",
    )


class TicketAiTestRunResponseModel(BaseModel):
    """
    手动测试执行响应模型。
    """

    task_type: str = Field(description="任务类型")
    success: bool = Field(description="是否执行成功")
    provider_code: str = Field(default="", description="实际使用的 Provider 编码")
    model_name: str = Field(default="", description="实际使用的模型名称")
    prompt_code: str = Field(default="", description="提示词模板编码")
    prompt_source: str = Field(default="", description="提示词来源：template=模板原文 override=临时编辑")
    system_prompt: str = Field(default="", description="实际发送的系统提示词")
    user_prompt: str = Field(default="", description="实际发送的用户提示词")
    raw_text: str = Field(default="", description="模型原始输出")
    parsed: dict[str, Any] = Field(default_factory=dict, description="解析后的 JSON 输出（提取/分类/知识任务）")
    normalized: dict[str, Any] = Field(default_factory=dict, description="归一化后的业务结果（提取任务含机台告警）")
    machine_number_warnings: list[str] = Field(default_factory=list, description="机台编号校验告警（提取任务）")
    warnings: list[str] = Field(default_factory=list, description="通用校验告警")
    result_text: str = Field(default="", description="文本型结果（翻译/标题总结）")
    token_usage: dict[str, Any] = Field(default_factory=dict, description="Token 用量")
    elapsed_ms: int = Field(default=0, description="执行耗时毫秒")
    error_message: str = Field(default="", description="失败原因")
