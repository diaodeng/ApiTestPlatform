import concurrent.futures
import fnmatch
import os
import threading

from loguru import logger

from model.config import PosChangeParamsModel
from server.config import PosConfig, SearchConfig, StartConfig
from server.pos_config_server import PosConfigServer
from server.pos_tool_config_server import PosToolConfigServer
from server.remote_config_server import RemoteConfigServer
from services.pos_service import PosService
from ui_web.dialog_bridge import WebDialogService
from ui_web.event_bus import event_bus
from utils.common import (
    ExeVersionReader,
    get_active_mac,
    get_client_root_dir,
    get_local_ip,
)
from utils.file_handle import open_file_location

# POS 后台任务线程池上限（与原 QThreadPool maxThreadCount=4 对齐）。
_POOL_MAX_WORKERS = 4
# 在线切换/退出账号的互斥锁：同一时刻只允许一个此类任务（与原实现一致）。
_TASK_LOCK = threading.Lock()

# 切换 POS 表单状态的持久化文件：锚定应用根目录（打包态为 exe 目录），不随 cwd 漂移。
_CHANGE_POS_STATE_PATH = str(get_client_root_dir() / "storage" / "data" / "pos_change_state.json")


class PosApi:
    """
    POS 页面后端桥（替代原 Qt PosController 及其对话框的后端部分）。

    - 原 QThreadPool + Worker 替换为 concurrent.futures 线程池；
    - 原 status/log Signal 替换为 EventBus 推送（pos_status / pos_log）；
    - 启动 POS 过程中的确认弹窗改由 WebDialogService 桥接到前端模态框；
    - 扫描、启停、驱动/缓存/证书等操作语义与原实现一致。
    """

    def __init__(self, dialog_service: WebDialogService):
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=_POOL_MAX_WORKERS, thread_name_prefix="pos-worker"
        )
        # 弹窗桥必须使用 Bridge 下发的全局唯一实例：
        # 前端 resolve_dialog 只应答 Bridge 持有的那个实例，自建实例会导致
        # 引擎等待在另一份 pending 表上永远收不到应答，300 秒超时按取消处理
        self.dialog_service = dialog_service
        self._scan_running = False
        self._scan_lock = threading.Lock()
        self._online_switching = False
        self._logout_running = False

    # ===== 引导数据 =====

    def get_bootstrap(self) -> dict:
        """
        返回 POS 页面初始化所需的配置：搜索配置、启动配置、扫描历史。
        配置文件损坏时不抛出（否则页面初始化直接失败），改为 ok=False
        携带具体异常信息，由前端 toast 提示"配置文件异常"。
        """
        try:
            return {
                "ok": True,
                "search_config": SearchConfig.read().model_dump(),
                "start_config": StartConfig.read().model_dump(),
                "history": SearchConfig.read_search_result(),
                "pos_config": PosConfig.read_pos_config().model_dump(),
            }
        except Exception as e:
            logger.error(f"POS 页面引导数据读取失败: {e}")
            return {"ok": False, "message": str(e)}

    # ===== 搜索扫描 =====

    def save_search_config(self, data: dict) -> dict:
        """
        保存搜索配置（文件名模式/目录模式/递归深度/工作目录）。
        """
        try:
            SearchConfig.write(data)
            return {"ok": True}
        except Exception as e:
            logger.exception(f"保存搜索配置失败: {e}")
            return {"ok": False, "message": str(e)}

    def add_work_dir(self, path: str) -> dict:
        SearchConfig.add_work_dir(path)
        return {"ok": True, "work_dirs": SearchConfig.read_work_dir()}

    def remove_work_dir(self, path: str) -> dict:
        SearchConfig.remove_work_dir(path)
        return {"ok": True, "work_dirs": SearchConfig.read_work_dir()}

    def scan(self) -> dict:
        """
        按当前搜索配置扫描工作目录下的 POS 文件，结果落盘并返回。
        """
        with self._scan_lock:
            if self._scan_running:
                return {"ok": False, "message": "扫描进行中，请稍候"}
            self._scan_running = True

        self._push_status("开始扫描...")
        try:
            dirs = SearchConfig.read_work_dir()
            if not dirs:
                raise Exception("未设置工作目录")

            config = SearchConfig.read()
            result_set = set()
            max_depth = max(1, int(config.max_depth or 1))
            pattern = (config.file_pattern or "*").strip() or "*"
            subdir_pattern = (config.dir_pattern or "*").strip() or "*"
            for d in dirs:
                if not d or not os.path.isdir(d):
                    logger.warning(f"工作目录不存在，已跳过: {d}")
                    continue
                result_set.update(self._scan_dir(d, pattern, subdir_pattern, max_depth))

            result = sorted(result_set)
            SearchConfig.save_search_result(result)
            self._push_status(f"扫描完成，共 {len(result)} 个")
            return {"ok": True, "result": result}
        except Exception as e:
            logger.error(f"POS 扫描失败: {e}")
            with self._scan_lock:
                self._scan_running = False
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}
        finally:
            with self._scan_lock:
                self._scan_running = False

    def _scan_dir(self, base_dir: str, file_pattern: str, dir_pattern: str, max_depth: int) -> list[str]:
        """
        递归扫描目录，匹配文件名与目录名模式（与原控制器实现一致）。
        """
        found = []

        def walk(current_dir: str, current_depth: int):
            if current_depth > max_depth:
                return
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if entry.is_file(follow_symlinks=False):
                            if fnmatch.fnmatch(entry.name.lower(), file_pattern.lower()):
                                found.append(entry.path)
                            continue
                        if (
                            entry.is_dir(follow_symlinks=False)
                            and current_depth < max_depth
                            and fnmatch.fnmatch(entry.name.lower(), dir_pattern.lower())
                        ):
                            walk(entry.path, current_depth + 1)
            except PermissionError:
                logger.warning(f"目录无访问权限，已跳过: {current_dir}")
            except FileNotFoundError:
                logger.warning(f"目录不存在，已跳过: {current_dir}")

        walk(base_dir, 1)
        return found

    # ===== 启停 =====

    def start_pos(self, path: str) -> dict:
        """
        启动 POS：先执行启动前检查（可能弹确认框），通过后拉起进程。
        """
        self._push_status(f"启动中: {path}")
        try:
            ok, ctx = PosService.prepare_start(self.dialog_service, path)
        except Exception as e:
            logger.exception(f"POS 启动检查失败: {e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}

        if not ok:
            # 检查阶段可能已杀掉运行中的 POS（先杀后确认的既有行为），取消时需向用户说明
            killed_hint = (
                "（注意：已提前停止运行中的POS进程）"
                if ctx and getattr(ctx, "killed_running", False)
                else ""
            )
            self._push_status(f"启动已取消{killed_hint}")
            self._push_log(f"启动已取消{killed_hint}")
            return {"ok": False, "message": f"启动已取消{killed_hint}"}

        self._push_status("检查完成，开始启动...")

        future = self.pool.submit(PosService.execute_start, ctx)
        try:
            pid = future.result(timeout=120)
        except Exception as e:
            logger.exception(f"POS 启动失败: {e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}

        msg = f"启动成功 PID={pid}"
        logger.info(msg)
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": True, "pid": pid, "message": msg}

    def stop_pos(self) -> dict:
        """
        停止当前运行中的 POS 进程。
        """
        self._push_status("停止POS中...")
        try:
            result = self.pool.submit(PosService.stop_current).result(timeout=60)
        except Exception as e:
            logger.exception(f"停止 POS 失败: {e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}

        msg = "POS已停止" if result else "没有运行中的POS"
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": bool(result), "message": msg}

    def stop_offline(self) -> dict:
        """
        停止离线 java 进程。
        """
        self._push_status("停止离线进程...")
        try:
            killed = self.pool.submit(PosService.stop_offline, ["java.exe"]).result(timeout=60)
        except Exception as e:
            logger.exception(f"停止离线进程失败: {e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}

        msg = f"已停止: {killed}"
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": True, "message": msg}

    # ===== 环境信息 =====

    def get_env(self, path: str) -> dict:
        """
        获取 POS 环境信息（本地环境、版本、商家/门店/POS）。
        """
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                payload = executor.submit(self._build_env_payload, path).result(timeout=10)
            return {"ok": True, "data": payload, "message": self._format_env_message(payload)}
        except Exception as e:
            logger.warning(f"获取环境信息失败: {path}, error={e}")
            return {"ok": False, "message": str(e)}

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
            if isinstance(payload, str):
                return f"环境信息获取失败: {payload}"
            source = "本地" if payload.get("is_local", True) else "远端"
            env_show = payload.get("remote_env") or payload.get("local_env") or "-"
            return (
                f"{source} 商家:{payload.get('vender_no', '-')} | "
                f"门店ID(sap/org): {payload.get('sap_org_no', '-')}/{payload.get('org_no', '-')} | "
                f"环境:{env_show} 版本:{payload.get('version', '-')} POS:{payload.get('pos_id', '-')}"
            )
        except Exception:
            return f"组装信息异常：{payload!s}"

    # ===== 切换 POS =====

    def change_pos(self, data: dict) -> dict:
        """
        在线切换 POS（远端接口）。表单数据结构见 PosChangeParamsModel。
        """
        self._push_status("切换POS中...")
        try:
            request = PosChangeParamsModel.model_validate(data)
            logger.info(f"切换POS参数: {data}")
            PosService.change_pos(request)
        except Exception as e:
            logger.exception(f"切换POS失败: {e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}

        self._push_status("POS切换成功")
        self._push_log("POS切换成功")
        return {"ok": True, "message": "POS切换成功"}

    def get_change_pos_bootstrap(self, pos_path: str = "") -> dict:
        """
        切换 POS 弹窗初始化数据：环境/商家/门店级联配置、上次表单状态、
        指定 POS 路径时的默认值回填。
        """
        tool_config = PosToolConfigServer.read_pos_tool_config()
        env_list = []
        store_list = []
        if tool_config and getattr(tool_config, "data", None):
            env_list = [
                {"env_code": item.env_code, "env_name": item.env_name}
                for item in (tool_config.data.env_list or [])
            ]
            store_list = [
                {
                    "env": item.env,
                    "vender_id": item.vender_id,
                    "vender_name": item.vender_name,
                    "store_id": item.store_id,
                    "store_name": item.store_name,
                }
                for item in (tool_config.data.store_list or [])
            ]

        state = self._load_change_pos_state()
        if pos_path:
            self._fill_state_from_pos_path(state, pos_path)
        return {
            "ok": True,
            "env_list": env_list,
            "store_list": store_list,
            "state": state,
            "pos_mac": state.get("pos_mac") or get_active_mac() or "",
            "pos_ip": state.get("pos_ip") or get_local_ip() or "",
        }

    def save_change_pos_state(self, state: dict) -> dict:
        """
        持久化切换 POS 表单状态（与原对话框行为一致）。
        """
        try:
            import json

            os.makedirs(os.path.dirname(_CHANGE_POS_STATE_PATH), exist_ok=True)
            with open(_CHANGE_POS_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            return {"ok": True}
        except Exception as e:
            logger.warning(f"保存切换POS状态失败: {e}")
            return {"ok": False, "message": str(e)}

    def _load_change_pos_state(self) -> dict:
        try:
            import json

            if not os.path.exists(_CHANGE_POS_STATE_PATH):
                return {"switch_mode": "1", "pos_type": "1", "pos_mac": "", "pos_ip": "", "pos_no": "", "pos_group": ""}
            with open(_CHANGE_POS_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"读取切换POS状态失败: {e}")
            return {}

    def _fill_state_from_pos_path(self, state: dict, pos_path: str) -> None:
        """
        按指定 POS 路径回填表单默认值（商家/门店/POS编号/环境分组）。
        """
        try:
            params = PosConfig.read_pos_params(pos_path, 1)
            env = PosConfig.get_local_pos_env(pos_path) or ""
            if params:
                state["vendor_id"] = str(params.venderNo or "")
                state["store_id"] = str(params.orgNo or "")
                state["pos_no"] = str(params.posId or "")
                state["pos_group"] = str(getattr(params, "posGroupNo", "") or "")
                state["pos_type"] = str(params.posType or "1")
            if env and params:
                group, _ = PosConfig.get_pos_group(str(params.venderNo or ""), env)
                if group:
                    state["env"] = group
        except Exception as e:
            logger.debug(f"按POS路径回填切换状态失败: {e}")

    def switch_pos_online(self, path: str) -> dict:
        """
        对指定 POS 执行在线切换（同一时刻仅允许一个任务）。
        """
        with _TASK_LOCK:
            if self._online_switching:
                return {"ok": False, "message": "已有在线切换任务进行中，请稍候"}
            self._online_switching = True
        try:
            self._push_status("在线切换POS中...")
            logger.info(f"开始在线切换POS: {path}")
            PosConfigServer.change_pos_on_network(path)
            msg = "在线切换POS成功"
            logger.info(f"在线切换POS完成: {path}")
            self._push_status(msg)
            self._push_log(msg)
            return {"ok": True, "message": msg}
        except Exception as e:
            logger.warning(f"在线切换POS失败: {path}, error={e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}
        finally:
            self._online_switching = False

    # ===== 本地环境 =====

    def get_local_env(self, pos_path: str) -> dict:
        """
        本地环境切换弹窗数据：当前环境描述与已备份环境列表。
        """
        current_info = self._describe_current_local_env(pos_path)
        return {"ok": True, "current_info": current_info, "backed_envs": self._get_backed_env_map(pos_path)}

    def _describe_current_local_env(self, pos_path: str) -> str:
        from model.config import PosParamsModel

        local_pos_env = PosConfig.get_local_pos_env(pos_path) or "-"
        pos_params = PosConfig.read_pos_params(pos_path, 1)
        if pos_params and isinstance(pos_params, PosParamsModel):
            env_local = "本地环境" if pos_params.is_local else "远端环境"
            env_group, _ = PosConfig.get_pos_group(pos_params.venderNo, local_pos_env)
            try:
                config = PosToolConfigServer.read_pos_tool_config()
                for store_info in (config.data.store_list or []):
                    if (
                        store_info.vender_id == pos_params.venderNo
                        and store_info.env == env_group
                        and store_info.store_id == pos_params.orgNo
                    ):
                        return (
                            f"{env_local} {local_pos_env} -> {store_info.vender_name} -> "
                            f"{store_info.store_name} -> POS:{pos_params.posId}"
                        )
            except Exception:
                pass
            return (
                f"{env_local} 环境:{local_pos_env} 商家:{pos_params.venderNo} "
                f"门店:{pos_params.orgNo} POS:{pos_params.posId}"
            )
        return f"环境:{local_pos_env}，商家:无，门店:无"

    def _get_backed_env_map(self, pos_path: str) -> dict[str, str]:
        """
        汇总可选目标环境：内置环境 + pos_env_back 备份目录 + 历史记录。
        """
        cfg = PosConfig.read_pos_config()
        backed_env = ["RTA_TEST", "RTA_UAT", "RTA"]
        back_dir = os.path.join(os.path.dirname(pos_path), "pos_env_back")
        if os.path.exists(back_dir):
            backed_env.extend(
                item for item in sorted(os.listdir(back_dir))
                if os.path.isdir(os.path.join(back_dir, item))
            )
        if cfg.backup_envs and pos_path in cfg.backup_envs:
            for e in cfg.backup_envs.get(pos_path, []):
                if e not in backed_env:
                    backed_env.append(e)

        env_map = {e: e for e in backed_env}
        try:
            config = PosToolConfigServer.read_pos_tool_config()
            for key in backed_env:
                parts = key.split("_")
                if len(parts) <= 2:
                    continue
                current_env = "_".join(parts[:-2])
                vendor_id = parts[-2]
                store = parts[-1]
                env_group, _ = PosConfig.get_pos_group(vendor_id, current_env)
                for store_info in (config.data.store_list or []):
                    if (
                        store_info.vender_id == vendor_id
                        and store_info.env == env_group
                        and store_info.store_id == store
                    ):
                        env_map[key] = f"{key} -> {store_info.vender_name} -> {store_info.store_name}"
                        break
        except Exception:
            pass
        return env_map

    def change_local_env(self, pos_path: str, target_env_key: str) -> dict:
        """
        切换 POS 本地环境（先停止 CPOS 进程，再写入目标环境）。
        """
        from utils.common import kill_process_by_name

        if not target_env_key:
            return {"ok": False, "message": "请先选择目标环境"}
        try:
            kill_process_by_name("CPOS-DF.exe")
        except Exception:
            pass
        try:
            ok, msg = PosConfig.change_pos_local_env(pos_path, target_env_key)
        except Exception as e:
            logger.exception(f"切换本地环境失败: {e}")
            return {"ok": False, "message": str(e)}
        return {"ok": bool(ok), "message": msg or ("切换成功" if ok else "切换失败")}

    # ===== 远程配置同步 =====

    def sync_remote_config(self, config_url: str) -> dict:
        """
        从远端拉取 POS 配置。
        """
        self._push_status("正在更新 POS 配置...")
        try:
            result = RemoteConfigServer.sync_pos_config(config_url)
            updated_at = str((result or {}).get("updated_at") or "").strip() if isinstance(result, dict) else ""
            message = "POS 配置已更新"
            if updated_at:
                message = f"{message}，服务端更新时间：{updated_at}"
            self._push_status(message)
            self._push_log(message)
            return {"ok": True, "message": message, "result": result}
        except Exception as e:
            logger.exception(e)
            message = f"POS 配置更新失败: {e}"
            self._push_status(message)
            self._push_log(message)
            return {"ok": False, "message": message}

    # ===== 单项维护操作 =====

    def clean_cache(self, path: str) -> dict:
        self._push_status("清理缓存中...")
        try:
            ok, msg = PosConfig.clean_cache(path)
        except Exception as e:
            logger.exception(f"清理缓存失败: {e}")
            return {"ok": False, "message": str(e)}
        text = msg or ("清理缓存成功" if ok else "清理缓存失败")
        self._push_status(text)
        self._push_log(text)
        return {"ok": bool(ok), "message": text}

    def backup_payment_driver(self, path: str) -> dict:
        self._push_status("备份支付驱动中...")
        try:
            PosConfig.backup_payment_driver(path)
        except Exception as e:
            logger.exception(f"备份支付驱动失败: {e}")
            return {"ok": False, "message": str(e)}
        msg = "备份支付驱动完成"
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": True, "message": msg}

    def restore_payment_driver(self, path: str) -> dict:
        self._push_status("恢复支付驱动中...")
        try:
            PosConfig.restore_payment_driver(path)
        except Exception as e:
            logger.exception(f"恢复支付驱动失败: {e}")
            return {"ok": False, "message": str(e)}
        msg = "恢复支付驱动完成"
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": True, "message": msg}

    def cover_payment_driver(self, path: str) -> dict:
        self._push_status("覆盖支付驱动中...")
        try:
            ok, msg = PosConfig.cover_payment_driver(path)
        except Exception as e:
            logger.exception(f"覆盖支付驱动失败: {e}")
            return {"ok": False, "message": str(e)}
        text = msg or ("覆盖支付驱动成功" if ok else "覆盖支付驱动失败")
        self._push_status(text)
        self._push_log(text)
        return {"ok": bool(ok), "message": text}

    def clear_env(self, path: str) -> dict:
        self._push_status("清理环境文件中...")
        try:
            PosConfig.clear_env(path)
        except Exception as e:
            logger.exception(f"清理环境文件失败: {e}")
            return {"ok": False, "message": str(e)}
        msg = "清理当前环境文件完成"
        self._push_status(msg)
        self._push_log(msg)
        return {"ok": True, "message": msg}

    def replace_mitm_cert(self, path: str) -> dict:
        self._push_status("替换证书中...")
        try:
            ok, msg = PosConfig.replace_mitm_cert(path)
        except Exception as e:
            logger.exception(f"替换证书失败: {e}")
            return {"ok": False, "message": str(e)}
        text = msg or ("替换证书成功" if ok else "替换证书失败")
        self._push_status(text)
        self._push_log(text)
        return {"ok": bool(ok), "message": text}

    def open_location(self, path: str) -> dict:
        """
        打开 POS 文件所在目录。
        """
        ok = open_file_location(path)
        self._push_status("已打开文件所在目录" if ok else "打开文件所在目录失败")
        return {"ok": bool(ok)}

    def logout_pos(self, path: str) -> dict:
        """
        通过 POS 工具接口退出指定 POS 的账号。
        """
        with _TASK_LOCK:
            if self._logout_running:
                return {"ok": False, "message": "已有POS账号退出任务进行中，请稍候"}
            self._logout_running = True
        try:
            self._push_status("退出账号中...")
            logger.info(f"开始退出POS账号: {path}")
            PosConfigServer.logout_pos_account(path)
            msg = "POS账号已退出"
            logger.info(f"退出POS账号完成: {path}")
            self._push_status(msg)
            self._push_log(msg)
            return {"ok": True, "message": msg}
        except Exception as e:
            logger.warning(f"退出POS账号失败: {path}, error={e}")
            self._push_status(f"错误: {e}")
            return {"ok": False, "message": str(e)}
        finally:
            self._logout_running = False

    # ===== POS 账号处理弹窗 =====

    def get_account_defaults(self, pos_path: str) -> dict:
        """
        账号处理弹窗默认值：按本地参数推断环境分组与收银员账号。
        """
        try:
            pos_params = PosConfig.read_pos_params(pos_path, 1)
            pos_env = PosConfig.get_local_pos_env(pos_path)
            vendor_id = str(pos_params.venderNo or "") if pos_params else ""
            env_group, account = PosConfig.get_pos_group(vendor_id, pos_env)
            return {
                "ok": True,
                "env_group": env_group or "",
                "account": str(account or ""),
                "pos_env": pos_env or "",
            }
        except Exception as e:
            logger.warning(f"获取账号默认值失败: {e}")
            return {"ok": False, "message": str(e)}

    def logout_account(self, env: str, cashier_no: str) -> dict:
        """
        退出收银员账号（远端接口）。
        """
        from model.pos_network_model import PosLogoutModel
        from utils.pos_network import pos_account_logout

        if not env or not cashier_no:
            return {"ok": False, "message": "环境和收银员账号不能为空"}
        try:
            ok, msg = pos_account_logout(PosLogoutModel(env=env, cashierNo=cashier_no))
        except Exception as e:
            logger.exception(f"退出账号失败: {e}")
            return {"ok": False, "message": str(e)}
        return {"ok": bool(ok), "message": msg or ("退出账号成功" if ok else "退出账号失败")}

    def reset_account_password(self, env: str, cashier_no: str) -> dict:
        """
        重置收银员账号密码（远端接口）。
        """
        import asyncio

        from model.pos_network_model import PosResetAccountRequestModel
        from utils.pos_network import reset_account_password

        if not env or not cashier_no:
            return {"ok": False, "message": "环境和收银员账号不能为空"}
        try:
            ok, msg = asyncio.run(
                reset_account_password(PosResetAccountRequestModel(env=env, cashierNo=cashier_no))
            )
        except Exception as e:
            logger.exception(f"重置密码失败: {e}")
            return {"ok": False, "message": str(e)}
        return {"ok": bool(ok), "message": msg or ("重置密码成功" if ok else "重置密码失败")}

    # ===== POS 配置 =====

    def save_pos_config(self, data: dict) -> dict:
        """
        保存 POS 配置（设置弹窗）。
        """
        try:
            from model.config import PosConfigModel

            config = PosConfigModel.model_validate(data)
            PosConfig.save_pos_config(config)
            # 保存后立即刷新网络层 host 全局变量，避免必须重启应用才生效
            # （与「同步配置」路径 remote_config_server 的刷新行为对齐）
            from utils.pos_network import update_network_host

            update_network_host(config)
            return {"ok": True, "pos_config": PosConfig.read_pos_config().model_dump(), "message": "配置已保存"}
        except Exception as e:
            logger.exception(f"保存 POS 配置失败: {e}")
            return {"ok": False, "message": str(e)}

    def save_start_config(self, data: dict) -> dict:
        """
        保存启动配置（启动前自动动作勾选项）。
        """
        try:
            StartConfig.write(data)
            return {"ok": True}
        except Exception as e:
            logger.exception(f"保存启动配置失败: {e}")
            return {"ok": False, "message": str(e)}

    # ===== 进程管理 =====

    def list_processes(self, keyword: str = "") -> dict:
        """
        列出系统进程（可选按名称过滤），供进程管理弹窗展示。

        :param keyword: 进程名过滤关键字，空串返回全部
        """
        try:
            import psutil

            processes = []
            keyword_lower = str(keyword or "").strip().lower()
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    name = proc.info.get("name") or ""
                    if keyword_lower and keyword_lower not in name.lower():
                        continue
                    processes.append({"pid": proc.info["pid"], "name": name})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            processes.sort(key=lambda item: str(item["name"]).lower())
            return {"ok": True, "processes": processes}
        except Exception as e:
            logger.exception(f"列举进程失败: {e}")
            return {"ok": False, "message": str(e)}

    def kill_process(self, pid: int) -> dict:
        """
        结束指定 PID 的进程。
        """
        try:
            from services.process_service import ProcessService

            ProcessService.kill_by_pid(int(pid))
            msg = f"已结束进程 PID={pid}"
            self._push_log(msg)
            return {"ok": True, "message": msg}
        except Exception as e:
            logger.exception(f"结束进程失败 pid={pid}: {e}")
            return {"ok": False, "message": str(e)}

    # ===== 事件 =====

    def _push_status(self, message: str):
        event_bus.push("pos_status", {"message": str(message or "")})

    def _push_log(self, message: str):
        event_bus.push("pos_log", {"message": str(message or "")})
