# pos_start_engine.py
import os

from loguru import logger

from services.pos.rules.local_env_rule import LocalEnvRule
from utils.common import kill_process_by_name

from .context import PosStartContext


class PosStartEngine:
    def __init__(self, rules):
        self.rules = rules

    def run(self, ctx: PosStartContext, ui):

        # 阶段1：硬校验（短路）
        if not self._pre_check(ctx, ui):
            return False

        # 阶段2：环境决策（分支）
        if not self._env_decision(ctx, ui):
            return False

        # 阶段3：一致性处理
        if not self._consistency_check(ctx, ui):
            return False

        for rule in self.rules:
            result = rule.apply(ctx)

            if not result.continue_flow:
                ui.error(result.message)
                return False

            if result.need_confirm:
                if result.choice:
                    choice = ui.choice("提示", result.message)
                    if choice == 0:
                        return False
                    elif choice == 2:
                        ctx.need_switch = True
                else:
                    if not ui.confirm("提示", result.message):
                        return False

        return True

    def _pre_check(self, ctx: PosStartContext, ui):
        if not os.path.exists(ctx.path):
            ui.error("POS文件不存在")
            return False

        LocalEnvRule().apply(ctx)

        kill_process_by_name("CPOS-DF.exe")
        return True

    def _env_decision(self, ctx: PosStartContext, ui):

        if ctx.is_uat:
            if not ctx.has_local:
                return ui.confirm("提示", "当前是UAT环境，没有本地配置，直接启动？")

            elif not ctx.has_remote and not ctx.start_config.change_pos:
                return ui.confirm(
                    "提示", "当前是UAT环境，没获取到服务端配置，直接启动？"
                )

        else:
            if not ctx.has_local and not ctx.has_remote:
                return ui.confirm("提示", "没有本地配置和服务端配置，继续启动？")

            elif not ctx.has_remote and not ctx.start_config.change_pos:
                return ui.confirm(
                    "提示", f"没获取到服务端配置，直接启动？\n{ctx.remote_info}"
                )

            elif not ctx.has_local:
                return ui.confirm("提示", "没获取到本地配置，直接启动？")

        return True

    def _consistency_check(self, ctx: PosStartContext, ui):

        if ctx.start_config.change_pos and ctx.has_local:
            ctx.need_switch = True
            return True

        elif ctx.has_local and ctx.has_remote:
            if ctx.is_mismatch():
                choice = ui.choice("提示", "本地和服务端配置不一致，继续启动？")

                if choice == 0:
                    return False
                elif choice == 2:
                    ctx.need_switch = True

        return True
