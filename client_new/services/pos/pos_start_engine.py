# pos_start_engine.py
import os

from loguru import logger

from services.pos.rules.local_env_rule import LocalEnvRule
from utils.common import get_process_by_name, kill_process_by_name

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

        # 阶段4：启动动作依赖检查（缺 pos_params 时依赖动作只能提示跳过，不能阻断）
        if not self._dependent_action_check(ctx, ui):
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

        # 缺 pos.ini 时环境完全未知（pos_init 会兜底打到 test 地址），硬阻断；
        # 该检查必须在杀进程之前，避免注定要拒绝的请求先杀掉运行中的 POS
        local_env_rule_result = LocalEnvRule().apply(ctx)
        if not local_env_rule_result.continue_flow:
            logger.warning(f"启动前检查未通过: {ctx.path}, {local_env_rule_result.message}")
            ui.error(local_env_rule_result.message)
            return False

        # 先判断是否真有进程再杀，并记录标志：用户随后取消启动时需要提示已杀进程
        if get_process_by_name("CPOS-DF.exe"):
            kill_process_by_name("CPOS-DF.exe")
            ctx.killed_running = True
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
                choice = ui.choice(
                    "提示",
                    f"本地和服务端配置不一致，继续启动？\n{ctx.local_env_info}\n{ctx.remote_info}",
                )

                if choice == 0:
                    return False
                elif choice == 2:
                    ctx.need_switch = True

        return True

    def _dependent_action_check(self, ctx: PosStartContext, ui):
        """
        检查勾选的启动动作是否依赖本地 pos_params。

        切换云端POS/退出登录需要从本地 pos_params 取商家、门店、环境分组等参数，
        缺 pos_params 时这两个动作无法执行。按产品约束缺 pos_params 不允许阻断启动，
        因此弹出确认：用户确认后跳过这些动作继续启动，取消则中止本次启动。
        """
        if ctx.has_local or ctx.skip_dependent_actions:
            return True

        need_skip = []
        if ctx.start_config.change_pos:
            need_skip.append("切换云端POS")
        if ctx.start_config.account_logout:
            need_skip.append("退出登录")

        if not need_skip:
            return True

        skip_names = "、".join(need_skip)
        if not ui.confirm(
            "提示",
            f"缺少本地POS参数（pos_params），无法执行【{skip_names}】，"
            f"是否跳过该动作并继续启动？",
        ):
            return False

        ctx.skip_dependent_actions = True
        logger.info(
            f"缺本地pos_params，用户确认跳过启动动作: {skip_names}, posPath={ctx.path}"
        )
        return True
