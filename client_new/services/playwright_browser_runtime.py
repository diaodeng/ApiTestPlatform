from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from model.config import AgentBrowserConfigModel
from server.config import AgentConfig


@dataclass(frozen=True)
class BrowserSpec:
    requested_name: str
    launcher_name: str
    install_name: str
    config_key: str
    channel: str | None = None


@dataclass(frozen=True)
class BrowserLaunchPlan:
    browser_name: str
    launcher_name: str
    install_name: str
    launch_kwargs: dict[str, Any]
    auto_install: bool
    install_dir: Path
    initial_env: dict[str, str]
    install_env: dict[str, str]
    manual_executable_path: Path | None = None


_BROWSER_SPECS = {
    "chromium": BrowserSpec(
        requested_name="chromium",
        launcher_name="chromium",
        install_name="chromium",
        config_key="chromium",
    ),
    "chrome": BrowserSpec(
        requested_name="chrome",
        launcher_name="chromium",
        install_name="chrome",
        config_key="chromium",
        channel="chrome",
    ),
    "msedge": BrowserSpec(
        requested_name="msedge",
        launcher_name="chromium",
        install_name="msedge",
        config_key="chromium",
        channel="msedge",
    ),
    "firefox": BrowserSpec(
        requested_name="firefox",
        launcher_name="firefox",
        install_name="firefox",
        config_key="firefox",
    ),
    "webkit": BrowserSpec(
        requested_name="webkit",
        launcher_name="webkit",
        install_name="webkit",
        config_key="webkit",
    ),
}

_INSTALL_LOCK = asyncio.Lock()


def get_client_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_default_playwright_install_dir() -> Path:
    return get_client_root_dir() / "storage" / "runtime" / "playwright-browsers"


def _read_browser_config() -> AgentBrowserConfigModel:
    try:
        config = AgentConfig.read_config()
        browser = getattr(config, "browser", None)
        if isinstance(browser, AgentBrowserConfigModel):
            return browser
        if isinstance(browser, dict):
            return AgentBrowserConfigModel.model_validate(browser)
    except Exception as exc:
        logger.warning(f"读取 Agent 浏览器配置失败，使用默认配置: {exc}")
    return AgentBrowserConfigModel()


def _normalize_browser_name(browser_name: str | None) -> str:
    normalized = str(browser_name or "chromium").strip().lower()
    if not normalized:
        return "chromium"
    return normalized


def _resolve_browser_spec(browser_name: str | None) -> BrowserSpec:
    normalized = _normalize_browser_name(browser_name)
    spec = _BROWSER_SPECS.get(normalized)
    if spec is None:
        supported = ", ".join(sorted(_BROWSER_SPECS))
        raise RuntimeError(f"unsupported browser: {browser_name}, supported: {supported}")
    return spec


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _resolve_path(raw_value: Any, *, base_dir: Path) -> Path | None:
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _resolve_manual_executable_path(
    spec: BrowserSpec,
    browser_config: AgentBrowserConfigModel,
    request_options: dict[str, Any],
    *,
    base_dir: Path,
) -> Path | None:
    per_browser_key = f"{spec.config_key}ExecutablePath"
    config_key = f"{spec.config_key}_executable_path"
    raw_value = (
        request_options.get("browserExecutablePath")
        or request_options.get(per_browser_key)
        or getattr(browser_config, config_key, "")
    )
    executable_path = _resolve_path(raw_value, base_dir=base_dir)
    if executable_path is None:
        return None
    if not executable_path.exists():
        raise RuntimeError(f"浏览器可执行文件不存在: {executable_path}")
    if executable_path.is_dir():
        raise RuntimeError(f"浏览器可执行文件不能是目录: {executable_path}")
    return executable_path


def _build_launch_plan(
    browser_name: str | None,
    request_options: dict[str, Any] | None = None,
) -> BrowserLaunchPlan:
    options = request_options or {}
    spec = _resolve_browser_spec(browser_name)
    browser_config = _read_browser_config()
    client_root = get_client_root_dir()

    auto_install = _parse_bool(
        options.get("autoInstallBrowser"),
        browser_config.auto_install,
    )

    custom_install_dir = _resolve_path(
        options.get("browserInstallDir") or browser_config.install_dir,
        base_dir=client_root,
    )
    install_dir = custom_install_dir or get_default_playwright_install_dir()
    manual_executable_path = _resolve_manual_executable_path(
        spec,
        browser_config,
        options,
        base_dir=client_root,
    )

    launch_kwargs: dict[str, Any] = {}
    if manual_executable_path is not None:
        launch_kwargs["executable_path"] = str(manual_executable_path)
    elif spec.channel:
        launch_kwargs["channel"] = spec.channel

    initial_env: dict[str, str] = {}
    if custom_install_dir is not None:
        initial_env["PLAYWRIGHT_BROWSERS_PATH"] = str(custom_install_dir)

    install_env = {"PLAYWRIGHT_BROWSERS_PATH": str(install_dir)}
    return BrowserLaunchPlan(
        browser_name=spec.requested_name,
        launcher_name=spec.launcher_name,
        install_name=spec.install_name,
        launch_kwargs=launch_kwargs,
        auto_install=auto_install,
        install_dir=install_dir,
        initial_env=initial_env,
        install_env=install_env,
        manual_executable_path=manual_executable_path,
    )


def _load_async_playwright_factory():
    try:
        module = importlib.import_module("playwright.async_api")
    except Exception as exc:
        raise RuntimeError(
            "playwright Python 包未安装，无法执行 Web 操作"
        ) from exc
    return getattr(module, "async_playwright")


def _compute_playwright_driver_command() -> tuple[str, str]:
    try:
        driver_module = importlib.import_module("playwright._impl._driver")
    except Exception as exc:
        raise RuntimeError("未找到 Playwright 驱动，无法自动安装浏览器") from exc

    compute_driver_executable = getattr(driver_module, "compute_driver_executable", None)
    if compute_driver_executable is None:
        raise RuntimeError("当前 Playwright 版本缺少 driver 安装入口")

    node_path, cli_path = compute_driver_executable()
    node = Path(node_path)
    cli = Path(cli_path)
    if not node.exists():
        raise RuntimeError(f"Playwright node 驱动不存在: {node}")
    if not cli.exists():
        raise RuntimeError(f"Playwright cli 不存在: {cli}")
    return str(node), str(cli)


def _needs_browser_install(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "executable doesn't exist" in message
        or "please run the following command" in message
    )


def _summarize_subprocess_output(stdout: str, stderr: str) -> str:
    lines = []
    if stdout:
        lines.extend(stdout.strip().splitlines())
    if stderr:
        lines.extend(stderr.strip().splitlines())
    lines = [line.strip() for line in lines if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-20:])


def _run_install_command(command: list[str], env: dict[str, str]) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=creationflags,
        check=False,
    )
    if result.returncode == 0:
        return

    summary = _summarize_subprocess_output(result.stdout, result.stderr)
    if summary:
        raise RuntimeError(f"Playwright 浏览器安装失败:\n{summary}")
    raise RuntimeError(
        f"Playwright 浏览器安装失败，退出码: {result.returncode}"
    )


async def _install_browser(plan: BrowserLaunchPlan) -> None:
    node_path, cli_path = _compute_playwright_driver_command()
    plan.install_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(plan.install_env)
    command = [node_path, cli_path, "install", plan.install_name]

    async with _INSTALL_LOCK:
        logger.info(
            f"Playwright 浏览器缺失，开始自动安装: {plan.install_name}, 目录: {plan.install_dir}"
        )
        await asyncio.to_thread(_run_install_command, command, env)


@contextlib.contextmanager
def _temporary_environment(updates: dict[str, str]):
    old_values: dict[str, str | None] = {}
    try:
        for key, value in updates.items():
            old_values[key] = os.environ.get(key)
            os.environ[key] = value
        yield
    finally:
        for key, old_value in old_values.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


async def _start_playwright(async_playwright_factory, env_updates: dict[str, str]):
    with _temporary_environment(env_updates):
        return await async_playwright_factory().start()


async def _launch_browser_instance(
    playwright: Any,
    plan: BrowserLaunchPlan,
    *,
    headless: bool,
) -> Any:
    launcher = getattr(playwright, plan.launcher_name, None)
    if launcher is None:
        raise RuntimeError(f"unsupported browser launcher: {plan.launcher_name}")

    launch_kwargs = dict(plan.launch_kwargs)
    launch_kwargs["headless"] = headless
    return await launcher.launch(**launch_kwargs)


def _build_launch_error(plan: BrowserLaunchPlan, exc: Exception) -> RuntimeError:
    if plan.manual_executable_path is not None:
        return RuntimeError(
            f"{plan.browser_name} 浏览器启动失败，请检查手动配置的可执行文件: "
            f"{plan.manual_executable_path}\n{exc}"
        )

    if _needs_browser_install(exc) and not plan.auto_install:
        return RuntimeError(
            f"{plan.browser_name} 浏览器未安装。请启用自动安装，或在 Agent 浏览器设置中手动配置已安装浏览器路径。"
        )

    return RuntimeError(f"{plan.browser_name} 浏览器启动失败: {exc}")


async def start_playwright_browser(
    browser_name: str | None,
    *,
    headless: bool,
    request_options: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    async_playwright_factory = _load_async_playwright_factory()
    plan = _build_launch_plan(browser_name, request_options=request_options)

    playwright = await _start_playwright(async_playwright_factory, plan.initial_env)
    try:
        browser = await _launch_browser_instance(
            playwright,
            plan,
            headless=headless,
        )
        return playwright, browser
    except Exception as exc:
        await playwright.stop()
        if (
            plan.manual_executable_path is not None
            or not plan.auto_install
            or not _needs_browser_install(exc)
        ):
            raise _build_launch_error(plan, exc) from exc

        await _install_browser(plan)

    playwright = await _start_playwright(async_playwright_factory, plan.install_env)
    try:
        browser = await _launch_browser_instance(
            playwright,
            plan,
            headless=headless,
        )
        return playwright, browser
    except Exception as exc:
        await playwright.stop()
        raise _build_launch_error(plan, exc) from exc
