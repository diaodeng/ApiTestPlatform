class PosStartContext:
    def __init__(self, path):
        self.path = path

        self.local_env = None
        self.local_params = None
        self.remote_params = None

        self.need_change_pos = False
        self.need_logout = False
        self.need_replace_cert = False
        self.need_backup = False
        self.need_cover_driver = False
        self.need_clean_cache = False

        self.abort = False
