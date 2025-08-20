import datetime
import json
import os

from sqlalchemy.orm import Session
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.do.report_do import HrmReport
from jinja2 import Environment, FileSystemLoader

from module_hrm.entity.vo.report_vo import ReportQueryModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel
from module_hrm.enums.enums import CaseRunStatus
from module_hrm.utils.util import format_duration
from utils.jinja_template import TemplateHandler


class ReportService:
    def __init__(self):
        pass

    def get_report_by_id(self, report_id: int) -> HrmReport:
        pass

    def get_report_by_name(self, report_name: str) -> HrmReport:
        pass

    def generate_report(self, report_name: str, report_content: str) -> HrmReport:
        pass

    def update_report(self, report_id: int, report_name: str, report_content: str) -> HrmReport:
        pass

    def delete_report(self, report_id: int) -> HrmReport:
        pass

    def create_report(self, report_name: str, **kwargs) -> HrmReport:
        report = HrmReport(report_name=report_name, **kwargs)

    @classmethod
    def generate_html_report(cls, query_db: Session, query_info: RunDetailQueryModel, data_scope_sql:str) -> str:
        # 2. 渲染HTML模板
        result = RunDetailDao.list(query_db, query_info, data_scope_sql)
        success_count = 0
        fail_count = 0
        skip_count = 0
        total_time = 0
        max_time = 0
        min_time = 0
        avg_time = 0

        for item in result:
            new_detail_data = ""
            run_detail_dict = json.loads(item["runDetail"])
            for step in run_detail_dict.get("teststeps", []):
                new_detail_data += "\n".join(step.get("result", {}).get("logs", {}).values())

            item["runDetail"] = new_detail_data

            run_time = round(item["runDuration"], 2)
            if run_time > max_time:
                max_time = run_time
            if run_time < min_time:
                min_time = run_time
            total_time += run_time

            run_status = item["status"]
            if run_status == CaseRunStatus.passed.value:
                success_count += 1
            elif run_status == CaseRunStatus.failed.value:
                fail_count += 1
            elif run_status == CaseRunStatus.skipped.value:
                skip_count += 1

        if len(result) > 0:
            avg_time = total_time / len(result)

        info = {
            "count": len(result),
            "success": success_count,
            "successPercent": f"{round(success_count / len(result) * 100, 2)}%",
            "fail": fail_count,
            "failPercent": f"{round(fail_count / len(result) * 100, 2)}%",
            "skip": skip_count,
            "skipPercent": f"{round(skip_count / len(result) * 100, 2)}%",
            "maxTime": format_duration(max_time),
            "minTime": format_duration(min_time),
            "avgTime": format_duration(avg_time),
            "totalTime": format_duration(total_time),
        }

        curren_dir = os.path.dirname(__file__)
        template_dir = os.path.join(os.path.dirname(curren_dir), 'templates')

        report = ReportDao.get_by_id(query_db, query_info.report_id)


        html_content = TemplateHandler(template_dir).generate_html(
            template_file="report.html",
            data={
                "title": f"{report.report_name}",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "report_name": report.report_name,
                "start_time": report.start_at.strftime("%Y-%m-%d %H:%M:%S"),
                "data": result,
                "info": info,
            })
        return html_content

    @classmethod
    def generate_pdf_report(cls, query_db: Session, query_info: RunDetailQueryModel, data_scope_sql:str) -> bytes|bool:
        result = RunDetailDao.list(query_db, query_info, data_scope_sql)

        curren_dir = os.path.dirname(__file__)
        template_dir = os.path.join(os.path.dirname(curren_dir), 'templates')

        pdf_content = TemplateHandler(template_dir).generate_pdf(
            template_file="report.html",
            data={
                "title": "数据报告",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": result,
            })
        return pdf_content
