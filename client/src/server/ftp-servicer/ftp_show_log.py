import ftplib
import time
import os
import threading
from datetime import datetime
import sys


class FTPFileMonitor:
    def __init__(self, host, port=21, username=None, password=None, remote_file_path=None, local_display_file=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_file_path = remote_file_path
        self.local_display_file = local_display_file or "ftp_monitor_display.txt"

        self.ftp = None
        self.last_size = 0
        self.last_mtime = None
        self.running = False
        self.thread = None

        # 显示配置
        self.tail_lines = 20  # 显示最后多少行
        self.poll_interval = 2  # 轮询间隔（秒）

    def connect(self):
        """连接到 FTP 服务器"""
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, self.port)
            if self.username and self.password:
                self.ftp.login(self.username, self.password)
            else:
                self.ftp.login()  # 匿名登录
            print(f"已连接到 FTP 服务器 {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开 FTP 连接"""
        if self.ftp:
            try:
                self.ftp.quit()
            except:
                pass
            self.ftp = None

    def get_file_size(self):
        """获取远程文件大小"""
        try:
            size = self.ftp.size(self.remote_file_path)
            return int(size) if size else 0
        except:
            return 0

    def get_file_mtime(self):
        """获取远程文件修改时间（如果支持）"""
        try:
            # 尝试使用 MDTM 命令获取文件修改时间
            resp = self.ftp.voidcmd(f"MDTM {self.remote_file_path}")
            if resp.startswith('213'):
                # 格式: 213 20231119233000
                mtime_str = resp[4:].strip()
                return datetime.strptime(mtime_str, '%Y%m%d%H%M%S')
        except:
            pass
        return None

    def download_new_content(self):
        """下载文件的新内容"""
        try:
            current_size = self.get_file_size()

            # 如果文件大小变小了（可能是文件被截断或重新创建）
            if current_size < self.last_size:
                print("检测到文件被截断或重新创建，重新开始监控")
                self.last_size = 0

            # 如果没有新内容
            if current_size <= self.last_size:
                return None

            # 下载新内容
            start_pos = self.last_size
            data = []

            def callback(chunk):
                data.append(chunk.decode('utf-8', errors='ignore'))

            self.ftp.retrbinary(f"RETR {self.remote_file_path}", callback, rest=start_pos)

            new_content = ''.join(data)
            self.last_size = current_size

            return new_content

        except Exception as e:
            print(f"下载新内容失败: {e}")
            return None

    def update_display(self, new_content):
        """更新本地显示文件"""
        try:
            # 如果文件不存在，创建它
            if not os.path.exists(self.local_display_file):
                with open(self.local_display_file, 'w', encoding='utf-8') as f:
                    f.write("")

            # 读取现有内容
            with open(self.local_display_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 添加新内容
            if new_content:
                new_lines = new_content.split('\n')
                lines.extend(new_lines)

            # 保持只显示最后 tail_lines 行
            if len(lines) > self.tail_lines:
                lines = lines[-self.tail_lines:]

            # 写入更新后的内容
            with open(self.local_display_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            # 在控制台也显示新内容
            if new_content:
                print(new_content.rstrip())

        except Exception as e:
            print(f"更新显示失败: {e}")

    def monitor_loop(self):
        """监控循环"""
        print(f"开始监控文件: {self.remote_file_path}")
        print(f"显示文件: {self.local_display_file}")
        print(f"按 Ctrl+C 停止监控")
        print("-" * 50)

        # 初始下载整个文件（或最后部分）
        try:
            initial_size = self.get_file_size()
            # 只下载最后部分内容
            start_pos = max(0, initial_size - 1024)  # 最后1KB
            data = []

            def callback(chunk):
                data.append(chunk.decode('utf-8', errors='ignore'))

            self.ftp.retrbinary(f"RETR {self.remote_file_path}", callback, rest=start_pos)
            initial_content = ''.join(data)

            # 只取最后 tail_lines 行
            lines = initial_content.split('\n')
            if len(lines) > self.tail_lines:
                initial_content = '\n'.join(lines[-self.tail_lines:])

            self.update_display(initial_content)
            self.last_size = initial_size

        except Exception as e:
            print(f"初始下载失败: {e}")

        # 监控循环
        while self.running:
            try:
                new_content = self.download_new_content()
                if new_content:
                    self.update_display(new_content)

                time.sleep(self.poll_interval)

            except Exception as e:
                print(f"监控循环错误: {e}")
                # 尝试重新连接
                time.sleep(5)
                if not self.connect():
                    print("重新连接失败，退出监控")
                    break

    def start_monitoring(self):
        """开始监控"""
        if not self.connect():
            return False

        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        return True

    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.disconnect()
        print("监控已停止")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='FTP 文件监控工具 (类似 tail -f)')
    parser.add_argument('--host', required=True, help='FTP 服务器地址')
    parser.add_argument('--port', type=int, default=21, help='FTP 服务器端口')
    parser.add_argument('--username', help='用户名')
    parser.add_argument('--password', help='密码')
    parser.add_argument('--file', required=True, help='要监控的远程文件路径')
    parser.add_argument('--display', help='本地显示文件路径')
    parser.add_argument('--lines', type=int, default=20, help='显示的行数')
    parser.add_argument('--interval', type=float, default=2, help='轮询间隔（秒）')

    args = parser.parse_args()

    # 创建监控器
    monitor = FTPFileMonitor(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        remote_file_path=args.file,
        local_display_file=args.display
    )

    monitor.tail_lines = args.lines
    monitor.poll_interval = args.interval

    # 开始监控
    if not monitor.start_monitoring():
        sys.exit(1)

    try:
        # 保持主线程运行
        while monitor.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到中断信号...")
    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()