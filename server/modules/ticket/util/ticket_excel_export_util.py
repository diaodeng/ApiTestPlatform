"""
工单导出 Excel 生成工具，负责按列定义和行数据生成 .xlsx 字节流。

设计原则：
- 不访问数据库，不处理业务逻辑。
- 先写入临时文件，再流式读取返回，避免大量数据堆积在内存中。
- 表头加粗、浅色背景、冻结首行。
"""
import os
import tempfile
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# 导出最大行数
MAX_EXPORT_ROWS = 10000

# 默认列宽
DEFAULT_COL_WIDTH = 16
MAX_COL_WIDTH = 48


class ExportColumn:
    """导出列定义。"""

    def __init__(self, key: str, label: str, required: bool = False):
        self.key = key
        self.label = label
        self.required = required


def _resolve_columns(
    all_columns: list[ExportColumn],
    requested_keys: list[str],
) -> list[ExportColumn]:
    """
    按请求的 key 列表解析最终导出列，未指定时使用全部列。
    :param all_columns: 全部可用列定义
    :param requested_keys: 前端传入的列 key 列表
    :return: 最终导出列列表
    """
    if not requested_keys:
        return list(all_columns)
    key_set = set(requested_keys)
    resolved = [col for col in all_columns if col.key in key_set]
    if not resolved:
        return list(all_columns)
    return resolved


def _guess_column_width(header: str, sample_values: list[str]) -> float:
    """
    根据表头和一个样本值估算列宽，取中文字符宽度约 2.2。
    :param header: 列标题
    :param sample_values: 样本值列表
    :return: 列宽
    """
    max_len = len(header) * 2.2  # 中文字符宽度
    for val in sample_values:
        if val is None:
            continue
        text = str(val)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_chars = len(text) - chinese_chars
        width = chinese_chars * 2.2 + ascii_chars * 1.1
        if width > max_len:
            max_len = width
    return min(max(max_len + 2, DEFAULT_COL_WIDTH), MAX_COL_WIDTH)


def _make_header_style() -> dict[str, Any]:
    """生成表头样式。"""
    return {
        "font": Font(bold=True, size=11),
        "fill": PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid"),
        "alignment": Alignment(horizontal="center", vertical="center", wrap_text=True),
    }


def _format_cell_value(value: Any) -> str:
    """格式化单元格值，None 转为 '-'。"""
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def generate_excel_bytes(
    columns: list[ExportColumn],
    rows: list[dict[str, Any]],
    sheet_name: str = "Sheet1",
) -> bytes:
    """
    生成 Excel 文件字节流（先写临时文件再流式读取）。
    :param columns: 导出列定义
    :param rows: 已格式化的行数据，每行是 {key: value} 字典
    :param sheet_name: 工作表名称
    :return: Excel 文件字节流
    """
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(
            f"当前匹配 {len(rows)} 条，超过单次导出上限 {MAX_EXPORT_ROWS} 条，请缩小筛选条件后重试。"
        )

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    # 写入表头
    header_style = _make_header_style()
    for col_idx, col in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col.label)
        cell.font = header_style["font"]
        cell.fill = header_style["fill"]
        cell.alignment = header_style["alignment"]

    # 写入数据行
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, col in enumerate(columns, 1):
            value = row_data.get(col.key)
            ws.cell(row=row_idx, column=col_idx, value=_format_cell_value(value))

    # 设置列宽（基于前 100 行样本）
    sample_rows = rows[:100]
    for col_idx, col in enumerate(columns, 1):
        sample_values = [row.get(col.key) for row in sample_rows]
        width = _guess_column_width(col.label, sample_values)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # 冻结首行
    ws.freeze_panes = "A2"

    # 写入临时文件
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    try:
        os.close(tmp_fd)
        wb.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def generate_excel_file_stream(
    columns: list[ExportColumn],
    rows: list[dict[str, Any]],
    sheet_name: str = "Sheet1",
):
    """
    生成 Excel 文件流（生成器），用于 StreamingResponse。
    :param columns: 导出列定义
    :param rows: 已格式化的行数据
    :param sheet_name: 工作表名称
    :yield: 文件字节块
    """
    data = generate_excel_bytes(columns, rows, sheet_name)
    yield data
