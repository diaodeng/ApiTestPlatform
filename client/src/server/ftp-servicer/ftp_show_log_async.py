import aioftp
import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class AsyncFTPClient:
    def __init__(self, host: str, port: int = 21, username: str = "anonymous", password: str = "anonymous"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.current_remote_path = "/"
        self.current_local_path = Path.cwd()

    async def connect(self) -> bool:
        """连接到 FTP 服务器"""
        try:
            self.client = aioftp.Client()
            await self.client.connect(self.host, self.port)
            await self.client.login(self.username, self.password)
            self.current_remote_path = await self.client.get_current_directory()
            print(f"✅ 已连接到 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.quit()
            self.client = None
            print("🔌 已断开连接")

    async def list_directory(self, path: str = ".") -> List[Dict]:
        """列出目录内容"""
        try:
            if path == ".":
                path = self.current_remote_path

            files = []
            async for path, info in self.client.list(path):
                files.append({
                    'name': path.name,
                    'type': 'directory' if info['type'] == 'dir' else 'file',
                    'size': info.get('size', 0),
                    'modified': info.get('modify', 'Unknown'),
                    'permissions': info.get('perm', '')
                })

            return files
        except Exception as e:
            print(f"❌ 列出目录失败: {e}")
            return []

    async def change_directory(self, path: str):
        """改变远程目录"""
        try:
            await self.client.change_directory(path)
            self.current_remote_path = await self.client.get_current_directory()
            print(f"📁 当前目录: {self.current_remote_path}")
        except Exception as e:
            print(f"❌ 改变目录失败: {e}")

    async def download_file(self, remote_path: str, local_path: Optional[str] = None):
        """下载文件"""
        try:
            if not local_path:
                local_path = Path(remote_path).name

            local_file = self.current_local_path / local_path

            print(f"⬇️  下载中: {remote_path} -> {local_file}")

            async with self.client:
                await self.client.download(remote_path, local_file)

            file_size = local_file.stat().st_size
            print(f"✅ 下载完成: {local_file} ({file_size} 字节)")

        except Exception as e:
            print(f"❌ 下载失败: {e}")

    async def upload_file(self, local_path: str, remote_path: Optional[str] = None):
        """上传文件"""
        try:
            local_file = self.current_local_path / local_path

            if not local_file.exists():
                print(f"❌ 本地文件不存在: {local_file}")
                return

            if not remote_path:
                remote_path = local_file.name

            print(f"⬆️  上传中: {local_file} -> {remote_path}")

            async with self.client:
                await self.client.upload(local_file, remote_path)

            print(f"✅ 上传完成: {remote_path}")

        except Exception as e:
            print(f"❌ 上传失败: {e}")

    async def delete_file(self, remote_path: str):
        """删除远程文件"""
        try:
            await self.client.remove(remote_path)
            print(f"🗑️  已删除: {remote_path}")
        except Exception as e:
            print(f"❌ 删除失败: {e}")

    async def create_directory(self, dirname: str):
        """创建远程目录"""
        try:
            await self.client.make_directory(dirname)
            print(f"📂 已创建目录: {dirname}")
        except Exception as e:
            print(f"❌ 创建目录失败: {e}")

    async def get_file_info(self, remote_path: str) -> Optional[Dict]:
        """获取文件信息"""
        try:
            async for path, info in self.client.list(remote_path):
                if path.name == Path(remote_path).name:
                    return {
                        'name': path.name,
                        'type': 'directory' if info['type'] == 'dir' else 'file',
                        'size': info.get('size', 0),
                        'modified': info.get('modify', 'Unknown'),
                        'permissions': info.get('perm', '')
                    }
            return None
        except Exception as e:
            print(f"❌ 获取文件信息失败: {e}")
            return None

    async def tail_file(self, remote_path: str, lines: int = 50, follow: bool = False):
        """查看文件尾部内容，类似 tail 命令"""
        try:
            content = []
            async with self.client:
                async for block in self.client.download_stream(remote_path):
                    content.append(block.decode('utf-8', errors='ignore'))

            full_content = ''.join(content)
            file_lines = full_content.split('\n')

            # 显示最后几行
            start_line = max(0, len(file_lines) - lines)
            tail_content = '\n'.join(file_lines[start_line:])

            print(f"📄 文件: {remote_path}")
            print("-" * 50)
            print(tail_content)
            print("-" * 50)

            if follow:
                print("🔍 进入监控模式...")
                await self.monitor_file_tail(remote_path, lines)

        except Exception as e:
            print(f"❌ 读取文件失败: {e}")

    async def monitor_file_tail(self, remote_path: str, lines: int = 50, interval: float = 2.0):
        """监控文件尾部变化"""
        monitor = AsyncFTPTail(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            remote_file_path=remote_path,
            tail_lines=lines,
            poll_interval=interval
        )

        try:
            await monitor.monitor_file()
        except KeyboardInterrupt:
            monitor.stop()


class AsyncFTPInteractive:
    """交互式异步 FTP 客户端"""

    def __init__(self):
        self.ftp_client = None
        self.is_running = False

    async def start_interactive(self):
        """启动交互式会话"""
        print("🚀 异步 FTP 客户端")
        print("=" * 50)

        # 获取连接信息
        host = input("FTP 服务器地址: ").strip()
        port = int(input("端口 (默认 21): ").strip() or "21")
        username = input("用户名 (默认 anonymous): ").strip() or "anonymous"
        password = input("密码 (默认 anonymous): ").strip() or "anonymous"

        # 连接服务器
        self.ftp_client = AsyncFTPClient(host, port, username, password)
        if not await self.ftp_client.connect():
            return

        self.is_running = True
        await self.show_help()

        # 命令循环
        while self.is_running:
            try:
                command = input(f"\nftp://{host}> ").strip()
                if not command:
                    continue

                await self.execute_command(command)

            except KeyboardInterrupt:
                print("\n🛑 使用 'quit' 命令退出")
            except Exception as e:
                print(f"❌ 错误: {e}")

    async def execute_command(self, command: str):
        """执行命令"""
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ['quit', 'exit']:
            self.is_running = False
            await self.ftp_client.disconnect()
            print("👋 再见!")

        elif cmd in ['help', '?']:
            await self.show_help()

        elif cmd in ['ls', 'dir', 'list']:
            path = args[0] if args else "."
            files = await self.ftp_client.list_directory(path)
            await self.display_file_list(files)

        elif cmd == 'cd':
            if args:
                await self.ftp_client.change_directory(args[0])
            else:
                print("❌ 用法: cd <路径>")

        elif cmd == 'pwd':
            print(f"📁 {self.ftp_client.current_remote_path}")

        elif cmd == 'get':
            if args:
                local_name = args[1] if len(args) > 1 else None
                await self.ftp_client.download_file(args[0], local_name)
            else:
                print("❌ 用法: get <远程文件> [本地文件名]")

        elif cmd == 'put':
            if args:
                remote_name = args[1] if len(args) > 1 else None
                await self.ftp_client.upload_file(args[0], remote_name)
            else:
                print("❌ 用法: put <本地文件> [远程文件名]")

        elif cmd == 'delete':
            if args:
                await self.ftp_client.delete_file(args[0])
            else:
                print("❌ 用法: delete <文件名>")

        elif cmd == 'mkdir':
            if args:
                await self.ftp_client.create_directory(args[0])
            else:
                print("❌ 用法: mkdir <目录名>")

        elif cmd == 'tail':
            follow = '-f' in args
            clean_args = [arg for arg in args if arg != '-f']

            if clean_args:
                lines = 50
                if len(clean_args) > 1 and clean_args[0].startswith('-n'):
                    try:
                        lines = int(clean_args[0][2:])
                        file_path = clean_args[1]
                    except:
                        file_path = clean_args[0]
                else:
                    file_path = clean_args[0]

                await self.ftp_client.tail_file(file_path, lines, follow)
            else:
                print("❌ 用法: tail [-n 行数] [-f] <文件路径>")

        elif cmd == 'info':
            if args:
                info = await self.ftp_client.get_file_info(args[0])
                if info:
                    print(json.dumps(info, indent=2, ensure_ascii=False))
                else:
                    print("❌ 文件不存在或无法访问")
            else:
                print("❌ 用法: info <文件路径>")

        else:
            print(f"❌ 未知命令: {cmd}")

    async def display_file_list(self, files: List[Dict]):
        """显示文件列表"""
        if not files:
            print("📁 目录为空")
            return

        print(f"{'类型':<8} {'权限':<10} {'大小':<12} {'修改时间':<20} {'名称'}")
        print("-" * 70)

        for file in files:
            file_type = "📁" if file['type'] == 'directory' else "📄"
            size = self.format_size(file['size']) if file['type'] == 'file' else ""
            print(f"{file_type:<8} {file['permissions']:<10} {size:<12} {file['modified']:<20} {file['name']}")

    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    async def show_help(self):
        """显示帮助信息"""
        help_text = """
📖 可用命令:
  ls, dir, list [路径]    - 列出目录内容
  cd <路径>               - 改变远程目录
  pwd                     - 显示当前远程目录
  get <文件> [本地名]     - 下载文件
  put <文件> [远程名]     - 上传文件
  delete <文件>           - 删除远程文件
  mkdir <目录名>          - 创建远程目录
  tail [-n 行数] [-f] <文件> - 查看文件尾部内容 (-f 持续监控)
  info <文件>             - 显示文件信息
  help, ?                - 显示此帮助
  quit, exit             - 退出程序
        """
        print(help_text)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='异步 FTP 客户端')
    parser.add_argument('--host', help='FTP 服务器地址')
    parser.add_argument('--port', type=int, default=21, help='FTP 服务器端口')
    parser.add_argument('--username', help='用户名')
    parser.add_argument('--password', help='密码')
    parser.add_argument('--command', help='直接执行命令')

    args = parser.parse_args()

    if args.host:
        # 命令行模式
        client = AsyncFTPClient(
            host=args.host,
            port=args.port,
            username=args.username or "anonymous",
            password=args.password or "anonymous"
        )

        if await client.connect():
            if args.command:
                # 执行单个命令
                pass
            else:
                # 交互模式
                interactive = AsyncFTPInteractive()
                interactive.ftp_client = client
                await interactive.start_interactive()
    else:
        # 交互式输入模式
        interactive = AsyncFTPInteractive()
        await interactive.start_interactive()


if __name__ == "__main__":
    asyncio.run(main())