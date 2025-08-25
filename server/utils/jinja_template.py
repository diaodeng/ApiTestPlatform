import os
import pdfkit
from jinja2 import Environment, FileSystemLoader


class TemplateHandler:
    def __init__(self, templates_dir: str):
        self.env = Environment(loader=FileSystemLoader(templates_dir))

    def generate_html(self, template_file: str, data: dict) -> str:
        # 2. 渲染HTML模板
        template = self.env.get_template(template_file)
        html_content = template.render(**data)
        return html_content

    def generate_pdf(self, template_file: str, data: dict) -> bytes|bool:
        html = self.generate_html(template_file, data)

        path_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wk)

        pdf = pdfkit.from_string(html, False, configuration=config)
        return pdf