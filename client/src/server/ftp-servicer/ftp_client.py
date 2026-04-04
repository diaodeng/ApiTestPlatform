import ftplib
import os
import sys
import argparse
from getpass import getpass


class FTPClientCLI:
    def __init__(self):
        self.ftp = None
        self.current_local_dir = os.getcwd()
        self.current_remote_dir = "/"

    def connect(self, host, port=21, username=None, password=None):
        """连接到 FTP 服务器"""
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(host, port)

            if username is None:
                username = input("用户名: ")
            if password is None:
                password = getpass("密码: ")

            self.ftp.login(username, password)
            print(f"成功连接到 {host}:{port}")

            # 获取当前远程目录
            self.current_remote_dir = self.ftp.pwd()
            self.show_remote_dir()

            return True

        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def show_remote_dir(self):
        """显示远程目录内容"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        print(f"\n远程目录: {self.current_remote_dir}")
        print("-" * 50)

        try:
            files = []
            self.ftp.retrlines('LIST', files.append)

            for file in files:
                print(file)

        except Exception as e:
            print(f"获取目录列表失败: {e}")

    def show_local_dir(self):
        """显示本地目录内容"""
        print(f"\n本地目录: {self.current_local_dir}")
        print("-" * 50)

        try:
            items = os.listdir(self.current_local_dir)
            for item in items:
                full_path = os.path.join(self.current_local_dir, item)
                if os.path.isdir(full_path):
                    print(f"[目录] {item}")
                else:
                    size = os.path.getsize(full_path)
                    print(f"[文件] {item} ({size} 字节)")

        except Exception as e:
            print(f"获取本地目录列表失败: {e}")

    def change_remote_dir(self, path):
        """改变远程目录"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        try:
            self.ftp.cwd(path)
            self.current_remote_dir = self.ftp.pwd()
            self.show_remote_dir()

        except Exception as e:
            print(f"改变目录失败: {e}")

    def change_local_dir(self, path):
        """改变本地目录"""
        try:
            if path == "..":
                new_path = os.path.dirname(self.current_local_dir)
            else:
                new_path = os.path.abspath(path)

            if os.path.exists(new_path) and os.path.isdir(new_path):
                self.current_local_dir = new_path
                self.show_local_dir()
            else:
                print("目录不存在")

        except Exception as e:
            print(f"改变本地目录失败: {e}")

    def download_file(self, remote_file, local_file=None):
        """下载文件"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        if local_file is None:
            local_file = remote_file

        local_path = os.path.join(self.current_local_dir, local_file)

        try:
            with open(local_path, 'wb') as f:
                self.ftp.retrbinary(f'RETR {remote_file}', f.write)
            print(f"文件下载成功: {remote_file} -> {local_path}")

        except Exception as e:
            print(f"下载失败: {e}")

    def upload_file(self, local_file, remote_file=None):
        """上传文件"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        if remote_file is None:
            remote_file = os.path.basename(local_file)

        local_path = os.path.join(self.current_local_dir, local_file)

        if not os.path.exists(local_path):
            print("本地文件不存在")
            return

        try:
            with open(local_path, 'rb') as f:
                self.ftp.storbinary(f'STOR {remote_file}', f)
            print(f"文件上传成功: {local_path} -> {remote_file}")

        except Exception as e:
            print(f"上传失败: {e}")

    def delete_remote_file(self, filename):
        """删除远程文件"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        try:
            self.ftp.delete(filename)
            print(f"文件删除成功: {filename}")

        except Exception as e:
            print(f"删除失败: {e}")

    def create_remote_dir(self, dirname):
        """创建远程目录"""
        if not self.ftp:
            print("未连接到 FTP 服务器")
            return

        try:
            self.ftp.mkd(dirname)
            print(f"目录创建成功: {dirname}")

        except Exception as e:
            print(f"创建目录失败: {e}")

    def show_help(self):
        """显示帮助信息"""
        help_text = """
FTP 客户端命令:
  ls, dir        - 显示远程目录内容
  lls, ldir      - 显示本地目录内容
  cd <path>      - 改变远程目录
  lcd <path>     - 改变本地目录
  get <file>     - 下载文件
  put <file>     - 上传文件
  delete <file>  - 删除远程文件
  mkdir <dir>    - 创建远程目录
  pwd           - 显示当前远程目录
  lpwd          - 显示当前本地目录
  help          - 显示此帮助信息
  quit, exit    - 退出程序
        """
        print(help_text)

    def interactive_mode(self):
        """交互式模式"""
        print("FTP 客户端 (输入 'help' 查看帮助)")

        while True:
            try:
                command = input("\nftp> ").strip()
                if not command:
                    continue

                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ['quit', 'exit']:
                    if self.ftp:
                        self.ftp.quit()
                    print("再见!")
                    break

                elif cmd in ['help', '?']:
                    self.show_help()

                elif cmd in ['ls', 'dir']:
                    self.show_remote_dir()

                elif cmd in ['lls', 'ldir']:
                    self.show_local_dir()

                elif cmd == 'cd':
                    if args:
                        self.change_remote_dir(args[0])
                    else:
                        print("用法: cd <路径>")

                elif cmd == 'lcd':
                    if args:
                        self.change_local_dir(args[0])
                    else:
                        print("用法: lcd <路径>")

                elif cmd == 'pwd':
                    print(f"远程目录: {self.current_remote_dir}")

                elif cmd == 'lpwd':
                    print(f"本地目录: {self.current_local_dir}")

                elif cmd == 'get':
                    if args:
                        local_name = args[1] if len(args) > 1 else None
                        self.download_file(args[0], local_name)
                    else:
                        print("用法: get <远程文件> [本地文件名]")

                elif cmd == 'put':
                    if args:
                        remote_name = args[1] if len(args) > 1 else None
                        self.upload_file(args[0], remote_name)
                    else:
                        print("用法: put <本地文件> [远程文件名]")

                elif cmd == 'delete':
                    if args:
                        self.delete_remote_file(args[0])
                    else:
                        print("用法: delete <文件名>")

                elif cmd == 'mkdir':
                    if args:
                        self.create_remote_dir(args[0])
                    else:
                        print("用法: mkdir <目录名>")

                else:
                    print(f"未知命令: {cmd}")

            except KeyboardInterrupt:
                print("\n使用 'quit' 命令退出")
            except Exception as e:
                print(f"错误: {e}")


def main():
    parser = argparse.ArgumentParser(description='FTP 客户端')
    parser.add_argument('--host', help='FTP 服务器地址')
    parser.add_argument('--port', type=int, default=21, help='FTP 服务器端口')
    parser.add_argument('--username', help='用户名')
    parser.add_argument('--password', help='密码')

    args = parser.parse_args()

    client = FTPClientCLI()

    if args.host:
        # 命令行模式
        if client.connect(args.host, args.port, args.username, args.password):
            client.interactive_mode()
    else:
        # 交互式输入连接信息
        host = input("FTP 服务器地址: ")
        port = input("端口 (默认 21): ")
        port = int(port) if port else 21

        if client.connect(host, port):
            client.interactive_mode()


if __name__ == "__main__":
    main()