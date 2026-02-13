from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func, or_

from config.get_db import get_db
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.role_do import SysRoleDept
from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService


class GetDataScope:
    """
    FastAPI 数据权限依赖
    返回 SQLAlchemy filter 表达式（而不是字符串）
    """

    def __init__(
        self,
        model: type,
        *,
        user_alias: str = "user_id",
        dept_alias: str = "dept_id",
    ) -> None:
        self.model = model
        self.user_field = user_alias
        self.dept_field = dept_alias

    def __call__(
        self,
        db: Session = Depends(get_db),
        current_user=Depends(LoginService.get_current_user),
    ) -> DataScopeExpr:
        user = current_user.user
        user_id = user.user_id
        dept_id = user.dept_id

        # 取权限最小值（权限最大）
        min_role = min(
            user.role,
            key=lambda r: int(r.data_scope),
            default=None,
        )

        # 无角色 or 超级管理员 or 全数据权限
        if min_role is None or user_id == 1 or int(min_role.data_scope) == 1:
            return True

        scope = int(min_role.data_scope)
        model = self.model

        # 防止字段不存在导致 AttributeError
        has_dept = hasattr(model, self.dept_field)
        has_user = hasattr(model, self.user_field)

        # 2：自定义部门
        if scope == 2 and has_dept:
            return getattr(model, self.dept_field).in_(
                db.query(SysRoleDept.dept_id).filter(
                    SysRoleDept.role_id == min_role.role_id
                )
            )

        # 3：本部门
        if scope == 3 and has_dept:
            return getattr(model, self.dept_field) == dept_id

        # 4：本部门及子部门
        if scope == 4 and has_dept:
            return getattr(model, self.dept_field).in_(
                db.query(SysDept.dept_id).filter(
                    or_(
                        SysDept.dept_id == dept_id,
                        func.find_in_set(dept_id, SysDept.ancestors),
                    )
                )
            )

        # 5：仅本人
        if scope == 5 and has_user:
            return getattr(model, self.user_field) == user_id

        # 兜底：无数据权限
        return False


class GetDataScopeBack:
    """
    获取当前用户数据权限对应的查询sql语句
    """

    def __init__(
        self,
        query_alias: str | None = "",
        db_alias: str | None = "db",
        user_alias: str | None = "user_id",
        dept_alias: str | None = "dept_id",
    ):
        self.query_alias = query_alias
        self.db_alias = db_alias
        self.user_alias = user_alias
        self.dept_alias = dept_alias

    def __call__(self, current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
        user_id = current_user.user.user_id
        dept_id = current_user.user.dept_id
        role_datascope_list = [
            {"role_id": item.role_id, "data_scope": int(item.data_scope)} for item in current_user.user.role
        ]
        max_data_scope_dict = min(role_datascope_list, key=lambda x: x["data_scope"])
        max_role_id = max_data_scope_dict["role_id"]
        max_data_scope = max_data_scope_dict["data_scope"]
        if self.query_alias == "" or max_data_scope == 1 or user_id == 1:
            param_sql = "1 == 1"
        elif max_data_scope == 2:
            param_sql = f"{self.query_alias}.{self.dept_alias}.in_({self.db_alias}.query(SysRoleDept.dept_id).filter(SysRoleDept.role_id == {max_role_id})) if hasattr({self.query_alias}, '{self.dept_alias}') else 1 == 1"
        elif max_data_scope == 3:
            param_sql = f"{self.query_alias}.{self.dept_alias} == {dept_id} if hasattr({self.query_alias}, '{self.dept_alias}') else 1 == 1"
        elif max_data_scope == 4:
            param_sql = f"{self.query_alias}.{self.dept_alias}.in_({self.db_alias}.query(SysDept.dept_id).filter(or_(SysDept.dept_id == {dept_id}, func.find_in_set({dept_id}, SysDept.ancestors)))) if hasattr({self.query_alias}, '{self.dept_alias}') else 1 == 1"
        elif max_data_scope == 5:
            param_sql = f"{self.query_alias}.{self.user_alias} == {user_id} if hasattr({self.query_alias}, '{self.user_alias}') else 1 == 1"
        else:
            param_sql = "1 == 0"

        return param_sql
