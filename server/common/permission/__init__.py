from .auth_check import CheckRoleInterfaceAuth, CheckUserInterfaceAuth
from .model import MenuConfig, PermDef
from .registry import (
    get_all_auth_perm_codes,
    get_all_menus,
    get_all_perms,
    register_menu,
    register_perm,
)

__all__ = [
    "CheckRoleInterfaceAuth",
    "CheckUserInterfaceAuth",
    "MenuConfig",
    "PermDef",
    "get_all_auth_perm_codes",
    "get_all_menus",
    "get_all_perms",
    "register_menu",
    "register_perm",
]
