from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PermDef:
    perm: str
    name: str


@dataclass(frozen=True)
class MenuConfig:
    key: str
    name: str
    menu_type: Literal["M", "C", "F"]
    parent_key: str | None = None
    perm: str = ""
    path: str = ""
    component: str = ""
    query: str = ""
    icon: str = "#"
    order: int = 1
    is_frame: int = 1
    is_cache: int = 0
    visible: str = "0"
    status: str = "0"
    remark: str = ""
