from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from model.config import AgentBrowserConfigModel
from server.config import AgentConfig

InstallStatusCallback = Callable[[str], None]


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
_INSTALL_EVENT_LOCK = threading.Lock()
_INSTALL_EVENT_LISTENERS: set[InstallStatusCallback] = set()
_PERCENT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d+)?)%")


def add_install_event_listener(listener: InstallStatusCallback) -> None:
    """
    注册 Playwright 浏览器安装日志监听器。

    :param listener: 日志回调，参数为单行文本消息。
    """
    if listener is None:
        return
    with _INSTALL_EVENT_LOCK:
        _INSTALL_EVENT_LISTENERS.add(listener)


def remove_install_event_listener(listener: InstallStatusCallback) -> None:
    """
    移除 Playwright 浏览器安装日志监听器。

    :param listener: 已注册的日志回调。
    """
    if listener is None:
        return
    with _INSTALL_EVENT_LOCK:
        _INSTALL_EVENT_LISTENERS.discard(listener)


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
        raise RuntimeError(
            f"unsupported browser: {browser_name}, supported: {supported}"
        )
    return spec


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _pick_first_non_empty_text(*values: Any) -> str:
    """
    从候选值中挑选第一个非空文本。

    :param values: 待选择的候选值，支持任意类型。
    :return: 去除首尾空白后的第一个非空字符串，若均为空则返回空字符串。
    """
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _resolve_download_settings(
    browser_config: AgentBrowserConfigModel,
    request_options: dict[str, Any],
) -> tuple[str, str]:
    """
    解析 Playwright 下载源与下载代理设置。

    :param browser_config: Agent 浏览器本地配置。
    :param request_options: 本次请求的运行时覆盖参数。
    :return: (download_host, download_proxy)。
    """
    download_host = _pick_first_non_empty_text(
        request_options.get("playwrightDownloadHost"),
        request_options.get("downloadHost"),
        request_options.get("browserDownloadHost"),
        request_options.get("playwright_download_host"),
        getattr(browser_config, "playwright_download_host", ""),
    )
    download_proxy = _pick_first_non_empty_text(
        request_options.get("playwrightDownloadProxy"),
        request_options.get("downloadProxy"),
        request_options.get("httpProxy"),
        request_options.get("proxy"),
        request_options.get("playwright_download_proxy"),
        getattr(browser_config, "playwright_download_proxy", ""),
    )
    return download_host, download_proxy


def _build_download_env(download_host: str, download_proxy: str) -> dict[str, str]:
    """
    构建 Playwright 下载相关环境变量。

    :param download_host: 浏览器下载源地址。
    :param download_proxy: 下载代理地址。
    :return: 可直接注入 subprocess 的环境变量字典。
    """
    env: dict[str, str] = {}
    resolved_host = str(download_host or "").strip().rstrip("/")
    resolved_proxy = str(download_proxy or "").strip()

    if resolved_host:
        env["PLAYWRIGHT_DOWNLOAD_HOST"] = resolved_host
    if resolved_proxy:
        env["HTTPS_PROXY"] = resolved_proxy
        env["HTTP_PROXY"] = resolved_proxy
        env["ALL_PROXY"] = resolved_proxy
        env["https_proxy"] = resolved_proxy
        env["http_proxy"] = resolved_proxy
        env["all_proxy"] = resolved_proxy
    return env


def _list_install_event_listeners() -> list[InstallStatusCallback]:
    """
    获取当前安装日志监听器快照。

    :return: 监听器列表副本，避免遍历过程中被并发修改。
    """
    with _INSTALL_EVENT_LOCK:
        return list(_INSTALL_EVENT_LISTENERS)


def _emit_install_status(
    message: str, *, callback: InstallStatusCallback | None = None
) -> None:
    """
    广播安装状态日志。

    :param message: 日志内容。
    :param callback: 当前调用链附带的临时回调。
    """
    text = str(message or "").strip()
    if not text:
        return

    logger.info(f"[PlaywrightInstall] {text}")
    if callback is not None:
        try:
            callback(text)
        except Exception as exc:
            logger.warning(f"安装日志回调执行失败: {exc}")

    for listener in _list_install_event_listeners():
        try:
            listener(text)
        except Exception as exc:
            logger.warning(f"安装日志监听器执行失败: {exc}")


def _resolve_proxy_text(env: dict[str, str]) -> str:
    """
    解析安装命令最终使用的代理文本。

    :param env: 安装命令环境变量。
    :return: 代理地址，未配置时返回空字符串。
    """
    return _pick_first_non_empty_text(
        env.get("HTTPS_PROXY"),
        env.get("HTTP_PROXY"),
        env.get("ALL_PROXY"),
        env.get("https_proxy"),
        env.get("http_proxy"),
        env.get("all_proxy"),
    )


def _extract_progress_percent(line: str) -> str:
    """
    从日志行中提取百分比进度。

    :param line: 单行安装输出。
    :return: 形如 `23%` 的进度文本，未匹配时返回空字符串。
    """
    match = _PERCENT_PATTERN.search(str(line or ""))
    if not match:
        return ""
    try:
        value = float(match.group(1))
    except Exception:
        return ""
    value = max(0.0, min(value, 100.0))
    if abs(value - int(value)) < 0.001:
        return f"{int(value)}%"
    return f"{value:.1f}%"


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
    download_host, download_proxy = _resolve_download_settings(browser_config, options)
    download_env = _build_download_env(download_host, download_proxy)

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
    install_env.update(download_env)
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
        raise RuntimeError("playwright Python 包未安装，无法执行 Web 操作") from exc
    return getattr(module, "async_playwright")


def _compute_playwright_driver_command() -> tuple[str, str]:
    try:
        driver_module = importlib.import_module("playwright._impl._driver")
    except Exception as exc:
        raise RuntimeError("未找到 Playwright 驱动，无法自动安装浏览器") from exc

    compute_driver_executable = getattr(
        driver_module, "compute_driver_executable", None
    )
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


def _summarize_install_lines(lines: list[str]) -> str:
    """
    截取安装输出摘要，便于错误提示展示。

    :param lines: 安装输出行列表。
    :return: 最后 20 行非空文本摘要。
    """
    normalized_lines = [
        str(line or "").strip() for line in lines if str(line or "").strip()
    ]
    if not normalized_lines:
        return ""
    return "\n".join(normalized_lines[-20:])


def _run_install_command(
    command: list[str],
    env: dict[str, str],
    *,
    status_callback: InstallStatusCallback | None = None,
) -> None:
    """
    执行 Playwright 浏览器安装命令，并实时输出下载日志。

    :param command: 安装命令参数列表。
    :param env: 子进程环境变量。
    :param status_callback: 状态回调，用于上报实时日志。
    """
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=creationflags,
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("Playwright 安装进程未返回标准输出句柄")

    output_lines: list[str] = []
    last_percent = ""
    for raw_line in iter(process.stdout.readline, ""):
        text = str(raw_line or "").replace("\r", "\n")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            output_lines.append(stripped)
            percent = _extract_progress_percent(stripped)
            if percent and percent != last_percent:
                last_percent = percent
                _emit_install_status(f"下载进度: {percent}", callback=status_callback)
            _emit_install_status(stripped, callback=status_callback)

    process.stdout.close()
    return_code = process.wait()
    if return_code == 0:
        return

    summary = _summarize_install_lines(output_lines)
    if summary:
        raise RuntimeError(f"Playwright 浏览器安装失败:\n{summary}")
    raise RuntimeError(f"Playwright 浏览器安装失败，退出码: {return_code}")


async def _install_browser(
    plan: BrowserLaunchPlan,
    *,
    status_callback: InstallStatusCallback | None = None,
) -> None:
    """
    安装指定 Playwright 浏览器，并输出关键环境信息。

    :param plan: 浏览器安装计划。
    :param status_callback: 状态回调，用于上报实时日志。
    """
    node_path, cli_path = _compute_playwright_driver_command()
    plan.install_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(plan.install_env)
    command = [node_path, cli_path, "install", plan.install_name]
    resolved_download_host = str(
        plan.install_env.get("PLAYWRIGHT_DOWNLOAD_HOST") or ""
    ).strip()
    resolved_proxy = _resolve_proxy_text(plan.install_env)

    async with _INSTALL_LOCK:
        _emit_install_status(
            f"开始安装浏览器: {plan.install_name}",
            callback=status_callback,
        )
        _emit_install_status(
            f"安装目录: {plan.install_dir}",
            callback=status_callback,
        )
        _emit_install_status(
            f"下载源: {resolved_download_host or 'Playwright 默认源'}",
            callback=status_callback,
        )
        _emit_install_status(
            f"代理: {resolved_proxy or '未使用'}",
            callback=status_callback,
        )
        await asyncio.to_thread(
            _run_install_command,
            command,
            env,
            status_callback=status_callback,
        )
        _emit_install_status(
            f"浏览器安装完成: {plan.install_name}",
            callback=status_callback,
        )


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
    launch_kwargs["args"] = ["--window-size=1920,1080"]
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
    status_callback: InstallStatusCallback | None = None,
) -> tuple[Any, Any]:
    """
    启动 Playwright 浏览器；必要时自动安装缺失浏览器。

    :param browser_name: 浏览器名称（chromium/firefox/webkit/chrome/msedge）。
    :param headless: 是否无头模式启动。
    :param request_options: 运行时覆盖参数（安装目录、下载源、代理等）。
    :param status_callback: 安装阶段状态回调。
    :return: (playwright, browser) 对象元组。
    """
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

        await _install_browser(plan, status_callback=status_callback)

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


async def install_playwright_browser(
    browser_name: str | None,
    *,
    request_options: dict[str, Any] | None = None,
    status_callback: InstallStatusCallback | None = None,
) -> None:
    """
    按配置手动安装指定 Playwright 浏览器。

    :param browser_name: 浏览器名称（留空默认 chromium）。
    :param request_options: 运行时覆盖参数（安装目录、下载源、代理等）。
    :param status_callback: 安装阶段状态回调。
    """
    plan = _build_launch_plan(browser_name, request_options=request_options)
    await _install_browser(plan, status_callback=status_callback)


def install_playwright_browser_sync(
    browser_name: str | None,
    *,
    request_options: dict[str, Any] | None = None,
    status_callback: InstallStatusCallback | None = None,
) -> None:
    """
    同步方式安装指定 Playwright 浏览器。

    :param browser_name: 浏览器名称（留空默认 chromium）。
    :param request_options: 运行时覆盖参数（安装目录、下载源、代理等）。
    :param status_callback: 安装阶段状态回调。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "当前线程已有事件循环，请使用异步接口 install_playwright_browser"
        )

    asyncio.run(
        install_playwright_browser(
            browser_name,
            request_options=request_options,
            status_callback=status_callback,
        )
    )
