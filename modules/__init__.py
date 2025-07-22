"""
本地提示词管理软件 - 模块包

提供配置管理、项目初始化等核心功能
"""

from .config_manager import (
    ConfigManager, 
    GlobalConfigManager, 
    HotkeyConfigManager
)
from .project_initializer import (
    ProjectInitializer,
    initialize_on_startup
)

__all__ = [
    'ConfigManager',
    'GlobalConfigManager', 
    'HotkeyConfigManager',
    'ProjectInitializer',
    'initialize_on_startup'
] 