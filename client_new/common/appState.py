class _UserInfo:
    username: str = None
    nickname: str = None


class ClientInfo:
    current_pos: str | None = None
    toolbar_info: str | None = None
    tool_pos_config: str | None = None


userInfo = _UserInfo()
client_info = ClientInfo()
