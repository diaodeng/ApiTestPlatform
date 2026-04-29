from datetime import datetime

from fastapi import FastAPI
from loguru import logger

from config.database import SessionLocal
from module_admin.entity.do.menu_do import SysMenu

from .model import MenuConfig
from .registry import get_all_auth_perm_codes, get_all_menus
from .route_scanner import scan_fastapi_permissions

_MARKER_PREFIX = "__perm_sync__="
_SYNC_USER = "permission_sync"


def _marker(key: str) -> str:
    return f"{_MARKER_PREFIX}{key}"


def _extract_markers(remark: str | None) -> set[str]:
    markers: set[str] = set()
    for segment in (remark or "").split("|"):
        segment = segment.strip()
        if segment.startswith(_MARKER_PREFIX):
            markers.add(segment[len(_MARKER_PREFIX) :])
    return markers


def _has_marker(remark: str | None, key: str) -> bool:
    return key in _extract_markers(remark)


def _append_marker(base_text: str | None, key: str) -> str:
    base = (base_text or "").strip()
    marker = _marker(key)
    if _has_marker(base, key):
        return base
    if not base:
        return marker
    return f"{base} | {marker}"


def _merge_remark(existing_remark: str | None, configured_remark: str, key: str) -> str:
    existing = (existing_remark or "").strip()
    configured = (configured_remark or "").strip()

    if configured and configured in existing:
        return _append_marker(existing, key)
    if configured and not existing:
        return _append_marker(configured, key)
    if configured and existing:
        return _append_marker(f"{configured} | {existing}", key)
    return _append_marker(existing, key)


def _normalize_component(value: str) -> str | None:
    return value or None


def _normalize_query(value: str) -> str | None:
    return value or None


def _sync_menu_fields(row: SysMenu, menu: MenuConfig, parent_id: int) -> None:
    row.menu_name = menu.name
    row.parent_id = parent_id
    row.order_num = menu.order
    row.path = menu.path
    row.component = _normalize_component(menu.component)
    row.query = _normalize_query(menu.query)
    row.is_frame = menu.is_frame
    row.is_cache = menu.is_cache
    row.menu_type = menu.menu_type
    row.visible = menu.visible
    row.status = menu.status
    row.perms = menu.perm or None
    row.icon = menu.icon or "#"
    row.update_by = _SYNC_USER
    row.update_time = datetime.now()
    row.remark = _merge_remark(row.remark, menu.remark, menu.key)


def _create_menu_row(menu: MenuConfig, parent_id: int) -> SysMenu:
    now = datetime.now()
    return SysMenu(
        menu_name=menu.name,
        parent_id=parent_id,
        order_num=menu.order,
        path=menu.path,
        component=_normalize_component(menu.component),
        query=_normalize_query(menu.query),
        is_frame=menu.is_frame,
        is_cache=menu.is_cache,
        menu_type=menu.menu_type,
        visible=menu.visible,
        status=menu.status,
        perms=menu.perm or None,
        icon=menu.icon or "#",
        create_by=_SYNC_USER,
        create_time=now,
        update_by=_SYNC_USER,
        update_time=now,
        remark=_merge_remark("", menu.remark, menu.key),
    )


def _find_existing_menu(
    rows: list[SysMenu],
    menu: MenuConfig,
    parent_id: int,
) -> SysMenu | None:
    for row in rows:
        if _has_marker(row.remark, menu.key):
            return row

    candidates = [
        row
        for row in rows
        if row.menu_type == menu.menu_type and row.parent_id == parent_id
    ]

    if menu.component:
        for row in candidates:
            if (row.component or "") == menu.component:
                return row

    if menu.perm:
        for row in candidates:
            if (row.perms or "") == menu.perm and row.menu_name == menu.name:
                return row
        if menu.menu_type != "F":
            for row in candidates:
                if (row.perms or "") == menu.perm and (row.path or "") == menu.path:
                    return row

    if menu.path:
        for row in candidates:
            if (row.path or "") == menu.path and row.menu_name == menu.name:
                return row
        for row in candidates:
            if (row.path or "") == menu.path:
                return row

    for row in candidates:
        if row.menu_name == menu.name:
            return row

    return None


def _menu_depth(key: str, menus: dict[str, MenuConfig], cache: dict[str, int]) -> int:
    if key in cache:
        return cache[key]

    menu = menus[key]
    if not menu.parent_key:
        cache[key] = 0
        return 0

    if menu.parent_key not in menus:
        raise RuntimeError(f"Parent menu key not found: {menu.parent_key}")

    depth = _menu_depth(menu.parent_key, menus, cache) + 1
    cache[key] = depth
    return depth


def _sort_menus(menus: dict[str, MenuConfig]) -> list[MenuConfig]:
    depth_cache: dict[str, int] = {}
    return sorted(
        menus.values(),
        key=lambda menu: (
            _menu_depth(menu.key, menus, depth_cache),
            menu.order,
            menu.key,
        ),
    )


def check_menu(app: FastAPI) -> set[str]:
    route_perms = set(scan_fastapi_permissions(app).keys())
    defined_perms = get_all_auth_perm_codes()
    missing = sorted(route_perms - defined_perms)

    if missing:
        logger.warning(f"[PERM-CHECK] Route perms not defined: {missing}")
    else:
        logger.info(f"[PERM-CHECK] Route permission scan passed, total={len(route_perms)}")

    return route_perms


def sync_registered_menus(app: FastAPI) -> None:
    check_menu(app)
    menus = get_all_menus()
    if not menus:
        logger.info("[PERM-SYNC] No menu definitions registered, skip sync")
        return

    with SessionLocal() as db:
        rows = db.query(SysMenu).all()
        managed_rows: dict[str, SysMenu] = {}

        for menu in _sort_menus(menus):
            parent_id = 0
            if menu.parent_key:
                parent_row = managed_rows.get(menu.parent_key)
                if not parent_row:
                    raise RuntimeError(
                        f"Parent menu not resolved before child: {menu.key} -> {menu.parent_key}"
                    )
                parent_id = parent_row.menu_id

            row = _find_existing_menu(rows, menu, parent_id)
            if row is None:
                row = _create_menu_row(menu, parent_id)
                db.add(row)
                db.flush()
                rows.append(row)
            else:
                _sync_menu_fields(row, menu, parent_id)

            managed_rows[menu.key] = row

        db.commit()
        logger.info(f"[PERM-SYNC] Synced menus successfully, total={len(menus)}")
