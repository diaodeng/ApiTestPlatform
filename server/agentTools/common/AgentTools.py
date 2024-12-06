import json
import socket
import threading
import time
from loguru import logger
import requests
from urllib.parse import urlparse, parse_qs, unquote

# 配置信息
CONFIG = {
    'listen_address': '127.0.0.1',
    'listen_port': 8081,
    'forward_base_url': 'http://127.0.0.1:5001'
}


class AgentTools:
    def __init__(self):
        self.running = True

    def handle_client(self, client_socket):
        """处理客户端请求，转发并返回响应"""
        response = b''
        body = b''
        # 请求方法、路径、协议版本
        method, path, _ = '', '', ''
        header_flag = False
        headers = {}
        logger.info(f'开始接收数据')
        starttime = time.time()
        while True:
            res = client_socket.recv(1024)
            if res:
                response += res
                # 解析Content-Length
                if not header_flag:
                    header, body = response.split(b'\r\n\r\n', 1)
                    header_lines = header.split(b'\r\n')
                    if header_lines:
                        # 第一行是请求方法、路径、协议
                        method, path, _ = header_lines[0].decode().split(' ')
                        # 移除第一行
                        header_lines = header_lines[1:]
                    # 创建headers字典
                    headers = {line.split(b': ', 1)[0].decode(): line.split(b': ', 1)[1].decode() for line in
                               header_lines if line}
                    if 'Content-Length' in headers:
                        header_flag = True
                if header_flag:
                    content_length = int(headers['Content-Length'])
                    header, body = response.split(b'\r\n\r\n', 1)
                    if len(body) >= content_length:
                        # 数据接收完毕，退出循环
                        if 'param=' in body.decode():
                            data = unquote(body.decode().split('param=', 1)[1].replace('+', ''))
                            logger.info(json.dumps(data, ensure_ascii=False))
                        logger.info(f'body={body}')
                        break
            else:
                # 没有数据可接收，等待或退出
                break

        recv_time = time.time() - starttime
        logger.info(f'数据接受完成：{recv_time}')
        # 构造转发URL
        forward_url = f"{CONFIG['forward_base_url']}{path}"
        logger.info(forward_url)

        # 解析查询字符串为字典
        params = parse_qs(body)

        req_start_time = time.time()
        # 转发请求
        response = requests.request(method, forward_url, params=params)
        req_res_time = time.time() - req_start_time
        logger.info(f'转发请求响应时长：{req_res_time}')
        # 将响应发送回客户端
        client_socket.sendall(response.content)
        client_socket.close()
        pushd_time = time.time() - starttime
        logger.info(f'总耗时：{pushd_time}')

    def start_server(self, CONFIG):
        """启动监听服务器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((CONFIG['listen_address'], CONFIG['listen_port']))
        server_socket.listen(5)
        logger.info(f"Listening on {CONFIG['listen_address']}:{CONFIG['listen_port']}")
        client_thread = None
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                logger.info(f"Received connection from {addr}")
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
        finally:
            self.running = False
            server_socket.close()
            client_thread.join(timeout=10)
