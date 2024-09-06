import asyncio
import json

import websockets

class PromoDataHandle:
    def __init__(self, **kwargs):
        self.url = kwargs.get('url')
        self.venderId = kwargs.get('venderId')
        self.data = kwargs.get('ws_data')
    async def websocket_get_pro_ids(self):
        async with websockets.connect(self.url) as websocket:
            await websocket.send(json.dumps(self.data))
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
            return pro_ids, user_pro_info


    async def websocket_stop_pro_ids(token, vender_id, pro_ids):
        url = f"ws://test-idms-api.rta-os.com/websocket/sql_execute?token={token}"
        sql = f"update `promo_instance` set `pro_status` = 7 where `vender_id` = {vender_id} and `pro_id` in {pro_ids};"
        # data = {"data": {"database": "rta_promotion", "instance_id": 25263, "explain": False,
        #                  "sql": sql}, "type": "execute"}
        # async with websockets.connect(url) as websocket:
        #     await websocket.send(json.dumps(data))
        #     res_data = []
        #     for i in range(3):
        #         response = await websocket.recv()
        #         res_data.append(response)
        #     result = json.loads(res_data[2]).get('data', None)
        #     pro_ids = []
        #     if result:
        #         res_data = result.get('result', None)
        #         if res_data:
        #             for pro_info in res_data:
        #                 pro_ids.append(pro_info.get('C_1'))
        #     return pro_ids
        print(sql)


if __name__ == '__main__':

    data = {
        "url": "ws://test-idms-api.rta-os.com/websocket/sql_execute?token=e7b0bf9b062dee8f816a887d6cf16f7610387034",
        "venderId": 11,
        "ws_data": {
            "data": {
                "database": "rta_promotion",
                "instance_id": 25263,
                "explain": False,
                "sql": "SELECT a.`pro_id`, a.`vender_id`, a.`pro_status`, a.`pro_creater_name`, a.`pro_creater_id`, b.`store_join_type` FROM `promo_instance` a left join `promo_join_executor` b on a.`pro_id` = b.`pro_id` left join `promo_apply` c on a.`pro_id` = c.`pro_id` where a.`pro_status` = 4 and a.`vender_id` = 11 and (a.`pro_creater_name` = 'Sync Admin' or (b.`store_join_type` = 1 and a.`bar_code` IS NULL and a.`pro_id` not in (select d.`pro_id` from `promo_apply` d group by d.`pro_id` having count(case when d.`apply_type` =11 then 1 end)>0))) group by a.`pro_id` limit 10",
            },
            "type": "execute"
        }
    }
    handle = PromoDataHandle(**data)
    pro_ids, user_pro_info = asyncio.run(handle.websocket_get_pro_ids())
    from utils.feishu import Feishu

    vender_id = 11
    limit = 5
    content = f"即将强制结束商家：{vender_id}, 以下用户创建的促销单，原因是包含了全部门店，且未设置资格码"
    for k, v in user_pro_info.items():
        content = content + '\r\n用户名：' + k + ' 促销单：' + str(v)
    content = content + f'\r\n本次任务共处理数据：{len(pro_ids)}条'
    # Feishu().sendTextmessage(content)
    # asyncio.run(websocket_stop_pro_ids(token, 11, tuple(pro_ids)))
    print(content)
