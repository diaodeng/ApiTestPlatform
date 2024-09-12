import asyncio
import json

import websockets
from loguru import logger


class PromoDataHandle:
    def __init__(self, **kwargs):
        self.uri = kwargs.get('uri', None)
        self.venderId = kwargs.get('venderId', [])
        self.data = kwargs.get('ws_data', None)
        self.data2 = kwargs.get('ws_data2', None)

    async def websocket_get_pro_ids(self):
        async with websockets.connect(self.uri) as websocket:
            venderIds = ','.join(str(n) for n in self.venderId)
            self.data = json.dumps(self.data).replace('venderId', venderIds)
            logger.info(f'ws请求数据：{self.data}')
            await websocket.send(self.data)
            res_data = []
            for i in range(3):
                response = await websocket.recv()
                res_data.append(response)
            result = json.loads(res_data[2]).get('data', None)
            pro_ids = []
            user_pro_info = {}
            if result:
                res_data = result.get('result', None)
                if res_data:
                    for pro_info in res_data:
                        u_key = pro_info.get('C_4')
                        u_value = pro_info.get('C_1')
                        if u_key in user_pro_info:
                            user_pro_info[u_key].append(u_value)
                        else:
                            user_pro_info[u_key] = [u_value]
                        pro_ids.append(u_value)
            logger.info(f'查询到的促销单：{pro_ids}')
            logger.info(f'用户对应的促销单：{user_pro_info}')
            return pro_ids, user_pro_info

    async def websocket_stop_pro_ids(self, proIds):
        async with websockets.connect(self.uri) as websocket:
            venderIds = ','.join(str(n) for n in self.venderId)
            self.data2 = json.dumps(self.data2).replace('venderId', venderIds)
            proIds = ','.join(proId for proId in proIds)
            self.data2 = self.data2.replace('proIds', proIds)
            logger.info(f'ws请求数据：{self.data2}')
            await websocket.send(self.data2)
            response = await websocket.recv()
            logger.info(f'停止促销信息：{response}')


if __name__ == '__main__':
    pass
