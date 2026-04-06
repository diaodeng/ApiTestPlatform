import concurrent.futures
import fnmatch
import os

from loguru import logger
from PySide6.QtCore import QObject, QThreadPool, Signal

from model.config import PosChangeParamsModel
from server.config import PosConfig, SearchConfig
from server.pos_config_server import PosConfigServer
from server.pos_tool_config_server import PosToolConfigServer
from services.pos_service import PosService
from utils.common import ExeVersionReader
from utils.file_handle import open_file_location
from workers.worker import Worker


class PosController(QObject):
    # ======================
    # 信号定义
    # ======================
    result_signal = Signal(str)  # 搜索结果
    status_signal = Signal(str)  # 状态
    log_signal = Signal(str)  # 日志
    finished_signal = Signal()  # 完成

    def __init__(self):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(4)
        self._scan_running = False
        self._env_loading_paths = set()

    # ======================
    # 搜索
    # ======================
    def start_search(self, file_pattern: str, dir_pattern: str, depth: int):
        if self._scan_running:
            self.status_signal.emit("扫描进行中，请稍候")
            return

        self._scan_running = True
        self.status_signal.emit("开始扫描...")

        def run():
            dirs = SearchConfig.read_work_dir()
            if not dirs:
                raise Exception("未设置工作目录")

            result_set = set()
            max_depth = max(1, int(depth or 1))
            pattern = (file_pattern or "*").strip() or "*"
            subdir_pattern = (dir_pattern or "*").strip() or "*"
            for d in dirs:
                if not d or not os.path.isdir(d):
                    logger.warning(f"工作目录不存在，已跳过: {d}")
                    continue
                files = self._scan_dir(d, pattern, subdir_pattern, max_depth)
                result_set.update(files)

            result = sorted(result_set)
            SearchConfig.save_search_result(result)
            return result

        worker = Worker(run)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_search_finished(self, result):
        self._scan_running = False
        self.status_signal.emit(f"扫描完成，共 {len(result)} 个")
        for path in result:
            self.result_signal.emit(path)
        self.finished_signal.emit()

    # ======================
    # 启动 POS
    # ======================
    def start_pos(self, path: str, dialog_service):
        self.status_signal.emit(f"启动中: {path}")

        ok, ctx = PosService.prepare_start(dialog_service, path)

        if not ok:
            self.status_signal.emit("启动已取消")
            return

        self.status_signal.emit("检查完成，开始启动...")

        def run():
            pid = PosService.execute_start(ctx)
            return pid

        worker = Worker(run)
        worker.signals.finished.connect(lambda pid: self._on_start_finished(path, pid))
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_start_finished(self, path, pid):
        msg = f"启动成功 PID={pid}"
        logger.info(msg)

        self.status_signal.emit(msg)
        self.log_signal.emit(msg)

    # ======================
    # 停止当前 POS
    # ======================
    def stop_pos(self):
        self.status_signal.emit("停止POS中...")

        def run():
            return PosService.stop_current()

        worker = Worker(run)
        worker.signals.finished.connect(self._on_stop_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_stop_finished(self, result):
        if result:
            msg = "POS已停止"
        else:
            msg = "没有运行中的POS"

        self.status_signal.emit(msg)
        self.log_signal.emit(msg)

    # ======================
    # 停止离线进程
    # ======================
    def stop_offline(self):
        self.status_signal.emit("停止离线进程...")

        def run():
            names = ["java.exe"]
            return PosService.stop_offline(names)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_stop_offline_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_stop_offline_finished(self, result):
        msg = f"已停止: {result}"
        self.status_signal.emit(msg)
        self.log_signal.emit(msg)

    # ======================
    # 查看环境
    # ======================
    def get_env(self, path: str, callback=None):
        if path in self._env_loading_paths:
            logger.warning("当前POS环境信息正在获取中，忽略重复请求")
            return

        self._env_loading_paths.add(path)

        def run():
            logger.info(f"获取环境信息: {path}")

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._build_env_payload, path)
                return future.result(timeout=10)

        worker = Worker(run)
        # 👇 持有 worker，防止 GC
        if not hasattr(self, "_workers"):
            self._workers = []

        self._workers.append(worker)

        def finished(result):
            try:
                logger.info("环境信息获取完")
                msg = self._format_env_message(result)

                if callback:
                    callback(msg)

                self.log_signal.emit(msg)
            finally:
                self._env_loading_paths.discard(path)
                if worker in self._workers:
                    self._workers.remove(worker)

        worker.signals.finished.connect(finished)
        worker.signals.error.connect(self._on_error)

        self.pool.start(worker)

    def _on_env_finished(self, result):
        msg = self._format_env_message(result)

        self.status_signal.emit(msg)
        self.log_signal.emit(msg)

    # ======================
    # 通用错误处理
    # ======================
    def _on_error(self, err):
        logger.error(err)
        self._scan_running = False
        self.status_signal.emit(f"错误: {err}")
        self.log_signal.emit(f"[错误] {err}")

    # ======================
    # 切换 POS（新增）
    # ======================
    def change_pos(self, data: dict):
        self.status_signal.emit("切换POS中...")

        def run():
            logger.info(f"切换POS参数: {data}")

            request = PosChangeParamsModel.model_validate(data)

            return PosService.change_pos(request)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_change_pos_finished)
        worker.signals.error.connect(self._on_error)

        self.pool.start(worker)

    def _on_change_pos_finished(self, _):
        msg = "POS切换成功"

        self.status_signal.emit(msg)
        self.log_signal.emit(msg)

    def clean_cache(self, path: str):
        self.status_signal.emit("清理缓存中...")

        def run():
            return PosConfig.clean_cache(path)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_clean_cache_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_clean_cache_finished(self, result):
        ok, msg = result
        text = msg or ("清理缓存成功" if ok else "清理缓存失败")
        self.status_signal.emit(text)
        self.log_signal.emit(text)

    def backup_payment_driver(self, path: str):
        self.status_signal.emit("备份支付驱动中...")

        def run():
            PosConfig.backup_payment_driver(path)
            return "备份支付驱动完成"

        worker = Worker(run)
        worker.signals.finished.connect(
            lambda msg: (self.status_signal.emit(msg), self.log_signal.emit(msg))
        )
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def restore_payment_driver(self, path: str):
        self.status_signal.emit("恢复支付驱动中...")

        def run():
            PosConfig.restore_payment_driver(path)
            return "恢复支付驱动完成"

        worker = Worker(run)
        worker.signals.finished.connect(
            lambda msg: (self.status_signal.emit(msg), self.log_signal.emit(msg))
        )
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def cover_payment_driver(self, path: str):
        self.status_signal.emit("覆盖支付驱动中...")

        def run():
            return PosConfig.cover_payment_driver(path)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_cover_payment_driver_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_cover_payment_driver_finished(self, result):
        ok, msg = result
        text = msg or ("覆盖支付驱动成功" if ok else "覆盖支付驱动失败")
        self.status_signal.emit(text)
        self.log_signal.emit(text)

    def clear_pos_env_file(self, path: str):
        self.status_signal.emit("清理环境文件中...")

        def run():
            PosConfig.clear_env(path)
            return "清理当前环境文件完成"

        worker = Worker(run)
        worker.signals.finished.connect(
            lambda msg: (self.status_signal.emit(msg), self.log_signal.emit(msg))
        )
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def open_pos_location(self, path: str):
        if open_file_location(path):
            self.status_signal.emit("已打开文件所在目录")
        else:
            self.status_signal.emit("打开文件所在目录失败")

    def replace_mitm_cert(self, path: str):
        self.status_signal.emit("替换证书中...")

        def run():
            return PosConfig.replace_mitm_cert(path)

        worker = Worker(run)
        worker.signals.finished.connect(self._on_replace_cert_finished)
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _on_replace_cert_finished(self, result):
        ok, msg = result
        text = msg or ("替换证书成功" if ok else "替换证书失败")
        self.status_signal.emit(text)
        self.log_signal.emit(text)

    def logout_pos_account(self, path: str):
        self.status_signal.emit("退出账号中...")

        def run():
            PosConfigServer.logout_pos_account(path)
            return "POS账号已退出"

        worker = Worker(run)
        worker.signals.finished.connect(
            lambda msg: (self.status_signal.emit(msg), self.log_signal.emit(msg))
        )
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _scan_dir(
        self, base_dir: str, file_pattern: str, dir_pattern: str, max_depth: int
    ) -> list[str]:
        found = []

        def walk(current_dir: str, current_depth: int):
            if current_depth > max_depth:
                return

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if entry.is_file(follow_symlinks=False):
                            if fnmatch.fnmatch(
                                entry.name.lower(), file_pattern.lower()
                            ):
                                found.append(entry.path)
                            continue

                        if (
                            entry.is_dir(follow_symlinks=False)
                            and current_depth < max_depth
                        ):
                            if fnmatch.fnmatch(entry.name.lower(), dir_pattern.lower()):
                                walk(entry.path, current_depth + 1)
            except PermissionError:
                logger.warning(f"目录无访问权限，已跳过: {current_dir}")
            except FileNotFoundError:
                logger.warning(f"目录不存在，已跳过: {current_dir}")

        walk(base_dir, 1)
        return found

    def switch_pos_online_by_path(self, path: str):
        self.status_signal.emit("在线切换POS中...")

        def run():
            PosConfigServer.change_pos_on_network(path)
            return "在线切换POS成功"

        worker = Worker(run)
        worker.signals.finished.connect(
            lambda msg: (self.status_signal.emit(msg), self.log_signal.emit(msg))
        )
        worker.signals.error.connect(self._on_error)
        self.pool.start(worker)

    def _build_env_payload(self, path: str) -> dict:
        local_env = PosConfig.get_local_pos_env(path) or "-"
        version = ExeVersionReader(path).get_exe_file_version() if path else None
        pos_params, store_list, _ = PosToolConfigServer.get_store_list(path)

        remote_env = "-"
        if store_list:
            remote_env = store_list[0].env or "-"

        data = {
            "local_env": local_env,
            "remote_env": remote_env,
            "version": version or "-",
            "vender_no": "-",
            "sap_org_no": "-",
            "org_no": "-",
            "pos_id": "-",
            "is_local": True,
        }
        if pos_params:
            data["vender_no"] = str(pos_params.venderNo or "-")
            data["sap_org_no"] = str(pos_params.sapOrgNo or "-")
            data["org_no"] = str(pos_params.orgNo or "-")
            data["pos_id"] = str(pos_params.posId or "-")
            data["is_local"] = bool(pos_params.is_local)
        return data

    def _format_env_message(self, payload: dict) -> str:
        try:
            if not payload:
                return "环境信息获取失败"
            source = "本地" if payload.get("is_local", True) else "远端"
            env_show = payload.get("remote_env") or payload.get("local_env") or "-"
            return (
                f"{source} 商家:{payload.get('vender_no', '-')} | "
                f"门店ID(sap/org): {payload.get('sap_org_no', '-')}/{payload.get('org_no', '-')} | "
                f"环境:{env_show} 版本:{payload.get('version', '-')} POS:{payload.get('pos_id', '-')}"
            )
        except Exception:
            return f"组装信息异常：{str(payload)}"
