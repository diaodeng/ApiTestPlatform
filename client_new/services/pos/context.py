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
