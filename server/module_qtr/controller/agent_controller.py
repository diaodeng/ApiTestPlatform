import base64
import gzip
import zlib

from fastapi import APIRouter, WebSocket
from fastapi.responses import JSONResponse
import asyncio
import json
import uuid
from module_hrm.entity.vo.agent_vo import AgentModel


agentController = APIRouter(prefix='/qtr/agent')

# 存储agent的WebSocket连接和Future对象（用于HTTP请求等待WebSocket响应）
agents = {}
response_futures = {}
MAX_MESSAGE_SIZE = 1024

# 这是您的检查函数，它应该是异步的
async def check_dictionary():
    # print("Checking dictionary...")
    # 这里执行您的检查逻辑
    pass
    # ...
    # print("Dictionary check completed.")

# 这是一个后台任务，它会定期调用检查函数
async def background_task():
    while True:
        await check_dictionary()
        await asyncio.sleep(10)  # 等待5秒钟后再次调用检查函数

# 应用启动事件处理器
async def startup_handler():
    # 在启动时创建一个后台任务
    asyncio.create_task(background_task())
    print("Background task started.")

@agentController.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    agents[agent_id] = websocket

    # 当有新的WebSocket连接时，初始化一个空的字典来存储该agent的待处理Future对象
    if agent_id not in response_futures:
        response_futures[agent_id] = {}


    try:
        while True:
            data = await websocket.receive_text()
            # 解析接收到的消息
            message_data = json.loads(data)

            # 检查消息类型是否为分片
            if message_data['type'] == 'chunk':
                # 获取分片信息
                index = message_data['index']
                total = message_data['total']
                data_chunk = message_data['data']

                # 将分片存储在字典中
                if agent_id not in response_futures[agent_id]:
                    response_futures[agent_id][agent_id] = {
                        'total': total,
                        'chunks': [None] * total  # 初始化分片数组
                    }

                # 存储分片数据
                response_futures[agent_id][agent_id]['chunks'][index] = data_chunk

                # 检查是否收到了所有的分片
                if all(chunk is not None for chunk in response_futures[agent_id][agent_id]['chunks']):
                    # 重新组装消息
                    complete_message = ''.join(response_futures[agent_id][agent_id]['chunks'])
                    # 解压数据
                    data = decompress_text(complete_message)

                    # 将字符串转换为字节
                    string_bytes = data.encode('utf-8')

                    # 使用 base64 模块进行解码
                    encoded_bytes = base64.b64decode(string_bytes)

                    # 将编码后的字节转换回字符串
                    data = encoded_bytes.decode('utf-8')

                    response_data = json.loads(data)

                    # 检查是否有等待这个响应的Future对象
                    # 假设response_data中包含一个"request_id"字段来标识是哪个HTTP请求发送的消息
                    request_id = response_data.get("request_id")
                    if request_id and agent_id in response_futures and request_id in response_futures[agent_id]:
                        # 设置Future对象的结果
                        response_futures[agent_id][request_id].set_result(response_data)
                        # 从字典中移除这个Future对象，因为它已经被设置了结果
                        del response_futures[agent_id][request_id]
                    # 从字典中移除已处理的分片
                    del response_futures[agent_id][agent_id]
            else:
                # 如果不是分片消息，则直接处理（这里可以根据需要添加逻辑）
                pass


    except Exception as e:
        print(f"Error with {agent_id}: connection closed, {e}")
    finally:
        try:
            del agents[agent_id]
            # 取消所有未处理的Future对象
            if agent_id in response_futures:
                for future in response_futures[agent_id].values():
                    future.cancel()
                del response_futures[agent_id]
            await websocket.close()
        except Exception as e:
            pass
        finally:
            print(f"Connection closed for agent: {agent_id}")


@agentController.post("/send/{agent_id}")
async def send_message(agent_id: str, message: dict, request_id: str = None):
    print(f'agents==========>>>{agents}')
    # 如果没有提供request_id，则生成一个唯一的标识符
    if not request_id:
        request_id = str(uuid.uuid4())

    if agent_id in agents:
        # 创建一个Future对象来代表异步操作的结果
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # 将Future对象存储在字典中，以便稍后设置其结果
        if agent_id not in response_futures:
            response_futures[agent_id] = {}
        response_futures[agent_id][request_id] = future

        # 发送消息到WebSocket，并包含request_id以便客户端能够识别是哪个请求的响应
        message['request_id'] = request_id
        message = json.dumps(message)
        # 将字符串转换为字节
        string_bytes = message.encode('utf-8')

        # 使用 base64 模块进行编码
        encoded_bytes = base64.b64encode(string_bytes)

        # 将编码后的字节转换回字符串
        message = encoded_bytes.decode('utf-8')

        # 压缩数据
        message = compress_text(message)
        await agents[agent_id].send_text(json.dumps(message))

        # 等待Future对象的结果（即WebSocket客户端的响应）
        try:
            response = await asyncio.wait_for(future, timeout=10)
            # return JSONResponse({"status": "sent", "agent_id": agent_id, "response": response, "request_id": request_id})
            return JSONResponse(response)
        except asyncio.TimeoutError:
            # 如果超时，取消Future对象
            if agent_id in response_futures and request_id in response_futures[agent_id]:
                response_futures[agent_id][request_id].cancel()
                del response_futures[agent_id][request_id]
            return JSONResponse(
                {"status": "timeout", "message": "No response from agent within 10 seconds", "request_id": request_id},
                status_code=408)
    else:
        return JSONResponse({"status": "error", "message": "Agent not connected", "request_id": request_id},
                            status_code=404)


@agentController.on_event("startup")
async def startup_event():
    # 可以在这里进行一些启动时的初始化
    print("Server started")


@agentController.on_event("shutdown")
async def shutdown_event():
    # 确保所有WebSocket连接在服务器关闭时被正确关闭
    for agent_id, websocket in agents.items():
        await websocket.close()
    print("Server shut down")


def compress_text(text: str) -> str:
    """
    压缩文本内容
    """
    print(f"压缩前大小：{len(text)}")
    # logger.debug(f"压缩前数据：{text}")
    # 压缩文本
    compressed_data = gzip.compress(text.encode('utf-8'))
    # logger.debug(f"解压后的数据：{gzip.decompress(compressed_data).decode('utf8')}")
    # logger.info(compressed_data)
    # 使用 base64 编码
    encoded_data = base64.b64encode(compressed_data).decode('utf8')
    # logger.info(f"编码后的数据：{encoded_data}")
    print(f"压缩后大小：{len(encoded_data)}")
    return encoded_data

def decompress_text(encoded_data: str) -> str:
    """
    被压缩后再经过base64编码的数据，先base64解码再解压
    """

    decode_data = base64.b64decode(encoded_data.encode("utf-8"))
    if decode_data.startswith(b'x\x9c'):
        decompress_text = zlib.decompress(decode_data).decode("utf8")
    elif decode_data.startswith(b'x\x1f') or decode_data.startswith(b'\x1f\x8b'):
        decompress_text = gzip.decompress(decode_data).decode("utf-8")
    else:
        raise TypeError("解压失败")
    # decompress_text = gzip.decompress(decode_data).decode("utf-8")
    return decompress_text
