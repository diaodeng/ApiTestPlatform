import random
import uuid
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import Depends, Form, Header, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config.env import AppConfig, JwtConfig, RedisInitKeyConfig
from config.get_db import get_db
from exceptions.exception import AuthException, LoginException
from module_admin.service.api_key_service import ApiKeyService
from module_admin.dao.dept_dao import DeptDao
from module_admin.dao.login_dao import login_by_account
from module_admin.dao.post_dao import PostDao
from module_admin.dao.role_dao import RoleDao
from module_admin.dao.user_dao import UserDao
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.login_vo import SmsCode, UserLogin, UserRegister
from module_admin.entity.vo.user_vo import AddUserModel, CurrentUserModel, ResetUserModel, TokenData, UserInfoModel
from module_admin.service.user_service import UserService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.message_util import message_service
from utils.pwd_util import PwdUtil

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_authorization_header(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    """
    提取请求头中的Authorization信息
    :param authorization: 请求头中的Authorization原始值
    :return: Authorization原始值，不存在时返回None
    """
    return authorization


class CustomOAuth2PasswordRequestForm(OAuth2PasswordRequestForm):
    """
    自定义OAuth2PasswordRequestForm类，增加验证码及会话编号参数
    """

    def __init__(
            self,
            grant_type: str = Form(default=None, regex="password"),
            username: str = Form(),
            password: str = Form(),
            scope: str = Form(default=""),
            client_id: Optional[str] = Form(default=None),
            client_secret: Optional[str] = Form(default=None),
            code: Optional[str] = Form(default=""),
            uuid: Optional[str] = Form(default=""),
            login_info: Optional[dict[str, str]] = Form(default=None)
    ):
        super().__init__(grant_type=grant_type, username=username, password=password,
                         scope=scope, client_id=client_id, client_secret=client_secret)
        self.code = code
        self.uuid = uuid
        self.login_info = login_info


class LoginService:
    """
    登录模块服务层
    """
    REGISTER_DEFAULT_DEPT_ID_KEY = "sys.account.registerDefaultDeptId"
    REGISTER_DEFAULT_ROLE_IDS_KEY = "sys.account.registerDefaultRoleIds"
    REGISTER_DEFAULT_POST_IDS_KEY = "sys.account.registerDefaultPostIds"

    @classmethod
    async def __get_sys_config_value(cls, request: Request, config_key: str) -> Optional[str]:
        """
        获取系统参数缓存值
        :param request: Request对象
        :param config_key: 参数键名
        :return: 参数值字符串，不存在时返回None
        """
        config_value = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SYS_CONFIG.get('key')}:{config_key}"
        )
        if config_value is None:
            return None
        if isinstance(config_value, bytes):
            return config_value.decode("utf-8")
        return str(config_value)

    @classmethod
    def __parse_positive_int(cls, raw_value: Optional[str], config_key: str) -> Optional[int]:
        """
        解析正整数参数值
        :param raw_value: 参数原始值
        :param config_key: 参数键名
        :return: 正整数结果，解析失败返回None
        """
        if raw_value is None:
            return None
        value = raw_value.strip()
        if not value:
            return None
        if not value.isdigit():
            logger.warning(f"注册默认配置无效，{config_key} 不是正整数：{raw_value}")
            return None
        number = int(value)
        if number <= 0:
            logger.warning(f"注册默认配置无效，{config_key} 必须大于0：{raw_value}")
            return None
        return number

    @classmethod
    def __parse_positive_int_list(cls, raw_value: Optional[str], config_key: str) -> list[int]:
        """
        解析逗号分隔的正整数列表参数值
        :param raw_value: 参数原始值
        :param config_key: 参数键名
        :return: 去重后的正整数列表
        """
        if raw_value is None:
            return []
        value = raw_value.replace("，", ",").strip()
        if not value:
            return []
        parsed_ids = []
        parsed_id_set = set()
        for item in value.split(","):
            current_item = item.strip()
            if not current_item:
                continue
            if not current_item.isdigit() or int(current_item) <= 0:
                logger.warning(f"注册默认配置无效，{config_key} 包含非法ID：{current_item}")
                continue
            current_id = int(current_item)
            if current_id in parsed_id_set:
                continue
            parsed_ids.append(current_id)
            parsed_id_set.add(current_id)

        return parsed_ids

    @classmethod
    def __get_valid_default_dept_id(cls, query_db: Session, dept_id: Optional[int]) -> Optional[int]:
        """
        校验默认部门配置是否有效
        :param query_db: orm对象
        :param dept_id: 默认部门id
        :return: 有效部门id，无效返回None
        """
        if not dept_id:
            return None
        if DeptDao.get_dept_by_id(query_db, dept_id):
            return dept_id
        logger.warning(f"注册默认配置无效，部门不存在或不可用：dept_id={dept_id}")
        return None

    @classmethod
    def __filter_valid_default_role_ids(cls, query_db: Session, role_ids: list[int]) -> list[int]:
        """
        过滤有效的默认角色id列表
        :param query_db: orm对象
        :param role_ids: 默认角色id列表
        :return: 有效角色id列表
        """
        valid_role_ids = []
        for role_id in role_ids:
            if RoleDao.get_role_by_id(query_db, role_id):
                valid_role_ids.append(role_id)
            else:
                logger.warning(f"注册默认配置无效，角色不存在或不可用：role_id={role_id}")

        return valid_role_ids

    @classmethod
    def __filter_valid_default_post_ids(cls, query_db: Session, post_ids: list[int]) -> list[int]:
        """
        过滤有效的默认岗位id列表
        :param query_db: orm对象
        :param post_ids: 默认岗位id列表
        :return: 有效岗位id列表
        """
        valid_post_ids = []
        for post_id in post_ids:
            if PostDao.get_post_by_id(query_db, post_id):
                valid_post_ids.append(post_id)
            else:
                logger.warning(f"注册默认配置无效，岗位不存在或不可用：post_id={post_id}")

        return valid_post_ids

    @classmethod
    async def __get_register_default_assignments(cls, request: Request, query_db: Session) -> dict:
        """
        获取注册默认部门、角色、岗位配置
        :param request: Request对象
        :param query_db: orm对象
        :return: 默认配置字典（dept_id、role_ids、post_ids）
        """
        default_dept_value = await cls.__get_sys_config_value(request, cls.REGISTER_DEFAULT_DEPT_ID_KEY)
        default_role_ids_value = await cls.__get_sys_config_value(request, cls.REGISTER_DEFAULT_ROLE_IDS_KEY)
        default_post_ids_value = await cls.__get_sys_config_value(request, cls.REGISTER_DEFAULT_POST_IDS_KEY)
        parsed_dept_id = cls.__parse_positive_int(default_dept_value, cls.REGISTER_DEFAULT_DEPT_ID_KEY)
        parsed_role_ids = cls.__parse_positive_int_list(default_role_ids_value, cls.REGISTER_DEFAULT_ROLE_IDS_KEY)
        parsed_post_ids = cls.__parse_positive_int_list(default_post_ids_value, cls.REGISTER_DEFAULT_POST_IDS_KEY)

        return {
            "dept_id": cls.__get_valid_default_dept_id(query_db, parsed_dept_id),
            "role_ids": cls.__filter_valid_default_role_ids(query_db, parsed_role_ids),
            "post_ids": cls.__filter_valid_default_post_ids(query_db, parsed_post_ids),
        }

    @classmethod
    async def authenticate_user(cls, request: Request, query_db: Session, login_user: UserLogin):
        """
        根据用户名密码校验用户登录
        :param request: Request对象
        :param query_db: orm对象
        :param login_user: 登录用户对象
        :return: 校验结果
        """
        await cls.__check_login_ip(request)
        account_lock = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.ACCOUNT_LOCK.get('key')}:{login_user.user_name}")
        if login_user.user_name == account_lock:
            logger.warning("账号已锁定，请稍后再试")
            raise LoginException(data="", message="账号已锁定，请稍后再试")
        # 判断请求是否来自于api文档，如果是返回指定格式的结果，用于修复api文档认证成功后token显示undefined的bug
        request_from_swagger = request.headers.get('referer').endswith('docs') if request.headers.get(
            'referer') else False
        request_from_redoc = request.headers.get('referer').endswith('redoc') if request.headers.get(
            'referer') else False
        # 判断是否开启验证码，开启则验证，否则不验证（dev模式下来自API文档的登录请求不检验）
        if not login_user.captcha_enabled or (
                (request_from_swagger or request_from_redoc) and AppConfig.app_env == 'dev'):
            pass
        else:
            await cls.__check_login_captcha(request, login_user)
        user = login_by_account(query_db, login_user.user_name)
        if not user:
            logger.warning("用户不存在")
            raise LoginException(data="", message="用户不存在")
        if not PwdUtil.verify_password(login_user.password, user[0].password):
            cache_password_error_count = await request.app.state.redis.get(
                f"{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.get('key')}:{login_user.user_name}")
            password_error_counted = 0
            if cache_password_error_count:
                password_error_counted = cache_password_error_count
            password_error_count = int(password_error_counted) + 1
            await request.app.state.redis.set(
                f"{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.get('key')}:{login_user.user_name}", password_error_count,
                ex=timedelta(minutes=10))
            if password_error_count > 5:
                await request.app.state.redis.delete(
                    f"{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.get('key')}:{login_user.user_name}")
                await request.app.state.redis.set(
                    f"{RedisInitKeyConfig.ACCOUNT_LOCK.get('key')}:{login_user.user_name}", login_user.user_name,
                    ex=timedelta(minutes=10))
                logger.warning("10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试")
                raise LoginException(data="", message="10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试")
            logger.warning("密码错误")
            raise LoginException(data="", message="密码错误")
        if user[0].status == '1':
            logger.warning("用户已停用")
            raise LoginException(data="", message="用户已停用")
        await request.app.state.redis.delete(
            f"{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.get('key')}:{login_user.user_name}")
        return user

    @classmethod
    async def __check_login_ip(cls, request: Request):
        """
        校验用户登录ip是否在黑名单内
        :param request: Request对象
        :return: 校验结果
        """
        black_ip_value = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SYS_CONFIG.get('key')}:sys.login.blackIPList")
        black_ip_list = black_ip_value.split(',') if black_ip_value else []
        if request.headers.get('X-Forwarded-For') in black_ip_list:
            logger.warning("当前IP禁止登录")
            raise LoginException(data="", message="当前IP禁止登录")
        return True

    @classmethod
    async def __check_login_captcha(cls, request: Request, login_user: UserLogin):
        """
        校验用户登录验证码
        :param request: Request对象
        :param login_user: 登录用户对象
        :return: 校验结果
        """
        captcha_value = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.CAPTCHA_CODES.get('key')}:{login_user.uuid}")
        if not captcha_value:
            logger.warning("验证码已失效")
            raise LoginException(data="", message="验证码已失效")
        if login_user.code != str(captcha_value):
            logger.warning("验证码错误")
            raise LoginException(data="", message="验证码错误")
        return True

    @classmethod
    def create_access_token(cls, data: dict, expires_delta: Union[timedelta, None] = None):
        """
        根据登录信息创建当前用户token
        :param data: 登录信息
        :param expires_delta: token有效期
        :return: token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(weeks=1)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, JwtConfig.jwt_secret_key, algorithm=JwtConfig.jwt_algorithm)
        return encoded_jwt

    @classmethod
    def __get_request_ip(cls, request: Request) -> str | None:
        """
        获取当前请求的客户端IP
        :param request: Request对象
        :return: 客户端IP字符串，不存在时返回None
        """
        forward_ip = request.headers.get("X-Forwarded-For")
        if forward_ip:
            return forward_ip.split(",")[0].strip()
        if request.client:
            return request.client.host
        return None

    @classmethod
    def __resolve_user_permissions(cls, query_user: dict) -> list[str]:
        """
        根据数据库查询结果计算登录账号原始权限列表
        :param query_user: 用户查询结果字典
        :return: 当前登录账号原始权限列表
        """
        role_id_list = [item.role_id for item in query_user.get("user_role_info")]
        if 1 in role_id_list:
            return ["*:*:*"]
        return [row.perms for row in query_user.get("user_menu_info") if row.perms]

    @classmethod
    def __build_current_user_model(
        cls,
        query_user: dict,
        permissions: list[str],
        auth_type: str = "user",
        api_key_id: int | None = None,
        api_key_name: str | None = None,
    ) -> CurrentUserModel:
        """
        根据用户查询结果和权限信息构造当前用户模型
        :param query_user: 用户查询结果字典
        :param permissions: 当前请求最终生效的权限列表
        :param auth_type: 当前鉴权类型，user表示账号登录，api_key表示API Key登录
        :param api_key_id: 可选，当前API Key主键
        :param api_key_name: 可选，当前API Key名称
        :return: 当前用户模型对象
        """
        post_ids = ",".join([str(row.post_id) for row in query_user.get("user_post_info")])
        role_ids = ",".join([str(row.role_id) for row in query_user.get("user_role_info")])
        roles = [row.role_key for row in query_user.get("user_role_info")]

        return CurrentUserModel(
            permissions=permissions,
            roles=roles,
            user=UserInfoModel(
                **CamelCaseUtil.transform_result(query_user.get("user_basic_info")),
                postIds=post_ids,
                roleIds=role_ids,
                dept=CamelCaseUtil.transform_result(query_user.get("user_dept_info")),
                role=CamelCaseUtil.transform_result(query_user.get("user_role_info")),
            ),
            authType=auth_type,
            apiKeyId=api_key_id,
            apiKeyName=api_key_name,
        )

    @classmethod
    async def __get_current_user_by_jwt(cls, request: Request, token: str, query_db: Session) -> CurrentUserModel:
        """
        根据JWT令牌获取当前用户信息
        :param request: Request对象
        :param token: JWT令牌明文
        :param query_db: orm对象
        :return: 当前用户模型对象
        :raise AuthException: 当JWT令牌不合法或已失效时抛出
        """
        try:
            payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
            user_id: str = payload.get("user_id")
            session_id: str = payload.get("session_id")
            if user_id is None:
                logger.warning("用户token不合法")
                raise AuthException(data="", message="用户token不合法")
            token_data = TokenData(user_id=int(user_id))
        except JWTError:
            logger.warning("用户token已失效，请重新登录")
            raise AuthException(data="", message="用户token已失效，请重新登录")

        query_user = UserDao.get_user_by_id(query_db, user_id=token_data.user_id)
        if query_user.get("user_basic_info") is None:
            logger.warning("用户token不合法")
            raise AuthException(data="", message="用户token不合法")

        if AppConfig.app_same_time_login:
            redis_token = await request.app.state.redis.get(f"{RedisInitKeyConfig.ACCESS_TOKEN.get('key')}:{session_id}")
        else:
            redis_token = await request.app.state.redis.get(
                f"{RedisInitKeyConfig.ACCESS_TOKEN.get('key')}:{query_user.get('user_basic_info').user_id}"
            )

        if token != redis_token:
            logger.warning("用户token已失效，请重新登录")
            raise AuthException(data="", message="用户token已失效，请重新登录")

        if AppConfig.app_same_time_login:
            await request.app.state.redis.set(
                f"{RedisInitKeyConfig.ACCESS_TOKEN.get('key')}:{session_id}",
                redis_token,
                ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
            )
        else:
            await request.app.state.redis.set(
                f"{RedisInitKeyConfig.ACCESS_TOKEN.get('key')}:{query_user.get('user_basic_info').user_id}",
                redis_token,
                ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
            )

        return cls.__build_current_user_model(
            query_user=query_user,
            permissions=cls.__resolve_user_permissions(query_user),
            auth_type="user",
        )

    @classmethod
    async def __get_current_user_by_api_key(cls, request: Request, api_key: str, query_db: Session) -> CurrentUserModel:
        """
        根据API Key获取当前用户信息
        :param request: Request对象
        :param api_key: API Key明文
        :param query_db: orm对象
        :return: 当前用户模型对象
        :raise AuthException: 当API Key不合法、已过期或所属用户失效时抛出
        """
        api_key_info = ApiKeyService.authenticate_api_key_services(
            query_db=query_db,
            api_key=api_key,
            request_ip=cls.__get_request_ip(request),
        )
        query_user = UserDao.get_user_by_id(query_db, user_id=api_key_info.user_id)
        if query_user.get("user_basic_info") is None:
            logger.warning("API Key所属用户不存在或已停用")
            raise AuthException(data="", message="API Key所属用户不存在或已停用")

        user_permissions = cls.__resolve_user_permissions(query_user)
        api_key_permissions = ApiKeyService.parse_permission_codes(api_key_info.permission_codes)
        effective_permissions = ApiKeyService.get_effective_permission_codes(user_permissions, api_key_permissions)

        return cls.__build_current_user_model(
            query_user=query_user,
            permissions=effective_permissions,
            auth_type="api_key",
            api_key_id=api_key_info.api_key_id,
            api_key_name=api_key_info.key_name,
        )

    @classmethod
    def __resolve_auth_credential(cls, request: Request, token: str | None) -> tuple[str, str]:
        """
        解析当前请求使用的鉴权方式及凭证值
        :param request: Request对象
        :param token: Authorization请求头原始值
        :return: (鉴权类型, 凭证值) 元组，鉴权类型取值为jwt或api_key
        :raise AuthException: 当请求头中未携带任何可用凭证时抛出
        """
        raw_authorization = (token or "").strip()
        if not raw_authorization:
            x_api_key = (request.headers.get("X-API-Key") or "").strip()
            if x_api_key:
                return "api_key", x_api_key
            logger.warning("未提供认证信息")
            raise AuthException(data="", message="未提供认证信息")

        scheme, separator, credential = raw_authorization.partition(" ")
        if separator:
            normalized_scheme = scheme.lower()
            normalized_credential = credential.strip()
            if not normalized_credential:
                logger.warning("认证信息不合法")
                raise AuthException(data="", message="认证信息不合法")
            if normalized_scheme == "bearer":
                return "jwt", normalized_credential
            if normalized_scheme in {"apikey", "api-key"}:
                return "api_key", normalized_credential

        if raw_authorization.count(".") == 2:
            return "jwt", raw_authorization
        return "api_key", raw_authorization

    @classmethod
    async def get_current_user(
        cls,
        request: Request,
        token: Optional[str] = Depends(get_authorization_header),
        query_db: Session = Depends(get_db),
    ):
        """
        根据token获取当前用户信息
        :param request: Request对象
        :param token: 用户token
        :param query_db: orm对象
        :return: 当前用户信息对象
        :raise: 令牌异常AuthException
        """
        auth_type, credential = cls.__resolve_auth_credential(request, token)
        if auth_type == "jwt":
            return await cls.__get_current_user_by_jwt(request, credential, query_db)
        return await cls.__get_current_user_by_api_key(request, credential, query_db)

    @classmethod
    async def get_current_user_routers(cls, user_id: int, query_db: Session):
        """
        根据用户id获取当前用户路由信息
        :param user_id: 用户id
        :param query_db: orm对象
        :return: 当前用户路由信息对象
        """
        query_user = UserDao.get_user_by_id(query_db, user_id=user_id)
        user_router_menu = sorted([row for row in query_user.get('user_menu_info') if row.menu_type in ['M', 'C']],
                                  key=lambda x: x.order_num)
        user_router = cls.__generate_user_router_menu(0, user_router_menu)
        return user_router

    @classmethod
    def __generate_user_router_menu(cls, pid: int, permission_list):
        """
        工具方法：根据菜单信息生成路由信息树形嵌套数据
        :param pid: 菜单id
        :param permission_list: 菜单列表信息
        :return: 路由信息树形嵌套数据
        """
        router_list = []
        for permission in permission_list:
            if permission.parent_id == pid:
                children = cls.__generate_user_router_menu(permission.menu_id, permission_list)
                router_list_data = {}
                if permission.menu_type == 'M':
                    router_list_data['name'] = permission.path.capitalize()
                    router_list_data['hidden'] = False if permission.visible == '0' else True
                    if permission.parent_id == 0:
                        router_list_data['component'] = 'Layout'
                        router_list_data['path'] = f'/{permission.path}'
                    else:
                        router_list_data['component'] = 'ParentView'
                        router_list_data['path'] = permission.path
                    if permission.is_frame == 1:
                        router_list_data['redirect'] = 'noRedirect'
                    else:
                        router_list_data['path'] = permission.path
                    if children:
                        router_list_data['alwaysShow'] = True
                        router_list_data['children'] = children
                    router_list_data['meta'] = {
                        'title': permission.menu_name,
                        'icon': permission.icon,
                        'noCache': False if permission.is_cache == '0' else True,
                        'link': permission.path if permission.is_frame == 0 else None
                    }
                elif permission.menu_type == 'C':
                    router_list_data['name'] = permission.path.capitalize()
                    router_list_data['path'] = permission.path
                    router_list_data['query'] = permission.query
                    router_list_data['hidden'] = False if permission.visible == '0' else True
                    router_list_data['component'] = permission.component
                    router_list_data['meta'] = {
                        'title': permission.menu_name,
                        'icon': permission.icon,
                        'noCache': False if permission.is_cache == '0' else True,
                        'link': permission.path if permission.is_frame == 0 else None
                    }
                router_list.append(router_list_data)

        return router_list

    @classmethod
    async def register_user_services(cls, request: Request, query_db: Session, user_register: UserRegister):
        """
        用户注册services
        :param request: Request对象
        :param query_db: orm对象
        :param user_register: 注册用户对象
        :return: 注册结果
        """
        register_enabled = True if await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SYS_CONFIG.get('key')}:sys.account.registerUser") == 'true' else False
        captcha_enabled = True if await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SYS_CONFIG.get('key')}:sys.account.captchaEnabled") == 'true' else False
        if user_register.password == user_register.confirm_password:
            if register_enabled:
                if captcha_enabled:
                    captcha_value = await request.app.state.redis.get(
                        f"{RedisInitKeyConfig.CAPTCHA_CODES.get('key')}:{user_register.uuid}")
                    if not captcha_value:
                        logger.warning("验证码已失效")
                        return CrudResponseModel(is_success=False, message='验证码已失效')
                    elif user_register.code != str(captcha_value):
                        logger.warning("验证码错误")
                        return CrudResponseModel(is_success=False, message='验证码错误')
                default_assignments = await cls.__get_register_default_assignments(request, query_db)
                add_user = AddUserModel(
                    userName=user_register.username,
                    nickName=user_register.username,
                    password=PwdUtil.get_password_hash(user_register.password),
                    deptId=default_assignments.get('dept_id'),
                    roleIds=default_assignments.get('role_ids'),
                    postIds=default_assignments.get('post_ids')
                )
                result = UserService.add_user_services(query_db, add_user)
                return result
            else:
                result = {"is_success": False, "message": '注册程序已关闭，禁止注册'}
        else:
            result = {"is_success": False, "message": '两次输入的密码不一致'}

        return CrudResponseModel(**result)

    @classmethod
    async def get_sms_code_services(cls, request: Request, query_db: Session, user: ResetUserModel):
        """
        获取短信验证码service
        :param request: Request对象
        :param query_db: orm对象
        :param user: 用户对象
        :return: 短信验证码对象
        """
        redis_sms_result = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SMS_CODE.get('key')}:{user.session_id}")
        if redis_sms_result:
            return SmsCode(**{"is_success": False, "sms_code": '', "session_id": '', "message": '短信验证码仍在有效期内'})
        is_user = UserDao.get_user_by_name(query_db, user.user_name)
        if is_user:
            sms_code = str(random.randint(100000, 999999))
            session_id = str(uuid.uuid4())
            await request.app.state.redis.set(f"{RedisInitKeyConfig.SMS_CODE.get('key')}:{session_id}", sms_code,
                                              ex=timedelta(minutes=2))
            # 此处模拟调用短信服务
            message_service(sms_code)

            return SmsCode(**{"is_success": True, "sms_code": sms_code, "session_id": session_id, "message": '获取成功'})

        return SmsCode(**{"is_success": False, "sms_code": '', "session_id": '', "message": '用户不存在'})

    @classmethod
    async def forget_user_services(cls, request: Request, query_db: Session, forget_user: ResetUserModel):
        """
        用户忘记密码services
        :param request: Request对象
        :param query_db: orm对象
        :param forget_user: 重置用户对象
        :return: 重置结果
        """
        redis_sms_result = await request.app.state.redis.get(
            f"{RedisInitKeyConfig.SMS_CODE.get('key')}:{forget_user.session_id}")
        if forget_user.sms_code == redis_sms_result:
            forget_user.password = PwdUtil.get_password_hash(forget_user.password)
            forget_user.user_id = UserDao.get_user_by_name(query_db, forget_user.user_name).user_id
            edit_result = UserService.reset_user_services(query_db, forget_user)
            result = edit_result.dict()
        elif not redis_sms_result:
            result = {"is_success": False, "message": '短信验证码已过期'}
        else:
            await request.app.state.redis.delete(f"{RedisInitKeyConfig.SMS_CODE.get('key')}:{forget_user.session_id}")
            result = {"is_success": False, "message": '短信验证码不正确'}

        return CrudResponseModel(**result)

    @classmethod
    async def logout_services(cls, request: Request, session_id: str):
        """
        退出登录services
        :param request: Request对象
        :param session_id: 会话编号
        :return: 退出登录结果
        """
        await request.app.state.redis.delete(f"{RedisInitKeyConfig.ACCESS_TOKEN.get('key')}:{session_id}")
        # await request.app.state.redis.delete(f'{current_user.user.user_id}_access_token')
        # await request.app.state.redis.delete(f'{current_user.user.user_id}_session_id')

        return True
