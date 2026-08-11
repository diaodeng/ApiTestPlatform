import json
from datetime import datetime

from sqlalchemy.orm import Session

from common.permission.registry import get_all_menus
from config.database import SessionLocal
from module_admin.dao.api_key_dao import ApiKeyDao
from module_admin.dao.user_dao import UserDao
from module_admin.entity.vo.api_key_vo import (
    ApiKeyModel,
    ApiKeyPageQueryModel,
    ApiKeyPermissionOptionModel,
    ApiKeySecretModel,
    CreateApiKeyModel,
    ViewApiKeyModel,
)
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from utils.api_key_util import ApiKeyUtil
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.pwd_util import PwdUtil


class ApiKeyService:
    """
    API Key管理模块服务层
    """

    @classmethod
    def get_api_key_list_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        query_object: ApiKeyPageQueryModel,
    ) -> PageResponseModel:
        """
        获取当前登录用户的API Key分页列表
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param query_object: API Key分页查询对象
        :return: API Key分页响应对象
        """
        query_result = ApiKeyDao.get_api_key_list(query_db, current_user.user.user_id, query_object)
        rows = [cls.build_api_key_model(api_key).model_dump(by_alias=True) for api_key in query_result["rows"]]
        return PageResponseModel(
            rows=rows,
            page_num=query_result["page_num"],
            page_size=query_result["page_size"],
            total=query_result["total"],
            has_next=query_result["has_next"],
        )

    @classmethod
    def get_api_key_detail_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        api_key_id: int,
    ) -> ApiKeyModel | None:
        """
        获取当前登录用户指定API Key的详情
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param api_key_id: API Key主键
        :return: API Key详情模型，不存在时返回None
        """
        api_key_info = ApiKeyDao.get_api_key_by_id(query_db, api_key_id, current_user.user.user_id)
        if not api_key_info:
            return None
        return cls.build_api_key_model(api_key_info)

    @classmethod
    def get_api_key_permission_options_services(
        cls,
        current_user: CurrentUserModel,
    ) -> list[ApiKeyPermissionOptionModel]:
        """
        获取当前登录用户可分配给API Key的权限选项
        :param current_user: 当前登录用户对象
        :return: 当前用户可授权的权限选项列表
        """
        menus = get_all_menus()
        assignable_codes = cls.get_assignable_permission_codes(current_user)
        options: dict[str, ApiKeyPermissionOptionModel] = {}

        for menu in menus.values():
            if not menu.perm or menu.perm not in assignable_codes:
                continue
            parent_name = menus.get(menu.parent_key).name if menu.parent_key and menus.get(menu.parent_key) else None
            option = ApiKeyPermissionOptionModel(
                perm=menu.perm,
                name=menu.name,
                menuType=menu.menu_type,
                parentName=parent_name,
            )
            existing = options.get(menu.perm)
            if existing is None or (existing.menu_type == "M" and menu.menu_type != "M"):
                options[menu.perm] = option

        for perm_code in assignable_codes:
            if perm_code not in options:
                options[perm_code] = ApiKeyPermissionOptionModel(perm=perm_code, name=perm_code)

        return sorted(options.values(), key=lambda item: (item.parent_name or "", item.name, item.perm))

    @classmethod
    def add_api_key_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        page_object: CreateApiKeyModel,
    ) -> CrudResponseModel:
        """
        新增当前登录用户的API Key
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param page_object: 新增API Key请求对象
        :return: 新增结果，成功时result中返回API Key明文
        """
        normalized_key_name = (page_object.key_name or "").strip()
        if not normalized_key_name:
            return CrudResponseModel(is_success=False, message="API Key名称不能为空")

        permission_result = cls.validate_permission_codes(current_user, page_object.permission_codes)
        if not permission_result["is_success"]:
            return CrudResponseModel(is_success=False, message=permission_result["message"])

        expire_result = cls.validate_expire_time(page_object)
        if not expire_result["is_success"]:
            return CrudResponseModel(is_success=False, message=expire_result["message"])

        key_code, raw_api_key = ApiKeyUtil.generate_api_key()
        now = datetime.now()
        try:
            db_api_key = ApiKeyDao.add_api_key_dao(
                query_db,
                {
                    "user_id": current_user.user.user_id,
                    "key_name": normalized_key_name,
                    "key_code": key_code,
                    "key_prefix": ApiKeyUtil.mask_api_key(raw_api_key),
                    "key_hash": ApiKeyUtil.get_api_key_hash(raw_api_key),
                    "key_cipher_text": ApiKeyUtil.encrypt_api_key(raw_api_key),
                    "permission_codes": json.dumps(permission_result["permission_codes"], ensure_ascii=False),
                    "expire_time": expire_result["expire_time"],
                    "never_expire": "1" if page_object.never_expire else "0",
                    "status": "0",
                    "create_by": current_user.user.user_name,
                    "create_time": now,
                    "update_by": current_user.user.user_name,
                    "update_time": now,
                    "remark": page_object.remark,
                },
            )
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="新增成功",
                result=ApiKeySecretModel(
                    apiKeyId=db_api_key.api_key_id,
                    keyName=db_api_key.key_name,
                    apiKey=raw_api_key,
                ),
            )
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def view_api_key_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        api_key_id: int,
        page_object: ViewApiKeyModel,
    ) -> CrudResponseModel:
        """
        校验当前账号密码后查看指定API Key明文
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param api_key_id: API Key主键
        :param page_object: 查看API Key请求对象
        :return: 查看结果，成功时result中返回API Key明文
        """
        api_key_info = ApiKeyDao.get_api_key_by_id(query_db, api_key_id, current_user.user.user_id)
        if not api_key_info:
            return CrudResponseModel(is_success=False, message="API Key不存在")

        if (page_object.user_name or "").strip() != current_user.user.user_name:
            return CrudResponseModel(is_success=False, message="账号校验失败")

        user_info = UserDao.get_user_by_id(query_db, current_user.user.user_id).get("user_basic_info")
        if not user_info or not PwdUtil.verify_password(page_object.password, user_info.password):
            return CrudResponseModel(is_success=False, message="账号或密码不正确")

        try:
            raw_api_key = ApiKeyUtil.decrypt_api_key(api_key_info.key_cipher_text)
        except ValueError:
            return CrudResponseModel(is_success=False, message="API Key解密失败，请重新创建")

        return CrudResponseModel(
            is_success=True,
            message="查看成功",
            result=ApiKeySecretModel(
                apiKeyId=api_key_info.api_key_id,
                keyName=api_key_info.key_name,
                apiKey=raw_api_key,
            ),
        )

    @classmethod
    def expire_api_key_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        api_key_id: int,
    ) -> CrudResponseModel:
        """
        手动过期当前登录用户指定的API Key
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param api_key_id: API Key主键
        :return: 手动过期操作结果
        """
        api_key_info = ApiKeyDao.get_api_key_by_id(query_db, api_key_id, current_user.user.user_id)
        if not api_key_info:
            return CrudResponseModel(is_success=False, message="API Key不存在")

        is_expired, _ = cls.get_api_key_expire_state(api_key_info)
        if is_expired:
            return CrudResponseModel(is_success=False, message="API Key已失效")

        try:
            ApiKeyDao.edit_api_key_dao(
                query_db,
                api_key_id,
                {
                    "status": "1",
                    "update_by": current_user.user.user_name,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="操作成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def delete_api_key_services(
        cls,
        query_db: Session,
        current_user: CurrentUserModel,
        api_key_id: int,
    ) -> CrudResponseModel:
        """
        删除当前登录用户指定的API Key
        :param query_db: orm对象
        :param current_user: 当前登录用户对象
        :param api_key_id: API Key主键
        :return: 删除操作结果
        """
        api_key_info = ApiKeyDao.get_api_key_by_id(query_db, api_key_id, current_user.user.user_id)
        if not api_key_info:
            return CrudResponseModel(is_success=False, message="API Key不存在")

        try:
            ApiKeyDao.delete_api_key_dao(
                query_db,
                api_key_id,
                {
                    "update_by": current_user.user.user_name,
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception as exc:
            query_db.rollback()
            raise exc

    @classmethod
    def authenticate_api_key_services(
        cls,
        query_db: Session,
        api_key: str,
        request_ip: str | None = None,
    ):
        """
        校验API Key并返回数据库对象
        :param query_db: orm对象
        :param api_key: 请求头传入的API Key明文
        :param request_ip: 当前请求IP
        :return: 校验通过后的API Key数据库对象
        :raise AuthException: 当API Key不存在、不合法或已过期时抛出
        """
        from exceptions.exception import AuthException

        try:
            key_code = ApiKeyUtil.extract_key_code(api_key)
        except ValueError as exc:
            raise AuthException(data="", message="API Key不合法") from exc

        api_key_info = ApiKeyDao.get_api_key_by_key_code(query_db, key_code)
        if not api_key_info or not ApiKeyUtil.verify_api_key(api_key, api_key_info.key_hash):
            raise AuthException(data="", message="API Key不合法")

        is_expired, expire_reason = cls.get_api_key_expire_state(api_key_info)
        if is_expired:
            error_message = "API Key已失效" if expire_reason == "manual" else "API Key已过期"
            raise AuthException(data="", message=error_message)

        cls.update_api_key_usage_audit(api_key_info.api_key_id, request_ip)
        return api_key_info

    @classmethod
    def update_api_key_usage_audit(cls, api_key_id: int, request_ip: str | None = None) -> None:
        """
        更新API Key最后使用审计信息，失败时只记录日志，不影响鉴权和业务接口。
        :param api_key_id: API Key主键
        :param request_ip: 当前请求IP
        :return: 无
        """
        audit_db = SessionLocal()
        try:
            ApiKeyDao.edit_api_key_dao(
                audit_db,
                api_key_id,
                {
                    "last_used_ip": request_ip or "",
                    "last_used_time": datetime.now(),
                },
            )
            audit_db.commit()
        except Exception as exc:
            audit_db.rollback()
            logger.warning(f"API Key最后使用审计更新失败，已忽略: api_key_id={api_key_id}, error={exc}")
        finally:
            audit_db.close()

    @classmethod
    def build_api_key_model(cls, api_key_info) -> ApiKeyModel:
        """
        将API Key数据库对象转换为前端可直接使用的响应模型
        :param api_key_info: API Key数据库对象
        :return: API Key响应模型
        """
        is_expired, expire_reason = cls.get_api_key_expire_state(api_key_info)
        expire_reason_text = None
        if expire_reason == "manual":
            expire_reason_text = "手动过期"
        elif expire_reason == "time":
            expire_reason_text = "到期失效"

        return ApiKeyModel(
            apiKeyId=api_key_info.api_key_id,
            userId=api_key_info.user_id,
            keyName=api_key_info.key_name,
            keyCode=api_key_info.key_code,
            keyPrefix=api_key_info.key_prefix,
            permissionCodes=cls.parse_permission_codes(api_key_info.permission_codes),
            expireTime=api_key_info.expire_time,
            neverExpire=api_key_info.never_expire == "1",
            status=api_key_info.status,
            lastUsedIp=api_key_info.last_used_ip,
            lastUsedTime=api_key_info.last_used_time,
            createBy=api_key_info.create_by,
            createTime=api_key_info.create_time,
            updateBy=api_key_info.update_by,
            updateTime=api_key_info.update_time,
            remark=api_key_info.remark,
            isExpired=is_expired,
            expireReason=expire_reason_text,
        )

    @classmethod
    def parse_permission_codes(cls, permission_codes: str | list[str] | None) -> list[str]:
        """
        解析API Key权限数据，统一转换为字符串列表
        :param permission_codes: 数据库存储的JSON字符串或权限列表
        :return: 解析后的权限代码列表
        """
        if permission_codes is None:
            return []
        if isinstance(permission_codes, list):
            return [str(item) for item in permission_codes if str(item).strip()]

        try:
            parsed_result = json.loads(permission_codes)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed_result, list):
            return []
        return [str(item) for item in parsed_result if str(item).strip()]

    @classmethod
    def get_effective_permission_codes(
        cls,
        user_permissions: list[str],
        api_key_permissions: list[str],
    ) -> list[str]:
        """
        计算API Key请求最终可用的权限列表
        :param user_permissions: 登录账号当前拥有的权限列表
        :param api_key_permissions: API Key创建时配置的权限列表
        :return: 账号权限与API Key权限收敛后的最终权限列表
        """
        normalized_api_key_permissions = list(dict.fromkeys([perm for perm in api_key_permissions if perm]))
        if "*:*:*" in user_permissions:
            return normalized_api_key_permissions

        user_permission_set = set(user_permissions)
        return [perm for perm in normalized_api_key_permissions if perm in user_permission_set]

    @classmethod
    def get_assignable_permission_codes(cls, current_user: CurrentUserModel) -> list[str]:
        """
        获取当前登录用户允许分配给API Key的权限代码列表
        :param current_user: 当前登录用户对象
        :return: 当前用户可授权的权限代码列表
        """
        if "*:*:*" in current_user.permissions:
            return sorted({menu.perm for menu in get_all_menus().values() if menu.perm})
        return list(dict.fromkeys([perm for perm in current_user.permissions if perm and perm != "*:*:*"]))

    @classmethod
    def validate_permission_codes(cls, current_user: CurrentUserModel, permission_codes: list[str]) -> dict:
        """
        校验新增API Key时传入的权限列表是否合法
        :param current_user: 当前登录用户对象
        :param permission_codes: 请求中传入的权限列表
        :return: 校验结果字典，包含is_success、message和permission_codes
        """
        assignable_codes = cls.get_assignable_permission_codes(current_user)
        if not assignable_codes:
            return {"is_success": False, "message": "当前账号暂无可授权的接口权限", "permission_codes": []}

        normalized_codes = [
            str(perm).strip()
            for perm in permission_codes
            if str(perm).strip() and str(perm).strip() != "*:*:*"
        ]
        normalized_codes = list(dict.fromkeys(normalized_codes))
        if not normalized_codes:
            return {"is_success": True, "message": "校验通过", "permission_codes": assignable_codes}

        invalid_codes = [perm for perm in normalized_codes if perm not in set(assignable_codes)]
        if invalid_codes:
            return {
                "is_success": False,
                "message": f"以下权限不可授权：{', '.join(invalid_codes)}",
                "permission_codes": [],
            }

        return {"is_success": True, "message": "校验通过", "permission_codes": normalized_codes}

    @classmethod
    def validate_expire_time(cls, page_object: CreateApiKeyModel) -> dict:
        """
        校验新增API Key时的有效期配置是否合法
        :param page_object: 新增API Key请求对象
        :return: 校验结果字典，包含is_success、message和expire_time
        """
        if page_object.never_expire:
            return {"is_success": True, "message": "校验通过", "expire_time": None}

        if not page_object.expire_time:
            return {"is_success": False, "message": "请设置API Key有效期", "expire_time": None}

        if page_object.expire_time <= datetime.now():
            return {"is_success": False, "message": "API Key有效期必须晚于当前时间", "expire_time": None}

        return {"is_success": True, "message": "校验通过", "expire_time": page_object.expire_time}

    @classmethod
    def get_api_key_expire_state(cls, api_key_info) -> tuple[bool, str | None]:
        """
        计算API Key当前是否已经失效以及失效原因
        :param api_key_info: API Key数据库对象
        :return: (是否失效, 失效原因) 元组，原因取值为manual、time或None
        """
        if api_key_info.status == "1":
            return True, "manual"
        if api_key_info.never_expire != "1" and api_key_info.expire_time and api_key_info.expire_time <= datetime.now():
            return True, "time"
        return False, None
