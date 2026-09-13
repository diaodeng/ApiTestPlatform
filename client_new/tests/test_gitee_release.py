"""
验证 Gitee release 定位工具：版本归一化、按客户端版本匹配 release、按文件名定位附件。

纯函数测试，不发真实网络请求；plugins/manager 的下载源回退链路依赖这三个函数。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.gitee_release import (
    find_release_asset,
    find_release_by_version,
    normalize_release_version,
)


def test_normalize_release_version():
    # 兼容 v 前缀与纯数字版本
    assert normalize_release_version("v1.1.1.0") == (1, 1, 1, 0)
    assert normalize_release_version("1.1.1.0") == (1, 1, 1, 0)
    # 空值与无数字内容回退 (0,)
    assert normalize_release_version(None) == (0,)
    assert normalize_release_version("") == (0,)
    assert normalize_release_version("latest") == (0,)


def test_find_release_by_version():
    releases = [
        {"tag_name": "v1.1.2.0", "assets": []},
        {"tag_name": "v1.1.1.0", "assets": []},
        {"tag_name": "v1.1.0.0", "assets": []},
    ]
    matched = find_release_by_version(releases, "1.1.1.0")
    assert matched is not None and matched["tag_name"] == "v1.1.1.0"
    # 找不到时返回 None
    assert find_release_by_version(releases, "9.9.9.9") is None
    assert find_release_by_version([], "1.1.1.0") is None
    # tag 缺失的 release 不参与匹配
    assert find_release_by_version([{"assets": []}], "1.1.1.0") is None


def test_find_release_asset():
    release = {
        "tag_name": "v1.1.1.0",
        "assets": [
            {"name": "QTRClientNew.zip", "browser_download_url": "https://gitee.com/a.zip"},
            {"name": "desktop-test.zip", "browser_download_url": "https://gitee.com/dt.zip"},
            {
                "name": "desktop-test.zip.sha256",
                "browser_download_url": "https://gitee.com/dt.zip.sha256",
            },
        ],
    }
    asset = find_release_asset(release, "desktop-test.zip")
    assert asset is not None and asset["browser_download_url"] == "https://gitee.com/dt.zip"
    sha = find_release_asset(release, "desktop-test.zip.sha256")
    assert sha is not None
    # 附件缺失 / assets 结构异常时返回 None
    assert find_release_asset(release, "web-test.zip") is None
    assert find_release_asset({"tag_name": "v1"}, "desktop-test.zip") is None
    assert find_release_asset({"assets": "bad"}, "desktop-test.zip") is None


def main():
    test_normalize_release_version()
    test_find_release_by_version()
    test_find_release_asset()
    print("[ALL PASS] gitee_release 工具函数验证通过")


if __name__ == "__main__":
    main()
