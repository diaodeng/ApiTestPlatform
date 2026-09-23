"""配置任务证据完整性派生服务。"""

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from modules.configuration_task.dao.stage_artifact_dao import (
    ConfigurationTaskStageDao,
    TaskArtifactDao,
    load_json_list,
)
from modules.configuration_task.dao.task_dao import ConfigurationTaskRunDao, load_json_object


@dataclass
class EvidenceStatusResult:
    """一次证据状态重算结果。"""

    status: str
    missing: list[dict[str, Any]]


def _dumps(value: Any) -> str:
    """把证据状态摘要序列化为紧凑 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _normalize_evidence_type(value: Any, artifact_type: Any = "") -> str:
    """兼容旧 step_screenshot 产物，统一为检查点截图类型。"""
    evidence_type = str(value or "").strip()
    if evidence_type == "step_screenshot" or not evidence_type:
        if str(artifact_type or "").strip() == "step_screenshot":
            return "checkpoint_screenshot"
    return evidence_type


class ConfigurationTaskEvidenceStatusService:
    """按运行阶段快照、证据策略和产物引用重算证据状态。"""

    @classmethod
    def refresh_stage_status(
        cls,
        db: Session,
        run_stage_id: int,
        *,
        artifacts: list[Any] | None = None,
        run_params: dict[str, Any] | None = None,
        run_status: str = "RUNNING",
        commit: bool = True,
    ) -> EvidenceStatusResult:
        """重算单个运行阶段状态，不改变阶段业务状态。"""
        stage = ConfigurationTaskStageDao.get_run_stage(db, run_stage_id)
        if not stage:
            return EvidenceStatusResult("NOT_REQUIRED", [])
        if artifacts is None:
            artifacts = TaskArtifactDao.list_artifacts(db, stage.task_run_id)
        result = cls._calculate_stage_status(stage, artifacts, run_params or {}, run_status)
        ConfigurationTaskStageDao.update_run_stage(
            db,
            stage.run_stage_id,
            {
                "evidence_status": result.status,
                "evidence_missing_json": _dumps(result.missing),
            },
        )
        if commit:
            db.commit()
        return result

    @classmethod
    def refresh_run_and_stages(
        cls,
        db: Session,
        task_run_id: int,
        *,
        commit: bool = True,
    ) -> EvidenceStatusResult:
        """重算运行及其全部阶段的证据状态。"""
        run = ConfigurationTaskRunDao.get_run(db, task_run_id)
        if not run:
            return EvidenceStatusResult("NOT_REQUIRED", [])
        stages = ConfigurationTaskStageDao.list_run_stages(db, task_run_id)
        if not stages:
            result = EvidenceStatusResult("NOT_REQUIRED", [])
            ConfigurationTaskRunDao.update_run(
                db,
                task_run_id,
                {
                    "evidence_status": result.status,
                    "evidence_missing_json": _dumps(result.missing),
                },
            )
            if commit:
                db.commit()
            return result
        try:
            with db.begin_nested():
                artifacts = TaskArtifactDao.list_artifacts(db, task_run_id)
        except SQLAlchemyError as exc:
            # 兼容尚未执行证据迁移的旧数据库：业务终态不能因证据表缺失而失败。
            artifacts = []
            logger.warning(
                f"证据产物表不可用，按无产物计算状态: task_run_id={task_run_id}, error={exc}"
            )
        run_params = load_json_object(run.run_params_json)
        stage_results: list[EvidenceStatusResult] = []
        for stage in stages:
            # 阶段已经结束但运行整体仍在继续时，也应立即把缺失证据标为
            # INCOMPLETE；运行整体仍在执行的其他阶段继续保持 PENDING。
            stage_run_status = run.status
            if (
                str(run.status or "").upper() not in {"SUCCESS", "FAILED", "CANCELLED"}
                and str(getattr(stage, "status", "") or "").upper()
                in {"SUCCESS", "FAILED", "SKIPPED", "CANCELLED"}
            ):
                stage_run_status = "SUCCESS"
            result = cls._calculate_stage_status(stage, artifacts, run_params, stage_run_status)
            stage_results.append(result)
            ConfigurationTaskStageDao.update_run_stage(
                db,
                stage.run_stage_id,
                {
                    "evidence_status": result.status,
                    "evidence_missing_json": _dumps(result.missing),
                },
            )
        result = cls._aggregate_run_status(run.status, stage_results)
        ConfigurationTaskRunDao.update_run(
            db,
            task_run_id,
            {
                "evidence_status": result.status,
                "evidence_missing_json": _dumps(result.missing),
            },
        )
        if commit:
            db.commit()
        logger.debug(
            f"重算配置任务证据状态: task_run_id={task_run_id}, "
            f"status={result.status}, missing={len(result.missing)}"
        )
        return result

    @classmethod
    def _calculate_stage_status(
        cls,
        stage: Any,
        artifacts: list[Any],
        run_params: dict[str, Any],
        run_status: str,
    ) -> EvidenceStatusResult:
        """根据阶段策略和产物列表计算阶段状态。"""
        policy = load_json_object(getattr(stage, "evidence_policy_json", "{}"))
        mode = str(policy.get("mode") or "NONE").strip().upper()
        if mode == "NONE":
            return EvidenceStatusResult("NOT_REQUIRED", [])

        plan = run_params.get("evidencePlan") if isinstance(run_params, dict) else {}
        plan_steps = plan.get("steps") if isinstance(plan, dict) else {}
        if not isinstance(plan_steps, dict):
            plan_steps = {}
        stage_ids = {str(item) for item in load_json_list(getattr(stage, "step_ids_json", "[]")) if item}
        candidates: list[dict[str, Any]] = []
        for step_id, item in plan_steps.items():
            if not isinstance(item, dict):
                continue
            if stage_ids and str(step_id) not in stage_ids:
                continue
            evidence_type = str(item.get("evidenceType") or "checkpoint_screenshot").strip()
            if evidence_type == "failure_screenshot":
                continue
            candidates.append(
                {
                    "evidenceType": evidence_type,
                    "evidenceKey": str(item.get("evidenceKey") or step_id).strip(),
                    "sequenceNo": max(int(item.get("sequenceNo") or 1), 1),
                    "required": bool(item.get("required")),
                }
            )

        expected = cls._build_expected_items(mode, policy, candidates)
        if not expected:
            # OPTIONAL 没有实际要求时不应制造缺失项；有产物则标记为已采集。
            has_evidence = any(
                _normalize_evidence_type(getattr(item, "evidence_type", ""), getattr(item, "artifact_type", ""))
                in {"checkpoint_screenshot", "before_screenshot", "after_screenshot"}
                and getattr(item, "evidence_type", "") != "failure_screenshot"
                for item in artifacts
            )
            return EvidenceStatusResult("COMPLETE" if has_evidence else "NOT_REQUIRED", [])

        missing: list[dict[str, Any]] = []
        failed = False
        for item in expected:
            matches = [artifact for artifact in artifacts if cls._artifact_matches(artifact, item)]
            if not matches:
                missing.append({**item, "reason": "未收到对应证据"})
                continue
            online = [
                artifact
                for artifact in matches
                if (getattr(artifact, "availability_status", "ONLINE") or "ONLINE")
                == "ONLINE"
            ]
            if not online:
                failed = True
                missing.append({**item, "reason": "证据资源不可取回"})

        if failed:
            return EvidenceStatusResult("FAILED", missing)
        if not missing:
            return EvidenceStatusResult("COMPLETE", [])
        terminal = str(run_status or "").upper() in {"SUCCESS", "FAILED", "CANCELLED"}
        return EvidenceStatusResult("INCOMPLETE" if terminal else "PENDING", missing)

    @staticmethod
    def _build_expected_items(
        mode: str,
        policy: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将阶段策略转换为待匹配的证据项。"""
        if mode == "OPTIONAL":
            required_candidates = [item for item in candidates if item.get("required")]
            return required_candidates
        if mode == "BEFORE_AFTER":
            required_types = policy.get("requiredTypes") or policy.get("required_types") or [
                "before_screenshot",
                "after_screenshot",
            ]
        else:
            required_types = policy.get("requiredTypes") or policy.get("required_types") or []
        required_keys = policy.get("requiredEvidenceKeys") or policy.get("required_evidence_keys") or []
        expected: list[dict[str, Any]] = []
        if required_types:
            for evidence_type in required_types:
                evidence_type = str(evidence_type).strip()
                if not evidence_type or evidence_type == "failure_screenshot":
                    continue
                matching = [item for item in candidates if item["evidenceType"] == evidence_type]
                # requiredTypes 表达“该类型至少有一项”，不把同类型的多张截图
                # 展开成多个必需项；若要精确要求某张或某个序号，应使用 requiredEvidenceKeys。
                expected.append(
                    {
                        "evidenceType": evidence_type,
                        "evidenceKey": "",
                        "sequenceNo": None,
                    }
                    if matching
                    else {"evidenceType": evidence_type, "evidenceKey": "", "sequenceNo": 1}
                )
        elif mode == "REQUIRED":
            expected.extend(candidates)
        for evidence_key in required_keys:
            key = str(evidence_key or "").strip()
            if not key:
                continue
            matching = [item for item in candidates if item["evidenceKey"] == key]
            expected.extend(matching or [{"evidenceType": None, "evidenceKey": key, "sequenceNo": 1}])
        unique: list[dict[str, Any]] = []
        identities: set[tuple[Any, Any, Any]] = set()
        for item in expected:
            identity = (item.get("evidenceType"), item.get("evidenceKey", ""), item.get("sequenceNo", 1))
            if identity not in identities:
                identities.add(identity)
                unique.append(item)
        return unique

    @staticmethod
    def _artifact_matches(artifact: Any, expected: dict[str, Any]) -> bool:
        """判断产物是否满足一个证据项，失败截图永不满足验收证据。"""
        evidence_type = _normalize_evidence_type(
            getattr(artifact, "evidence_type", ""), getattr(artifact, "artifact_type", "")
        )
        if evidence_type == "failure_screenshot":
            return False
        expected_type = expected.get("evidenceType")
        if expected_type and evidence_type != expected_type:
            return False
        expected_key = str(expected.get("evidenceKey") or "")
        if expected_key and str(getattr(artifact, "evidence_key", "") or "") != expected_key:
            return False
        expected_sequence = expected.get("sequenceNo")
        if expected_sequence is None:
            return True
        return int(getattr(artifact, "sequence_no", 1) or 1) == int(expected_sequence or 1)

    @staticmethod
    def _aggregate_run_status(run_status: str, results: list[EvidenceStatusResult]) -> EvidenceStatusResult:
        """把阶段状态汇总为运行状态。"""
        if not results or all(item.status == "NOT_REQUIRED" for item in results):
            return EvidenceStatusResult("NOT_REQUIRED", [])
        missing: list[dict[str, Any]] = []
        has_pending = False
        has_failed = False
        for item in results:
            missing.extend(item.missing)
            has_pending = has_pending or item.status == "PENDING"
            has_failed = has_failed or item.status == "FAILED"
        if has_failed:
            status = "FAILED"
        elif missing and (str(run_status or "").upper() in {"SUCCESS", "FAILED", "CANCELLED"}):
            status = "INCOMPLETE"
        elif has_pending or missing:
            status = "PENDING"
        else:
            status = "COMPLETE"
        return EvidenceStatusResult(status, missing)
