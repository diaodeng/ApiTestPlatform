from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler, ThrottledDTPHandler
from pyftpdlib.servers import FTPServer
import os
import logging
import argparse


class CustomFTPHandler(FTPHandler):
    def on_connect(self):
        print(f"{self.remote_ip}:{self.remote_port} 已连接")

    def on_disconnect(self):
        print(f"{self.remote_ip}:{self.remote_port} 已断开")

    def on_login(self, username):
        print(f"用户 {username} 已登录")

    def on_logout(self, username):
        print(f"用户 {username} 已登出")

    def on_file_sent(self, file):
        print(f"文件 {file} 已发送")

    def on_file_received(self, file):
        print(f"文件 {file} 已接收")

    def on_incomplete_file_sent(self, file):
        print(f"文件 {file} 发送未完成")

    def on_incomplete_file_received(self, file):
        print(f"文件 {file} 接收未完成")
        # 删除不完整的文件
        try:
            os.remove(file)
        except:
            pass


def create_ftp_server(host='0.0.0.0', port=2121,
                      username='user', password='password',
                      ftp_root='./ftp_root',
                      max_connections=256, max_per_ip=5,
                      enable_anonymous=False,
                      upload_speed=None, download_speed=None):
    # 创建 FTP 根目录
    if not os.path.exists(ftp_root):
        os.makedirs(ftp_root)
        print(f"已创建 FTP 根目录: {ftp_root}")

    # 创建授权器
    authorizer = DummyAuthorizer()

    # 添加用户
    # 权限说明：
    # e - 改变目录
    # l - 列出文件
    # r - 读取文件
    # a - 追加文件
    # d - 删除文件
    # f - 重命名文件
    # m - 创建目录
    # w - 写入文件
    # M - 文件传输模式
    authorizer.add_user(username, password, ftp_root,
                        perm="elradfmwMT")

    # 可选：添加匿名用户
    if enable_anonymous:
        anonymous_root = os.path.join(ftp_root, "anonymous")
        if not os.path.exists(anonymous_root):
            os.makedirs(anonymous_root)
        authorizer.add_anonymous(anonymous_root, perm="elr")

    # 创建 FTP 处理器
    handler = CustomFTPHandler
    handler.authorizer = authorizer

    # 设置带宽限制
    if upload_speed or download_speed:
        dtp_handler = ThrottledDTPHandler
        if upload_speed:
            dtp_handler.read_limit = upload_speed * 1024  # KB/s
        if download_speed:
            dtp_handler.write_limit = download_speed * 1024  # KB/s
        handler.dtp_handler = dtp_handler

    # 配置处理器
    handler.banner = "欢迎使用自定义 FTP 服务器"
    handler.masquerade_address = None  # 用于 NAT 环境
    handler.passive_ports = range(60000, 61000)  # 被动模式端口范围

    # 创建服务器
    address = (host, port)
    server = FTPServer(address, handler)

    # 设置连接限制
    server.max_cons = max_connections
    server.max_cons_per_ip = max_per_ip

    return server


def run_server(host='0.0.0.0', port=2121,
                      username='user', password='password',
                      ftp_root='./ftp_root',
                      max_connections=256, max_per_ip=5,
                      enable_anonymous=False,
                      upload_speed=None, download_speed=None):
    create_ftp_server(host, port, username, password, ftp_root, max_connections).serve_forever()


def main():
    parser = argparse.ArgumentParser(description='FTP 服务器')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=2121, help='监听端口')
    parser.add_argument('--username', default='user', help='FTP 用户名')
    parser.add_argument('--password', default='password', help='FTP 密码')
    parser.add_argument('--root', default='d:/', help='FTP 根目录')
    parser.add_argument('--max-conn', type=int, default=256, help='最大连接数')
    parser.add_argument('--max-per-ip', type=int, default=5, help='每 IP 最大连接数')
    parser.add_argument('--anonymous', action='store_true', help='启用匿名访问')
    parser.add_argument('--upload-limit', type=int, help='上传速度限制 (KB/s)')
    parser.add_argument('--download-limit', type=int, help='下载速度限制 (KB/s)')

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建并启动服务器
    server = create_ftp_server(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        ftp_root=args.root,
        max_connections=args.max_conn,
        max_per_ip=args.max_per_ip,
        enable_anonymous=args.anonymous,
        upload_speed=args.upload_limit,
        download_speed=args.download_limit
    )

    print(f"FTP 服务器配置:")
    print(f"  地址: {args.host}:{args.port}")
    print(f"  用户名: {args.username}")
    print(f"  密码: {args.password}")
    print(f"  根目录: {args.root}")
    print(f"  最大连接数: {args.max_conn}")
    print(f"  每 IP 最大连接数: {args.max_per_ip}")
    print(f"  匿名访问: {'启用' if args.anonymous else '禁用'}")
    if args.upload_limit:
        print(f"  上传限制: {args.upload_limit} KB/s")
    if args.download_limit:
        print(f"  下载限制: {args.download_limit} KB/s")
    print("\n按 Ctrl+C 停止服务器")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        server.close_all()


if __name__ == "__main__":
    main()