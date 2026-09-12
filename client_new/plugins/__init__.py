"""插件化基础设施包：重依赖按插件包按需安装与激活。"""

from plugins.manager import (
    PLUGIN_DEFINITIONS,
    plugin_manager,
)

__all__ = ["PLUGIN_DEFINITIONS", "plugin_manager"]
