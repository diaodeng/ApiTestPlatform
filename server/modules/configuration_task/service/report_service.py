"""配置任务运行报告归档服务。

报告只读取：
    configuration_task_run -> configuration_task_run_stage -> configuration_task_artifact -> resource_object

Word 文件采用零依赖方式生成：输出 Word 兼容的 HTML（.doc 扩展名），
Word/WPS 可直接打开并另存为 .docx。不引入 python-docx/PIL 等新依赖，
不把截图 Base64 嵌入报告正文，报告只引用资源 ID 和文件名。

飞书通知复用 utils.message_util.FeiShuHandler 的文本卡片能力，推送失败
只记日志，不影响报告归档结果。
"""

import hashlib
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool
from loguru import logger

from config.database import SessionLocal
from modules.configuration_task.dao.resource_dao import ResourceDao
from modules.configuration_task.dao.stage_artifact_dao import (
    ConfigurationTaskStageDao,
    TaskArtifactDao,
)
from modules.configuration_task.dao.task_dao import (
    ConfigurationTaskDao,
    ConfigurationTaskRunDao,
    load_json_object,
)
from modules.configuration_task.service.artifact_service import ConfigurationTaskArtifactService

RUN_REPORTS_DIR = Path("storage") / "configuration-task-reports"


@dataclass
class ReportServiceResult:
    """报告操作结果。"""

    is_success: bool
    message: str
    result: Any = None


def _dumps(value) -> str:
    """序列化为紧凑 JSON。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationTaskReportService:
    """运行报告生成与归档。"""

    # ---------- 报告生成 ----------

    @classmethod
    async def generate_run_report(
        cls,
        task_run_id: int,
        current_user,
        notify_feishu: bool = False,
    ) -> ReportServiceResult:
        """生成运行报告并登记为产物；DB 段与文件写入均在线程池执行。"""
        user = getattr(current_user, "user", None)
        operator = user.user_name if user else "system"
        report_payload = await run_in_threadpool(
            cls._generate_report_sync, task_run_id, operator
        )
        if isinstance(report_payload, str):
            return ReportServiceResult(False, report_payload)
        if notify_feishu:
            await run_in_threadpool(cls._notify_feishu_sync, task_run_id, report_payload)
        return ReportServiceResult(True, "报告归档成功", report_payload)

    @classmethod
    def _generate_report_sync(cls, task_run_id: int, operator: str):
        """同步生成报告：读取运行/阶段/产物数据，写 Word 兼容文件并登记资源+产物。"""
        db = SessionLocal()
        try:
            run = ConfigurationTaskRunDao.get_run(db, task_run_id)
            if not run:
                return "运行记录不存在"
            task = ConfigurationTaskDao.get_task(db, run.task_id)
            stages = ConfigurationTaskStageDao.list_run_stages(db, task_run_id)
            artifacts = TaskArtifactDao.list_artifacts(db, task_run_id)

            report_html = cls._build_report_html(
                task_name=task.task_name if task else str(run.task_id),
                run=run,
                stages=stages,
                artifacts=artifacts,
            )
            file_name = f"配置任务报告-{task_run_id}.doc"
            content = report_html.encode("utf-8")
            sha256 = hashlib.sha256(content).hexdigest()
            size = len(content)

            # 报告文件保存在服务端本地目录，资源以 server 侧执行侧登记。
            RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            object_key = f"reports/{task_run_id}/{sha256[:16]}"
            report_path = RUN_REPORTS_DIR / f"{task_run_id}_{sha256[:16]}.doc"
            if not report_path.exists():
                report_path.write_bytes(content)

            existing = ResourceDao.get_by_identity(db, "server", object_key, 1)
            if existing:
                resource = existing
            else:
                now = datetime.now()
                try:
                    resource = ResourceDao.add_resource(
                        db,
                        {
                            "provider_type": "report",
                            "provider_execution_side": "server",
                            "agent_code": "server",
                            "object_key": object_key,
                            "original_file_name": file_name,
                            "mime_type": "application/msword",
                            "file_size": size,
                            "checksum_algorithm": "sha256",
                            "sha256": sha256,
                            "version": 1,
                            "status": "READY",
                            "create_by": operator,
                            "create_time": now,
                            "update_by": operator,
                            "update_time": now,
                            "last_audit_at": now,
                            "audit_message": "运行报告归档登记",
                            "remark": f"report_path={report_path.name}",
                        },
                    )
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"报告资源登记冲突，回查已有记录: task_run_id={task_run_id}, error={exc}")
                    resource = ResourceDao.get_by_identity(db, "server", object_key, 1)
                    if not resource:
                        return "报告资源登记失败"

            artifact = ConfigurationTaskArtifactService.register_report_artifact(
                db, task_run_id, resource, operator
            )
            logger.info(
                f"运行报告归档完成: task_run_id={task_run_id}, artifact_id={artifact.artifact_id}, size={size}"
            )
            return {
                "taskRunId": str(task_run_id),
                "artifactId": str(artifact.artifact_id),
                "resourceId": str(resource.resource_id),
                "fileName": file_name,
                "fileSize": size,
                "sha256": sha256,
            }
        finally:
            db.close()

    @classmethod
    def _build_report_html(
        cls,
        task_name: str,
        run,
        stages: list,
        artifacts: list,
    ) -> str:
        """组装 Word 兼容 HTML 报告正文；产物只引用资源 ID 与文件名。"""
        escape = html.escape

        def _stage_rows() -> str:
            if not stages:
                return "<tr><td colspan='5'>未声明阶段（单阶段全量执行）</td></tr>"
            return "".join(
                f"<tr><td>{stage.stage_order}</td><td>{escape(stage.stage_key)}</td>"
                f"<td>{escape(stage.stage_name)}</td><td>{escape(stage.mode)}</td>"
                f"<td>{escape(stage.status)}</td></tr>"
                for stage in stages
            )

        def _artifact_rows() -> str:
            if not artifacts:
                return "<tr><td colspan='4'>无产物</td></tr>"
            return "".join(
                f"<tr><td>{escape(item.artifact_type)}</td><td>{escape(item.original_file_name)}</td>"
                f"<td>{item.resource_id}</td><td>{item.file_size}</td></tr>"
                for item in artifacts
            )

        result_payload = load_json_object(run.result_json) or {}
        steps_summary = result_payload.get("steps")
        step_count = len(steps_summary) if isinstance(steps_summary, list) else 0

        return f"""<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:w="urn:schemas-microsoft-com:office:word"
xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>配置任务运行报告</title></head>
<body>
<h1>配置任务运行报告</h1>
<h2>运行信息</h2>
<table border="1" cellspacing="0" cellpadding="4">
<tr><td>任务名称</td><td>{escape(task_name)}</td></tr>
<tr><td>运行ID</td><td>{run.task_run_id}</td></tr>
<tr><td>版本号</td><td>v{run.version_no}</td></tr>
<tr><td>执行Agent</td><td>{escape(run.agent_code)}</td></tr>
<tr><td>状态</td><td>{escape(run.status)}</td></tr>
<tr><td>开始时间</td><td>{run.started_at or "-"}</td></tr>
<tr><td>结束时间</td><td>{run.ended_at or "-"}</td></tr>
<tr><td>时长(毫秒)</td><td>{run.duration_ms}</td></tr>
<tr><td>步骤数</td><td>{step_count}</td></tr>
<tr><td>错误信息</td><td>{escape(run.error_message or "-")}</td></tr>
</table>
<h2>阶段执行</h2>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>顺序</th><th>阶段标识</th><th>名称</th><th>模式</th><th>状态</th></tr>
{_stage_rows()}
</table>
<h2>产物清单</h2>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>类型</th><th>文件名</th><th>资源ID</th><th>大小(字节)</th></tr>
{_artifact_rows()}
</table>
<p>报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</body></html>"""

    # ---------- 飞书通知 ----------

    @classmethod
    def _notify_feishu_sync(cls, task_run_id: int, report_payload: dict[str, Any]) -> None:
        """推送报告完成通知到飞书机器人；失败只记日志。"""
        try:
            from config.env import FeishuBotConfig
            from module_hrm.entity.vo.push_vo import FeishuRobotModel
            from utils.message_util import FeiShuHandler

            robot = FeiShuHandler(
                FeishuRobotModel(
                    url=FeishuBotConfig.feishu_bot_token,
                    secret=FeishuBotConfig.feishu_bot_key,
                    push=FeishuBotConfig.feishu_bot_push,
                )
            )
            content = (
                f"配置任务运行报告已归档\n"
                f"运行ID：{report_payload.get('taskRunId')}\n"
                f"报告文件：{report_payload.get('fileName')}\n"
                f"大小：{report_payload.get('fileSize')} 字节"
            )
            # push 内部会调用 content_text 组装卡片，这里传纯文本。
            robot.push(content)
            logger.info(f"配置任务报告飞书通知已推送: task_run_id={task_run_id}")
        except Exception as exc:
            logger.warning(f"配置任务报告飞书通知推送失败（不影响归档）: task_run_id={task_run_id}, error={exc}")
