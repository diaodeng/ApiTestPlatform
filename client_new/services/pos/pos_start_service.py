from loguru import logger

from common.excptions import PosHandleException, PosStartException
from model.config import PosParamsModel, ResolutionModel
from server.config import PosConfig, StartConfig
from server.pos_config_server import PosConfigServer
from utils import file_handle

from .context import PosStartContext
from .pos_start_engine import PosStartEngine


class PosStartService:
    def __init__(self):
        pass

    @classmethod
    def prepare_start(cls, dialog_service, path, start_config=None):
        ctx = cls._build_context(path, start_config)
        engine = PosStartEngine(cls._rules())
        ok = engine.run(ctx, dialog_service)
        return ok, ctx

    @classmethod
    def _build_context(cls, path, start_config) -> PosStartContext:
        ctx = PosStartContext(path, start_config)
        ctx.start_config = StartConfig.read()

        ctx.local_env_info = PosConfig.get_local_pos_env(path)
        if not ctx.local_env_info:
            return ctx

        ctx.local_pos_params = PosConfig.read_pos_params(path, 1)
        ctx.remote_pos_params = PosConfig.read_pos_params(path, 2)

        ctx.has_local = isinstance(ctx.local_pos_params, PosParamsModel)
        ctx.has_remote = isinstance(ctx.remote_pos_params, PosParamsModel)

        ctx.remote_info = PosConfig.remote_pos_info(ctx.remote_pos_params)

        return ctx

    @classmethod
    def execute_start(cls, ctx):
        """
        执行启动：按启动配置依次执行前置动作后拉起 POS 进程。

        异常分层约定：
        - PosHandleException / 带 message 的业务异常：文案已可读，原样上抛给前端展示；
        - 其他未知异常：包装为 PosStartException，避免前端只看到笼统的"启动异常"。
        """
        try:
            # 切换云端POS：勾选了启动配置，或用户在"配置不一致"弹窗选择了"切换后启动"
            if (ctx.start_config.change_pos or ctx.need_switch) and not ctx.skip_dependent_actions:
                PosConfigServer.change_pos_on_network(ctx.path)

            if ctx.start_config.account_logout and not ctx.skip_dependent_actions:
                PosConfigServer.logout_pos_account(ctx.path)

            if ctx.start_config.replace_mitm_cert:
                success, msg = PosConfig.replace_mitm_cert(ctx.path)
                if not success:
                    raise PosStartException(msg)

            if ctx.start_config.backup:
                PosConfig.backup_payment_driver(ctx.path)

            if ctx.start_config.cover_payment_driver:
                success, msg = PosConfig.cover_payment_driver(ctx.path)
                if not success:
                    raise PosStartException(msg)

            if ctx.start_config.remove_cache:
                PosConfig.clean_cache(ctx.path)

            env = cls._build_env(ctx)

            process = file_handle.start_file_independent(ctx.path, env)

            return process.pid if process else None
        except (PosHandleException, PosStartException) as e:
            # 业务异常：文案已明确（如"获取pos_params参数失败"、"支付mock驱动不存在"），原样上抛
            logger.exception(f"启动前自动处理失败: {e}")
            raise
        except Exception as e:
            # 未知异常：包装后上抛，保留原始异常链
            logger.exception(e)
            raise PosStartException(f"启动前自动处理失败: {e}") from e

    @classmethod
    def _build_env(cls, ctx: PosStartContext):
        pos_params = ctx.remote_pos_params

        if pos_params and isinstance(pos_params, PosParamsModel):
            vendor_id = pos_params.venderNo
            config = PosConfig.get_vendor_config(vendor_id=vendor_id)

            if str(pos_params.posType) == "2":
                return config.resolution.sco.model_dump()
            else:
                return config.resolution.pos.model_dump()

        return ResolutionModel().model_dump()

    @classmethod
    def _rules(cls):
        # 规则链已清空：全部确认逻辑收敛到引擎各阶段，避免同一条件重复弹窗——
        # - UatNoLocalRule：与 _env_decision UAT分支重复（已删文件）；
        # - NoRemoteRule：与 _env_decision 的"没获取到服务端配置"分支逐象限重复（已删文件）；
        # - MismatchRule：与 _consistency_check 重复，且其 3 字段比对弱于 is_mismatch 的 6 字段；
        #   勾选"切换云端POS"时不一致本就是要切的内容，补弹确认反而语义矛盾；
        # - LocalEnvRule：在 _pre_check 就地硬校验（缺 pos.ini 阻断），不进规则链。
        return []
