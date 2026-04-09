from .model import MenuConfig, PermDef

_MENU_REGISTRY: dict[str, MenuConfig] = {}
_PERM_REGISTRY: dict[str, PermDef] = {}


def register_menu(menu: MenuConfig) -> MenuConfig:
    existing = _MENU_REGISTRY.get(menu.key)
    if existing:
        if existing != menu:
            raise RuntimeError(f"Duplicate menu key with different content: {menu.key}")
        return existing

    _MENU_REGISTRY[menu.key] = menu
    return menu


def register_perm(perm: PermDef) -> PermDef:
    existing = _PERM_REGISTRY.get(perm.perm)
    if existing:
        if existing != perm:
            raise RuntimeError(f"Duplicate permission with different content: {perm.perm}")
        return existing

    _PERM_REGISTRY[perm.perm] = perm
    return perm


def register_menu_class(cls: type) -> None:
    for name, value in vars(cls).items():
        if not isinstance(value, MenuConfig):
            continue
        if not name.isupper():
            raise RuntimeError(
                f"Menu constant {cls.__name__}.{name} must be UPPER_CASE"
            )
        register_menu(value)


def register_perm_class(cls: type) -> None:
    for name, value in vars(cls).items():
        if not isinstance(value, PermDef):
            continue
        if not name.isupper():
            raise RuntimeError(
                f"Permission constant {cls.__name__}.{name} must be UPPER_CASE"
            )
        register_perm(value)


def get_all_menus() -> dict[str, MenuConfig]:
    return dict(_MENU_REGISTRY)


def get_all_perms() -> dict[str, PermDef]:
    return dict(_PERM_REGISTRY)


def get_all_auth_perm_codes() -> set[str]:
    codes = {menu.perm for menu in _MENU_REGISTRY.values() if menu.perm}
    codes.update(_PERM_REGISTRY.keys())
    return codes
