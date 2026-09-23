# context.py


class PosStartContext:
    def __init__(self, path, start_config):
        self.path = path
        self.start_config = start_config

        self.local_env_info: str | None = None
        # self.is_uat: bool = False

        self.local_pos_params = None
        self.remote_pos_params = None

        self.has_local = False
        self.has_remote = False

        self.remote_info = ""

        self.need_switch = False
        # 启动前检查时是否真的杀掉了运行中的 POS 进程（用于取消启动时向用户说明）
        self.killed_running = False
        # 缺本地 pos_params 且用户确认后，跳过依赖本地参数的启动动作（切换云端POS/退出登录）
        self.skip_dependent_actions = False

    @property
    def is_uat(self):
        return self.local_env_info and (
            "rta_uat" in self.local_env_info.lower()
            or "kh_test_s" in self.local_env_info.lower()
        )

    def is_mismatch(self):
        fields = ("orgNo", "posGroupNo", "posId", "posType", "sapOrgNo", "venderNo")
        all_same = all(
            getattr(self.local_pos_params, f, None)
            == getattr(self.remote_pos_params, f, None)
            for f in fields
        )
        return not all_same
