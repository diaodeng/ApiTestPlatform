from typing import Union

from fastapi import Depends

from common.permission.model import MenuConfig, PermDef
from exceptions.exception import PermissionException
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService

PermissionType = Union[str, PermDef, MenuConfig]
PermissionListType = list[PermissionType]


def _resolve_perm_code(permission: PermissionType) -> str:
    if isinstance(permission, (PermDef, MenuConfig)):
        return permission.perm
    return permission


class CheckUserInterfaceAuth:
    """
    校验当前用户是否具有相应的接口权限
    :param perm: 权限标识
    :param is_strict: 当传入的权限标识是 list 类型时，是否开启严格模式
    """

    def __init__(
        self,
        perm: Union[PermissionType, PermissionListType],
        is_strict: bool = False,
    ):
        self.perm = perm
        self.is_strict = is_strict

    def __call__(
        self,
        current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    ):
        user_auth = set(current_user.permissions)

        if "*:*:*" in user_auth:
            return True

        if isinstance(self.perm, list):
            checker = all if self.is_strict else any
            ok = checker(
                _resolve_perm_code(permission) in user_auth for permission in self.perm
            )
        else:
            ok = _resolve_perm_code(self.perm) in user_auth

        if ok:
            return True

        raise PermissionException(data="", message="该用户无此接口权限")


class CheckRoleInterfaceAuth:
    """
    根据角色校验当前用户是否具有相应的接口权限
    :param role_key: 角色标识
    :param is_strict: 当传入的角色标识是 list 类型时，是否开启严格模式
    """

    def __init__(self, role_key: Union[str, list[str]], is_strict: bool = False):
        self.role_key = role_key
        self.is_strict = is_strict

    def __call__(
        self,
        current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    ):
        user_role_key_list = {role.role_key for role in current_user.user.role}

        if isinstance(self.role_key, str):
            if self.role_key in user_role_key_list:
                return True
        else:
            role_key_match = [
                role_key in user_role_key_list for role_key in self.role_key
            ]
            if self.is_strict and all(role_key_match):
                return True
            if not self.is_strict and any(role_key_match):
                return True

        raise PermissionException(data="", message="该用户无此接口权限")
