from module_hrm.entity.do.report_do import HrmReport


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
