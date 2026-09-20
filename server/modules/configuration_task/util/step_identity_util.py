"""配置任务步骤稳定身份工具。

步骤索引会随着插入、移动和删除变化，不能作为业务关联的唯一身份。本模块只负责
对步骤字典做无副作用的身份归一化，不负责复制步骤；复制场景由前端生成新的 stepId。
"""

import hashlib
import json
import re
from typing import Any

_STEP_ID_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def _normalise_existing_id(value: Any) -> str:
    """读取并清理已有步骤 ID；空值返回空字符串。"""
    return str(value or "").strip()


def _slug(value: Any) -> str:
    """将旧 stepKey 转成适合传输的稳定片段。"""
    text = _STEP_ID_PATTERN.sub("-", str(value or "").strip()).strip("-")
    return text[:80]


def _step_fingerprint(step: dict[str, Any]) -> str:
    """根据步骤的业务内容生成确定性摘要，避免依赖当前数组索引。"""
    identity_fields = {
        key: value
        for key, value in step.items()
        if key not in {"stepId", "step_id", "stepIndex", "step_index"}
    }
    raw = json.dumps(identity_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def ensure_step_ids(steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """为缺少 stepId 的步骤生成稳定 ID，并保留已有 ID。

    优先使用历史 stepKey，旧数据没有 stepKey 时使用步骤业务内容摘要。完全相同的
    重复步骤会追加 occurrence 后缀以保证一个版本内唯一；第一次保存后 ID 会写回
    版本 JSON，之后步骤移动只会携带已有 ID，不会重新生成。
    """
    normalized: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    occurrence: dict[str, int] = {}
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        item = dict(step)
        existing_id = _normalise_existing_id(item.get("stepId") or item.get("step_id"))
        if existing_id:
            item["stepId"] = existing_id
            item.pop("step_id", None)
            used_ids.add(existing_id)
            normalized.append(item)
            continue

        legacy_key = _slug(item.get("stepKey") or item.get("step_key"))
        base_id = f"step-{legacy_key}" if legacy_key else f"step-{_step_fingerprint(item)}"
        occurrence[base_id] = occurrence.get(base_id, 0) + 1
        candidate = base_id if occurrence[base_id] == 1 else f"{base_id}-{occurrence[base_id]}"
        suffix = occurrence[base_id]
        while candidate in used_ids:
            suffix += 1
            candidate = f"{base_id}-{suffix}"
        item["stepId"] = candidate
        item.pop("step_id", None)
        used_ids.add(candidate)
        normalized.append(item)
    return normalized


def step_id_map(steps: list[dict[str, Any]] | None) -> dict[str, int]:
    """返回 stepId 到当前步骤索引的映射，供阶段关联校验使用。"""
    return {
        str(step.get("stepId")): index
        for index, step in enumerate(steps or [])
        if isinstance(step, dict) and str(step.get("stepId") or "").strip()
    }


def step_by_id(steps: list[dict[str, Any]] | None, step_id: str) -> dict[str, Any] | None:
    """按稳定步骤 ID 查找步骤。"""
    normalized_id = str(step_id or "").strip()
    for step in steps or []:
        if isinstance(step, dict) and str(step.get("stepId") or "").strip() == normalized_id:
            return step
    return None
