"""Gitee release 查询工具：主程序更新检查（utils/common）与插件在线下载（plugins/manager）共用。

统一维护 release API 地址、版本号归一化和 release/附件定位逻辑，
避免两处硬编码同一 URL 或版本比较规则各自漂移。
"""

import re

import httpx

from utils.http_defaults import DEFAULT_HTTP_TIMEOUT

# Gitee releases 列表接口（公开仓库免鉴权），按创建时间倒序
GITEE_RELEASES_API_URL = (
    "https://gitee.com/api/v5/repos/panda26/api-test-platform/releases"
    "?page=1&per_page=20&direction=desc"
)


def normalize_release_version(value: str | None) -> tuple[int, ...]:
    """
    把版本号/标签归一化为纯数字元组，兼容 v1.2.3.4、1.2.3.4 等写法。
    :param value: 版本号或 tag 名
    :return: 数字元组，无数字时返回 (0,)
    """
    parts = re.findall(r"\d+", str(value or ""))
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts)


async def fetch_release_list() -> list[dict]:
    """
    异步拉取 Gitee releases 列表（主程序更新检查使用，跑在事件循环中）。
    :return: release 字典列表，返回格式异常时抛出 RuntimeError
    """
    async with httpx.AsyncClient(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = await client.get(GITEE_RELEASES_API_URL)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("版本接口返回格式异常")
    return data


def fetch_release_list_sync() -> list[dict]:
    """
    同步拉取 Gitee releases 列表（插件在线下载使用，跑在后台线程）。
    :return: release 字典列表，返回格式异常时抛出 RuntimeError
    """
    with httpx.Client(
        timeout=DEFAULT_HTTP_TIMEOUT,
        follow_redirects=True,
    ) as client:
        response = client.get(GITEE_RELEASES_API_URL)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        raise RuntimeError("版本接口返回格式异常")
    return data


def find_release_by_version(
    releases: list[dict], app_version: str
) -> dict | None:
    """
    按 tag 名与客户端版本号归一化后精确匹配，定位对应 release。
    :param releases: release 字典列表
    :param app_version: 当前客户端版本号（如 1.1.1.0）
    :return: 匹配的 release，找不到返回 None
    """
    target = normalize_release_version(app_version)
    for release in releases:
        tag = str(release.get("tag_name") or "").strip()
        if tag and normalize_release_version(tag) == target:
            return release
    return None


def find_release_asset(release: dict, asset_name: str) -> dict | None:
    """
    在 release 附件中按文件名精确定位附件。
    :param release: release 字典
    :param asset_name: 附件文件名（如 desktop-test.zip）
    :return: 附件字典（含 browser_download_url），找不到返回 None
    """
    assets = release.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if str(asset.get("name") or "").strip() == asset_name:
            return asset
    return None
