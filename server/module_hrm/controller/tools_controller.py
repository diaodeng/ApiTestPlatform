import base64

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from utils.common_util import AdvancedJsonParser, SmartJsonParser, WhitelistJsonParser
from utils.log_util import logger
from utils.response_util import ResponseUtil

toolsController = APIRouter(prefix='/hrm/tools')


class ParseJsonParam(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True,
                              populate_by_name=True
                              )
    content: str | None = None
    white_list: list[str] | set[str] | None = None
    advanced: bool | None = None
    nested_parse: bool | None = None


@toolsController.post("/jsonParse")
def json_parse(request: Request,
                     data: ParseJsonParam):
    try:
        logger.info(data.model_dump_json())
        if data.content:
            row_test = base64.b64decode(data.content).decode("utf-8")

            # 使用专门的多层转义解析器
            # json_data = MultiEscapeJsonParser.smart_decode(row_test)

            if data.advanced:
                # 使用高级解析器
                parser = AdvancedJsonParser()
                json_data = parser.advanced_parse(row_test)
            else:
                # 使用智能解析器
                parser = SmartJsonParser()
                json_data = parser.smart_parse(row_test)

            if data.nested_parse:
                # 递归解析嵌套的 JSON 字符串
                json_data = parser.parse_nested_json_strings(json_data)

            if data.white_list:
                json_data = WhitelistJsonParser(data.white_list).parse(json_data)
        else:
            json_data = ""
        return ResponseUtil.success(data=json_data)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
