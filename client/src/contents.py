class Contents:
    def __init__(self, ft, log, page, **kwargs):
        self.ft = ft
        self.log = log
        self.page = page
        self.kwargs = kwargs
        self._content_cache = {}
        self._content_builders = [
            self._build_settings,
            self._build_goods,
            self._build_agent,
            self._build_pos,
            self._build_mitmproxy,
            self._build_ftp,
            self._build_log_view,
            self._build_about,
        ]

    def _build_settings(self):
        from view_contents.content_settings import Settings

        return Settings(self.ft, self.page, self.log).settings()

    def _build_goods(self):
        from view_contents.content_goods import Goods

        return Goods(self.ft, self.page, self.log, **self.kwargs).goods()

    def _build_agent(self):
        from view_contents.content_agent import AgentHandler

        return AgentHandler(self.ft, self.page).init_ui()

    def _build_pos(self):
        from view_contents.content_pos_handler import PosHandler

        return PosHandler(self.ft, self.page).init_ui()

    def _build_mitmproxy(self):
        from view_contents.content_mitmproxy import MitmHandel

        return MitmHandel(self.page).init()

    def _build_ftp(self):
        from view_contents.content_ftp import FtpHandler

        return FtpHandler(self.page).init_ui()

    def _build_log_view(self):
        from view_contents.content_log_view import LogViewerApp

        return LogViewerApp(self.page).init_ui()

    def _build_about(self):
        from view_contents.content_about import About

        return About().about()

    # 内容区域函数
    def get_content(self, index):
        if index < 0 or index >= len(self._content_builders):
            raise IndexError(f"invalid content index: {index}")
        if index not in self._content_cache:
            self._content_cache[index] = self._content_builders[index]()
        return self._content_cache[index]
