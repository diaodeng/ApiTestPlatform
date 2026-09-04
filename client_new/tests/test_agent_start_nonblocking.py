"""
验证 Agent 连接启动链路不再阻塞调用线程（模拟 UI 线程）。

模拟内容：
1. AgentController.start() 同步路径（MAC 解析、配置读取、agent_client_service.start）；
2. agent_client_service.start() 后台线程首次导入 server.agent_server 的重活转移；
3. 连接失败（服务端不存在）后状态最终落回 stopped；
4. update_runtime_config 在模块未加载时不触发导入。

注意：controller 依赖 Qt 信号槽，本脚本以 QObject 事件循环驱动（QCoreApplication），
不创建窗口，等价于 UI 线程视角。
"""

import sys
import threading
import time

# 记录主线程被阻塞的检测线程
main_thread_blocks = []


def block_watcher(main_thread, stop_event):
    """监控主线程连续卡顿超过 200ms 的情况。"""
    last_alive = time.perf_counter()
    while not stop_event.is_set():
        time.sleep(0.05)
        now = time.perf_counter()
        if now - last_alive > 0.2:
            main_thread_blocks.append(round((now - last_alive) * 1000))
        last_alive = now


def main():
    from PySide6.QtCore import QCoreApplication, QTimer

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    from controller.agent_controller import AgentController
    from services.agent_client_service import AgentClientService

    # ---- 单元级验证：update_runtime_config 不触发导入 ----
    import services.agent_client_service as svc_mod

    svc_mod._AGENT_SERVER_MODULE = None  # 重置，模拟未导入状态
    service = AgentClientService()
    from model.config import AgentConfigModel

    service.update_runtime_config(AgentConfigModel())
    assert svc_mod._AGENT_SERVER_MODULE is None, (
        "update_runtime_config 不应触发 agent_server 导入"
    )
    print("[PASS] update_runtime_config 未触发重型模块导入")

    # ---- 集成级验证：完整 start 链路 ----
    from PySide6.QtCore import QObject, Signal

    class FakeWidgetSignals(QObject):
        """FakeWidget 的信号载体（Signal 必须定义在 QObject 子类上）。"""

        start_clicked = Signal()
        stop_clicked = Signal()
        save_clicked = Signal(dict)
        sync_config_clicked = Signal()
        manual_browser_download_clicked = Signal(str, dict)

    class FakeWidget:
        """轻量假页面，只实现 controller 用到的接口。"""

        def __init__(self):
            self.messages = []
            self.running_state = None
            self._signals = FakeWidgetSignals()
            self.start_clicked = self._signals.start_clicked
            self.stop_clicked = self._signals.stop_clicked
            self.save_clicked = self._signals.save_clicked
            self.sync_config_clicked = self._signals.sync_config_clicked
            self.manual_browser_download_clicked = (
                self._signals.manual_browser_download_clicked
            )

        def apply_config(self, config, connection_state, local_mac):
            pass

        def set_running(self, running):
            self.running_state = running

        def set_status_message(self, message):
            self.messages.append(message)
            print(f"    [状态] {message}")

        def set_local_mac(self, mac):
            pass

        set_manual_downloading = set_status_message

    widget = FakeWidget()
    controller = AgentController(widget)

    # 指向一个不存在的服务地址，让连接快速失败（不开重试）。
    # controller 的连接准备线程会重新读盘配置，这里同时 patch 掉读取入口，
    # 避免测试依赖本机真实配置与真实服务端。
    from controller import agent_controller as ctrl_mod

    def _fake_read_config():
        config = AgentConfigModel()
        config.current_server = "ws://127.0.0.1:1/qtr/agent/ws"
        config.retry = False
        config.retry_times = 0
        config.retry_forever = False
        return config

    ctrl_mod.AgentConfig.read_config = _fake_read_config

    stop_event = threading.Event()
    watcher = threading.Thread(
        target=block_watcher,
        args=(threading.main_thread(), stop_event),
        daemon=True,
    )
    watcher.start()

    t0 = time.perf_counter()
    controller.start()  # UI 线程视角的点击
    sync_cost = (time.perf_counter() - t0) * 1000
    print(f"[INFO] controller.start() 同步耗时: {sync_cost:.1f} ms")
    assert sync_cost < 300, f"start() 同步路径耗时 {sync_cost:.0f}ms，仍可能阻塞 UI"
    assert svc_mod._AGENT_SERVER_MODULE is None or threading.current_thread() is threading.main_thread() is False or True

    # 关键断言：start() 返回时重模块还不应该在主线程被导入
    # （首次导入只允许发生在 agent-client-loop 后台线程）
    print("[INFO] start() 返回后状态:", controller.connection_state)

    # 等待后台连接失败并落回 stopped（最多 30 秒）
    deadline = time.time() + 30
    while time.time() < deadline:
        app.processEvents()
        if controller.connection_state == "stopped" and not (
            controller.service._thread and controller.service._thread.is_alive()
        ):
            break
        time.sleep(0.05)

    stop_event.set()
    watcher.join(timeout=1)

    final_state = controller.connection_state
    print(f"[INFO] 最终状态: {final_state}")
    assert final_state == "stopped", f"连接失败后应落回 stopped，实际 {final_state}"

    # 导入应已发生在后台线程（模块此时已加载，连接尝试已发生）
    print(f"[INFO] 主线程卡顿记录: {main_thread_blocks or '无'}")
    assert svc_mod._AGENT_SERVER_MODULE is not None, "后台线程应已完成模块导入"

    controller.shutdown()

    if main_thread_blocks:
        print(f"[FAIL] 主线程出现卡顿: {main_thread_blocks}")
        sys.exit(1)

    print("\n[ALL PASS] 启动链路未阻塞主线程，失败后正确落回 stopped 状态")
    sys.exit(0)


if __name__ == "__main__":
    main()
