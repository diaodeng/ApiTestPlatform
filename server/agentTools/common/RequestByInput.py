import json

import httpx
import websockets
from httpx import HTTPError
from loguru import logger

from common.enums import RequestTypeEnum, get_enum_name
from common.SerializeData import serialize_response
from common.utils import bs64_to_text, text_to_bs64, compress_text
from websockets import InvalidStatusCode


class RequestByInput:
    def __init__(self):
        pass

    @classmethod
    async def forward_by_rules(self, req_data):
        """根据入参转发请求"""
        client_status = True
        req_data = bs64_to_text(req_data)
        req_data = json.loads(req_data)
        request_id = req_data.pop('request_id')
        request_type = req_data.pop('requestType')
        res_data = {}
        if request_type == RequestTypeEnum.http.value:
            with httpx.Client() as client:
                try:
                    res_response = client.request(**req_data)
                    res_data = serialize_response(res_response)
                except HTTPError as e:
                    logger.error(e)
                    # client_status = False
                except InvalidStatusCode as e:
                    logger.error(e.args)
                    res_data['Error'] = str(e)
                    # client_status = False
                except Exception as e:
                    logger.error(e)
                    res_data["Error"] = f'{e.args}'
                    # client_status = False
                res_data['request_id'] = request_id
                res_data['request_type'] = request_type
                string_to_encode = json.dumps(res_data, indent=4)
                encoded_string = text_to_bs64(string_to_encode)
                return compress_text(encoded_string), client_status
        elif request_type == RequestTypeEnum.websocket.value:
            try:
                ws_res_data, response_headers = await self.websocket_agent(req_data)
                res_data = {"ws_res_data": ws_res_data, "response_headers": response_headers}
                logger.info(f"ws响应数据：{res_data},ws响应headers:{response_headers}")
            except InvalidStatusCode as e:
                logger.error(e.args)
                res_data['Error'] = str(e)
                # client_status = False
            except Exception as e:
                logger.error(e.args)
                res_data['Error'] = f'{e.args}'
                # client_status = False
            res_data['request_id'] = request_id
            res_data['request_type'] = request_type
            string_to_encode = json.dumps(res_data, indent=4)
            encoded_string = text_to_bs64(string_to_encode)
            return compress_text(encoded_string), client_status
        else:
            res_data = {"request_id": request_id, "request_type": request_type, "message": f"请求类型错误:{get_enum_name(RequestTypeEnum, request_type)}"}
            string_to_encode = json.dumps(res_data)
            encoded_string = text_to_bs64(string_to_encode)
            return compress_text(encoded_string), client_status

    @classmethod
    async def websocket_agent(self, req_data: dict):
        uri = req_data["url"]
        logger.info(f"ws请求地址:{uri}")
        ws_req_data = req_data.get("data")
        logger.info(f"ws请求入参:{ws_req_data}")
        recv_num = req_data.get("recv_num")
        logger.info(f"ws接收数据条数:{recv_num}")
        try:
            async with websockets.connect(uri) as websocket:
                await websocket.send(ws_req_data)
                res_data = []
                for i in range(recv_num):
                    response = await websocket.recv()
                    res_data.append(response)
                logger.info(f"响应数据{res_data}")
                response_headers = json.dumps(dict(websocket.response_headers))
                return res_data, response_headers
        except ConnectionError as e:
            logger.error(e)
            return json.dumps({"message": f'ConnectionError:{e}'}), None
