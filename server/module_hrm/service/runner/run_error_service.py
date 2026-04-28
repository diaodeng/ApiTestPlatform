import hashlib
import json
import re
import traceback
from datetime import datetime
from typing import Any

from module_hrm.entity.vo.case_vo_detail_for_run import Result, TestCase
from module_hrm.entity.vo.run_error_vo import RunErrorEventModel, RunErrorRecordModel
from module_hrm.enums.enums import CaseRunStatus


def stringify_error_value(value: Any) -> str:
    """
    把断言值和异常对象稳定转成字符串，方便落库与前端直接展示。
    """
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    try:
        if isinstance(value, (dict, list, tuple, set)):
            return json.dumps(value, ensure_ascii=False)
    except TypeError:
        pass
    return str(value)


def normalize_error_reason(message: str) -> str:
    """
    归一化错误原因，避免动态值影响同类问题聚合。
    """
    text = (message or '').strip()
    if not text:
        return 'unknown'
    text = re.sub(r'\d+', '{num}', text)
    text = re.sub(r'\"[^\"]*\"', '{str}', text)
    text = re.sub(r"'[^']*'", '{str}', text)
    return text[:255]


def build_error_fingerprint(error_type: str, error_source: str, error_subtype: str, key: str) -> str:
    """
    使用稳定结构信息生成指纹，支持按失败原因聚合统计。
    """
    raw = '|'.join([
        error_type or 'unknown',
        error_source or 'unknown',
        error_subtype or 'unknown',
        key or 'unknown',
    ])
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _build_error_template(error_source: str, error_subtype: str, key: str) -> str:
    normalized_key = key or 'unknown'
    return f'{error_source}:{error_subtype}:{normalized_key}'


def build_assertion_error_event(
    *,
    error_source: str,
    error_subtype: str,
    assert_name: str = '',
    check_key: str = '',
    expected_value: Any = None,
    actual_value: Any = None,
    error_message: str = '',
    error_name: str = 'AssertionError',
    step_id: Any = None,
    step_name: str = '',
    error_stack: str = '',
) -> RunErrorEventModel:
    """
    构造断言失败事件，统一记录来源、断言项与期望实际值。
    """
    key = check_key or assert_name or normalize_error_reason(error_message)
    template = _build_error_template(error_source, error_subtype or assert_name or 'assert_fail', key)
    return RunErrorEventModel(
        error_type='assert_fail',
        error_source=error_source,
        error_subtype=error_subtype or assert_name or 'assert_fail',
        error_name=error_name or 'AssertionError',
        error_template=template,
        fingerprint=build_error_fingerprint('assert_fail', error_source, error_subtype or assert_name, key),
        step_id=stringify_error_value(step_id),
        step_name=step_name or '',
        check_key=check_key or '',
        assert_name=assert_name or '',
        expected_value=stringify_error_value(expected_value),
        actual_value=stringify_error_value(actual_value),
        error_message=stringify_error_value(error_message),
        error_stack=stringify_error_value(error_stack),
    )


def build_exception_error_event(
    *,
    error_source: str,
    error_name: str,
    error_message: str,
    step_id: Any = None,
    step_name: str = '',
    error_stack: str = '',
    error_subtype: str = '',
) -> RunErrorEventModel:
    """
    构造执行异常事件，统一保留错误名、错误信息和堆栈。
    """
    subtype = error_subtype or error_name or 'exception'
    key = normalize_error_reason(error_message) or subtype
    template = _build_error_template(error_source, subtype, key)
    return RunErrorEventModel(
        error_type='exception',
        error_source=error_source,
        error_subtype=subtype,
        error_name=error_name or 'Exception',
        error_template=template,
        fingerprint=build_error_fingerprint('exception', error_source, subtype, key),
        step_id=stringify_error_value(step_id),
        step_name=step_name or '',
        error_message=stringify_error_value(error_message),
        error_stack=stringify_error_value(error_stack),
    )


def append_error_event(result_obj: Result | None, event: RunErrorEventModel):
    """
    向结果对象追加错误事件，并按指纹和消息去重避免重复统计。
    """
    if not result_obj:
        return
    if result_obj.error_events is None:
        result_obj.error_events = []
    normalized_events = [RunErrorEventModel.model_validate(item) for item in result_obj.error_events]
    duplicated = any(
        item.fingerprint == event.fingerprint
        and item.error_message == event.error_message
        and item.step_id == event.step_id
        for item in normalized_events
    )
    if not duplicated:
        normalized_events.append(event)
    result_obj.error_events = normalized_events


def build_run_error_records(case_data: TestCase, run_info, detail_id: int, run_name: str) -> list[RunErrorRecordModel]:
    """
    把用例执行结果上的错误事件展开为可批量入库的错误记录。
    """
    records: list[RunErrorRecordModel] = []

    case_events = getattr(case_data.config.result, 'error_events', []) or []
    for event in case_events:
        records.append(_build_record(detail_id, case_data.case_id, run_info, run_name, event))

    for step in case_data.teststeps:
        step_result = getattr(step, 'result', None)
        if not step_result:
            continue
        for event in getattr(step_result, 'error_events', []) or []:
            records.append(_build_record(detail_id, case_data.case_id, run_info, run_name, event))

    return records


def _build_record(detail_id: int, run_id: int, run_info, run_name: str, event: RunErrorEventModel | dict) -> RunErrorRecordModel:
    event_model = RunErrorEventModel.model_validate(event)
    return RunErrorRecordModel(
        error_id=None,
        detail_id=detail_id,
        report_id=run_info.report_id,
        run_id=run_id,
        run_name=run_name,
        manager=run_info.runner,
        dept_id=-1,
        error_type=event_model.error_type,
        error_source=event_model.error_source,
        error_subtype=event_model.error_subtype,
        error_name=event_model.error_name,
        error_template=event_model.error_template,
        fingerprint=event_model.fingerprint,
        step_id=event_model.step_id,
        step_name=event_model.step_name,
        check_key=event_model.check_key,
        assert_name=event_model.assert_name,
        expected_value=event_model.expected_value,
        actual_value=event_model.actual_value,
        error_message=event_model.error_message,
        error_stack=event_model.error_stack,
        create_time=datetime.now(),
    )


def mark_case_run_failed(case_data: TestCase, exc: Exception):
    """
    为完全执行失败且尚未入队的用例补齐失败状态与错误事件，避免漏统计。
    """
    if not getattr(case_data.config, 'result', None):
        case_data.config.result = Result()

    case_result = case_data.config.result
    case_result.status = CaseRunStatus.failed.value
    case_result.success = False
    now_ts = datetime.now().timestamp()
    if not case_result.start_time_stamp:
        case_result.start_time_stamp = now_ts
    case_result.end_time_stamp = now_ts
    if not case_result.start_time_iso:
        case_result.start_time_iso = datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d %H:%M:%S')
    case_result.end_time_iso = datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d %H:%M:%S')
    append_error_event(
        case_result,
        build_exception_error_event(
            error_source='runner_worker',
            error_name=type(exc).__name__,
            error_message=str(exc),
            error_stack=''.join(traceback.format_exception(exc)),
            error_subtype='case_execute_exception',
        ),
    )
