"""
配置管理模块测试

测试 config_manager.py 模块的核心功能
"""

import pytest
import tempfile
import yaml
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.config_manager import ConfigManager, GlobalConfigManager, HotkeyConfigManager


class TestConfigManager:
    """ConfigManager基础类测试"""
    
    def test_config_manager_init(self):
        """测试配置管理器初始化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            manager = ConfigManager(config_path)
            
            assert manager.config_path == config_path
            assert manager.config_data == {}
            assert not manager._is_watching
            
    def test_save_and_load_config(self):
        """测试配置保存和加载"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            manager = ConfigManager(config_path)
            
            # 保存测试数据
            test_data = {
                'test_key': 'test_value',
                'nested': {
                    'key': 'value'
                }
            }
            manager.save_config(test_data)
            
            # 验证文件存在
            assert config_path.exists()
            
            # 重新加载并验证
            loaded_data = manager.load_config()
            assert loaded_data == test_data
            
    def test_get_and_set_methods(self):
        """测试配置项的获取和设置"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            manager = ConfigManager(config_path)
            
            # 设置配置项
            manager.set('simple_key', 'simple_value')
            manager.set('nested.key', 'nested_value')
            
            # 获取配置项
            assert manager.get('simple_key') == 'simple_value'
            assert manager.get('nested.key') == 'nested_value'
            assert manager.get('nonexistent', 'default') == 'default'


class TestGlobalConfigManager:
    """GlobalConfigManager测试"""
    
    def test_global_config_creation(self):
        """测试全局配置的创建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GlobalConfigManager(temp_dir)
            manager.load_config()
            
            # 验证默认配置项存在
            assert manager.get('api.deepseek.base_url') is not None
            assert manager.get('api.kimi.base_url') is not None
            assert manager.get('logging.level') is not None
            
    def test_api_key_methods(self):
        """测试API密钥相关方法"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GlobalConfigManager(temp_dir)
            manager.load_config()
            
            # 设置API密钥
            test_key = 'sk-test123'
            manager.set_api_key('deepseek', test_key)
            
            # 获取API密钥
            assert manager.get_api_key('deepseek') == test_key
            
    def test_config_validation(self):
        """测试配置验证"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GlobalConfigManager(temp_dir)
            manager.load_config()
            
            # 默认配置应该通过验证
            assert manager.validate_config() == True


class TestHotkeyConfigManager:
    """HotkeyConfigManager测试"""
    
    def test_hotkey_config_creation(self):
        """测试快捷键配置的创建"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = HotkeyConfigManager(temp_dir)
            manager.load_config()
            
            # 验证默认配置项存在
            hotkeys = manager.get_all_mappings()
            assert len(hotkeys) == 9  # 应该有9个快捷键
            assert manager.get('settings.enabled') == True
            
    def test_hotkey_mapping_methods(self):
        """测试快捷键映射相关方法"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = HotkeyConfigManager(temp_dir)
            manager.load_config()
            
            # 测试获取模板
            template = manager.get_template_for_hotkey('ctrl+alt+cmd+1')
            assert template == 'template1.md'
            
            # 测试设置映射
            manager.set_hotkey_mapping('ctrl+alt+cmd+1', 'new_template.md')
            assert manager.get_template_for_hotkey('ctrl+alt+cmd+1') == 'new_template.md'
            
    def test_hotkey_config_validation(self):
        """测试快捷键配置验证"""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = HotkeyConfigManager(temp_dir)
            manager.load_config()
            
            # 默认配置应该通过验证
            assert manager.validate_config() == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 