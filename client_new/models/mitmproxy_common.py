from dataclasses import dataclass
from datetime import datetime


@dataclass
class FlowItem:
    id: str
    method: str
    url: str
    path: str
    status_code: int | None
    size: int
    time: datetime
    request_scheme: str = ""
    request_host: str = ""
    request_port: int | None = None
    request_http_version: str = ""
    request_query: str = ""
    request_headers: str = ""
    request_cookies: str = ""
    request_form: str = ""
    request_body: str = ""
    request_content_type: str = ""
    client_address: str = ""
    server_address: str = ""
    response_reason: str = ""
    response_http_version: str = ""
    response_headers: str = ""
    response_body: str = ""
    response_content_type: str = ""
    duration_ms: int | None = None
    breakpoint_matched: bool = False
    breakpoint_stage: str = ""
    breakpoint_paused: bool = False
    breakpoint_status_text: str = ""
