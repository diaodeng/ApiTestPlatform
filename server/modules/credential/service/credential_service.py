import re
from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.credential.dao.credential_dao import CredentialDao
from modules.credential.entity.vo.credential_vo import (
    CredentialAuthConfigModel,
    CredentialModel,
    CredentialSaveModel,
    CredentialUpdateModel,
)
from modules.credential.util.credential_secret_util import decrypt_secret, encrypt_secret, mask_secret
from utils.log_util import logger

# 完整的模板占位符（允许首尾空白）时不含密文，脱敏时原样回显：
# ${secret.字段名} 引用凭证字段；${step.N.变量}/${step.步骤id.变量} 引用更早步骤的输出。
# 两类都是"引用声明"而非真实值，遮蔽会导致编辑页无法回显用户配置。
_TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"\$\{(?:secret|step\.[A-Za-z0-9]+)\.[A-Za-z_][A-Za-z0-9_]*\}")


class CredentialService:
    """凭证聚合根服务，负责密文快照、版本控制和安全审计。"""

    @classmethod
    def get_credential_secret(cls, db: Session, credential_id: int) -> dict | None:
        """获取解密后的凭证明文，仅用于编辑回显。调用方需自行控制权限。"""
        row = CredentialDao.get_credential(db, credential_id)
        if not row or not row.secret_cipher_text:
            return None
        try:
            return decrypt_secret(row.secret_cipher_text)
        except Exception:
            logger.warning(f"解密凭证失败，credential_id={credential_id}")
            return None

    @classmethod
    def list_credentials(cls, db: Session, keyword: str, enabled: bool | None) -> list[CredentialModel]:
        """获取不含明文的凭证列表。"""
        return [cls.to_model(db, row) for row in CredentialDao.list_credentials(db, keyword, enabled)]

    @classmethod
    def get_credential(cls, db: Session, credential_id: int) -> CredentialModel | None:
        """获取不含明文的凭证详情。"""
        row = CredentialDao.get_credential(db, credential_id)
        return cls.to_model(db, row) if row else None

    @classmethod
    def create_credential(cls, db: Session, model: CredentialSaveModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """创建凭证和认证配置，凭证明文仅在本次请求内存在。"""
        now = datetime.now()
        user_name = current_user.user.user_name
        # 多步链 ${secret.*} 引用校验：失败以业务失败返回（HTTP 200 + failure），
        # 若让 ValueError 冒泡会变成 500，前端只能看到"系统接口500异常"而丢失具体原因。
        try:
            cls._validate_step_secret_references(model.auth_config, model.secret)
        except ValueError as exc:
            return CrudResponseModel(is_success=False, message=str(exc))
        try:
            row = CredentialDao.add_credential(
                db,
                {
                    "credential_name": model.credential_name.strip(),
                    "credential_type": model.credential_type,
                    "auth_mode": model.auth_mode,
                    "enabled": model.enabled,
                    "auto_refresh_enabled": model.auto_refresh_enabled,
                    "refresh_interval_sec": model.refresh_interval_sec,
                    "sharing_mode": model.sharing_mode,
                    "secret_cipher_text": encrypt_secret(model.secret),
                    "secret_mask": mask_secret(model.secret),
                    "expire_time": model.expire_time,
                    "create_by": user_name,
                    "create_time": now,
                    "update_by": user_name,
                    "update_time": now,
                    "remark": model.remark,
                },
            )
            CredentialDao.save_auth_config(db, row.credential_id, model.auth_config.model_dump(by_alias=False))
            CredentialDao.add_operation_log(db, {"credential_id": row.credential_id, "operation_type": "create", "status": "success", "revision": 1, "message": "已创建凭证", "operator": user_name})
            db.commit()
            logger.info(f"已创建统一凭证，credential_id={row.credential_id}，credential_name={row.credential_name}")
            return CrudResponseModel(is_success=True, message="新增成功", result={"credentialId": str(row.credential_id)})
        except Exception:
            db.rollback()
            raise

    @classmethod
    def update_credential(cls, db: Session, credential_id: int, model: CredentialUpdateModel, current_user: CurrentUserModel) -> CrudResponseModel:
        """乐观锁更新凭证；冲突不会覆盖刷新后的有效凭证。"""
        current = CredentialDao.get_credential(db, credential_id)
        if not current:
            return CrudResponseModel(is_success=False, message="凭证不存在")
        now = datetime.now()
        values = model.model_dump(exclude={"expected_revision", "secret", "auth_config"}, by_alias=False)
        values.update({
            "credential_name": model.credential_name.strip(),
            "revision": model.expected_revision + 1,
            "update_by": current_user.user.user_name,
            "update_time": now,
        })
        # 详情接口不会返回密文，编辑普通字段时必须保留原快照，避免空 JSON 覆盖有效凭证。
        # 但凭证类型变化时，旧类型的主凭证不能继续被刷新请求携带。
        if model.secret or current.credential_type != model.credential_type:
            merged_secret = decrypt_secret(current.secret_cipher_text)
            if current.credential_type != model.credential_type:
                cls._clear_primary_secret_fields(merged_secret)
            # 编辑页已回填明文，显式传空串的字段表示用户清空了该敏感项，合并前删除而不是保留旧值。
            cls._drop_empty_secret_fields(model.secret)
            merged_secret.update(model.secret)
            # 多步链步骤模板中的 ${secret.*} 引用必须能在合并后的 secret 中解析，否则执行期原样发出。
            # 校验失败以业务失败返回（HTTP 200 + failure）；ValueError 冒泡会变成 500，丢失具体原因。
            try:
                cls._validate_step_secret_references(model.auth_config, merged_secret)
            except ValueError as exc:
                db.rollback()
                return CrudResponseModel(is_success=False, message=str(exc))
            values["secret_cipher_text"] = encrypt_secret(merged_secret)
            values["secret_mask"] = mask_secret(merged_secret)
        try:
            updated = CredentialDao.update_credential(db, credential_id, values, model.expected_revision)
            if not updated:
                CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "update_conflict", "status": "conflict", "revision": model.expected_revision, "message": "凭证已被其他刷新或编辑操作更新", "operator": current_user.user.user_name})
                db.commit()
                return CrudResponseModel(is_success=False, message="凭证版本冲突，请刷新页面后重试")
            CredentialDao.save_auth_config(db, credential_id, model.auth_config.model_dump(by_alias=False))
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "update", "status": "success", "revision": model.expected_revision + 1, "message": "已更新凭证", "operator": current_user.user.user_name})
            db.commit()
            return CrudResponseModel(is_success=True, message="修改成功")
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _drop_empty_secret_fields(secret: dict) -> None:
        """更新时剔除显式传空串的主字段，使"清空输入框保存"等价于删除该敏感字段。

        仅处理顶层字符串键；headers/cookies 等对象字段由编辑页整体覆盖，不走该逻辑。
        """
        for key in [key for key, value in secret.items() if value == ""]:
            secret.pop(key, None)

    @classmethod
    def _validate_step_secret_references(cls, auth_config, secret: dict) -> None:
        """校验多步链步骤模板中 ${secret.字段} 引用是否能被渲染。

        两类豁免（渲染引擎在执行时会自动注入或语义兼容，secret 里本就不存在同名字段）：
        - 运行时变量：`otp`（TOTP/手工验证码，按 otpType 生成）、`cookie`/`token`（主 Header 值
          或 Token 字段的语义别名）、`headerValue`（主 Header 值）；
        - 历史兼容别名：`header_value` → `headerValue`、`otp_secret`/`otpsecret` → `otpSecret`。
        引用其它不存在的字段（如把接口参数 pwd 误写成 ${secret.pwd} 而密文字段是 password）
        会在执行期原样发给目标系统导致登录失败，因此在保存时拒绝。
        仅扫描 url/headers/body。
        """
        steps = [
            ("登录链", getattr(auth_config, "login_steps", None) or []),
            ("刷新链", getattr(auth_config, "refresh_steps", None) or []),
        ]
        available = {str(key) for key in (secret or {}).keys()}
        # 运行时变量：渲染前由引擎注入 secret 上下文，不需要用户在凭证中显式保存。
        # cookie/token/headerValue 是主 Header/Token 字段的语义别名，始终可用；
        # otp 仅在凭证保存了 TOTP 密钥（otpSecret）时可用——此时按 otpType 自动生成。
        runtime_names = {"cookie", "token", "headerValue"}
        # 历史兼容：这些别名渲染工具会归一为正式字段名。
        alias_to_canonical = {"header_value": "headerValue", "otp_secret": "otpSecret", "otpsecret": "otpSecret"}
        available = {alias_to_canonical.get(key, key) for key in available}
        if "otpSecret" in available or "totpSecret" in available:
            runtime_names.add("otp")
        pattern = re.compile(r"\$\{secret\.([A-Za-z_][A-Za-z0-9_]*)\}")
        for chain_label, chain_steps in steps:
            for index, step in enumerate(chain_steps, start=1):
                position = f"{chain_label}步骤 {index}"
                step_name = getattr(step, "name", "") or ""
                if step_name:
                    position = f"{chain_label}步骤 {index}（{step_name}）"
                templates = [
                    getattr(step, "url", ""),
                    getattr(step, "headers", {}) or {},
                    getattr(step, "body", None),
                ]
                for template in templates:
                    for match in cls._iter_secret_references(template, pattern):
                        canonical = alias_to_canonical.get(match, match)
                        if canonical in available or canonical in runtime_names or match in runtime_names:
                            continue
                        raise ValueError(
                            f"{position}引用了 ${{secret.{match}}}，但当前凭证没有填写对应的 {match} 字段；"
                            "请在登录账号区域或其他敏感字段中填写后，再以 ${secret.字段名} 方式引用"
                        )

    @classmethod
    def _iter_secret_references(cls, value, pattern: re.Pattern):
        """递归产出任意 JSON 结构中所有 ${secret.字段} 引用的字段名。"""
        if isinstance(value, str):
            for match in pattern.finditer(value):
                yield match.group(1)
        elif isinstance(value, dict):
            for item in value.values():
                yield from cls._iter_secret_references(item, pattern)
        elif isinstance(value, list):
            for item in value:
                yield from cls._iter_secret_references(item, pattern)

    @staticmethod
    def _clear_primary_secret_fields(secret: dict) -> None:
        """切换凭证类型时删除旧类型主字段，保留附加 Header、Cookie 和登录账号等共享字段。"""
        primary_fields = {
            "cookie",
            "cookieHeader",
            "headerName",
            "header_name",
            "headerValue",
            "header_value",
            "valuePrefix",
            "value_prefix",
            "token",
            "apiKey",
            "storageState",
            "storage_state",
        }
        for field in primary_fields:
            secret.pop(field, None)

    @classmethod
    def delete_credential(cls, db: Session, credential_id: int, current_user: CurrentUserModel) -> CrudResponseModel:
        """逻辑删除凭证，已绑定业务在下次解析时会明确失败，避免静默降级。"""
        row = CredentialDao.get_credential(db, credential_id)
        if not row:
            return CrudResponseModel(is_success=False, message="凭证不存在")
        try:
            CredentialDao.update_credential(db, credential_id, {"del_flag": "2", "update_by": current_user.user.user_name, "update_time": datetime.now()})
            CredentialDao.add_operation_log(db, {"credential_id": credential_id, "operation_type": "delete", "status": "success", "revision": row.revision, "message": "已逻辑删除凭证", "operator": current_user.user.user_name})
            db.commit()
            return CrudResponseModel(is_success=True, message="删除成功")
        except Exception:
            db.rollback()
            raise

    @classmethod
    def to_model(cls, db: Session, row) -> CredentialModel:
        """将 ORM 凭证转换为安全响应模型。"""
        config = CredentialDao.get_auth_config(db, row.credential_id)
        auth_config = CredentialAuthConfigModel.model_validate(config) if config else CredentialAuthConfigModel()
        auth_config_data = auth_config.model_dump(by_alias=False)
        for key in ("request_template", "login_request_template", "refresh_request_template"):
            auth_config_data[key] = cls._redact_config_value(auth_config_data.get(key) or {})
        for key in ("login_steps", "refresh_steps"):
            auth_config_data[key] = [cls._redact_step_config(step) for step in (auth_config_data.get(key) or [])]
        auth_config = CredentialAuthConfigModel.model_validate(auth_config_data)
        return CredentialModel(
            credentialId=str(row.credential_id), credentialName=row.credential_name, credentialType=row.credential_type,
            authMode=row.auth_mode, enabled=row.enabled, autoRefreshEnabled=row.auto_refresh_enabled,
            refreshIntervalSec=row.refresh_interval_sec, sharingMode=row.sharing_mode, secretMask=row.secret_mask,
            revision=row.revision, expireTime=row.expire_time, lastRefreshTime=row.last_refresh_time,
            lastRefreshStatus=row.last_refresh_status, lastRefreshMessage=row.last_refresh_message,
            authConfig=auth_config, remark=row.remark, createBy=row.create_by, createTime=row.create_time,
            updateBy=row.update_by, updateTime=row.update_time,
        )

    @staticmethod
    def _redact_config_value(value):
        """隐藏请求模板中的常见敏感字段，防止编辑详情接口泄露固定密码或密钥。

        值为 ${secret.字段名} 占位符时不脱敏：占位符只是引用声明、不含密文，
        回显给编辑页才能正确显示用户配置；仅字面量敏感值被遮蔽为 ******。
        """
        sensitive_names = {
            "password", "passwd", "pwd", "secret", "token", "authorization",
            "cookie", "api_key", "apikey", "otp", "otp_secret", "otpsecret",
            "google_code", "ticket",
        }
        if isinstance(value, str) and _TEMPLATE_PLACEHOLDER_PATTERN.fullmatch(value.strip()):
            return value
        if isinstance(value, dict):
            return {
                key: (
                    "******"
                    if str(key).lower().replace("-", "_") in sensitive_names
                    and not (isinstance(item, str) and _TEMPLATE_PLACEHOLDER_PATTERN.fullmatch(item.strip()))
                    else CredentialService._redact_config_value(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [CredentialService._redact_config_value(item) for item in value]
        return value

    @classmethod
    def _redact_step_config(cls, step):
        """脱敏多步认证链单个步骤的 Header 与请求体中的字面量敏感值。

        步骤 outputs/assertions/when 是提取路径与断言配置，不含密文，保持原样返回；
        body 中建议用 ${secret.字段} 占位符，用户误填字面量密码时详情接口不会回显。
        """
        if not isinstance(step, dict):
            return step
        redacted = dict(step)
        redacted["headers"] = cls._redact_config_value(redacted.get("headers") or {})
        redacted["body"] = cls._redact_config_value(redacted.get("body"))
        return redacted
