from fastapi import FastAPI
from fastapi.routing import APIRoute

from .auth_check import CheckUserInterfaceAuth
from .model import MenuConfig, PermDef


def _normalize_perm(permission) -> str | None:
    if isinstance(permission, (MenuConfig, PermDef)):
        return permission.perm
    if isinstance(permission, str):
        return permission
    return None


def scan_fastapi_permissions(app: FastAPI) -> dict[str, dict[str, list[str]]]:
    perms_map: dict[str, dict[str, set[str]]] = {}

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        for dependency in route.dependencies:
            call = dependency.dependency
            if not isinstance(call, CheckUserInterfaceAuth):
                continue

            permissions = call.perm if isinstance(call.perm, list) else [call.perm]
            for permission in permissions:
                perm_code = _normalize_perm(permission)
                if not perm_code:
                    continue

                info = perms_map.setdefault(
                    perm_code,
                    {"paths": set(), "methods": set()},
                )
                info["paths"].add(route.path)
                info["methods"].update(route.methods or [])

    return {
        perm: {
            "paths": sorted(info["paths"]),
            "methods": sorted(info["methods"]),
        }
        for perm, info in perms_map.items()
    }
