from shutil import ExecError

from loguru import logger

from model.config import PosParamsModel, ResolutionModel
from server.config import PosConfig, SearchConfig, StartConfig
from server.pos_config_server import PosConfigServer
from services.pos.rules.local_env_rule import LocalEnvRule
from services.pos.rules.mismatch_rule import MismatchRule
from services.pos.rules.remote_rule import NoRemoteRule
from services.pos.rules.uat_rule import UatNoLocalRule
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
        try:
            if ctx.start_config.change_pos:
                PosConfigServer.change_pos_on_network(ctx.path)

            if ctx.start_config.account_logout:
                PosConfigServer.logout_pos_account(ctx.path)

            if ctx.start_config.replace_mitm_cert:
                success, msg = PosConfig.replace_mitm_cert(ctx.path)
                if not success:
                    raise Exception(msg)

            if ctx.start_config.backup:
                PosConfig.backup_payment_driver(ctx.path)

            if ctx.start_config.cover_payment_driver:
                success, msg = PosConfig.cover_payment_driver(ctx.path)
                if not success:
                    raise Exception(msg)

            if ctx.start_config.remove_cache:
                PosConfig.clean_cache(ctx.path)

            env = cls._build_env(ctx)

            process = file_handle.start_file_independent(ctx.path, env)

            return process.pid if process else None
        except Exception as e:
            logger.exception(e)
            raise ExecError("启动异常") from e

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
        return [
            LocalEnvRule(),
            UatNoLocalRule(),
            NoRemoteRule(),
            MismatchRule(),
        ]
