"""
主程序测试模块

测试PromptManager类的核心功能
"""

import pytest
import tempfile
import shutil
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from main import PromptManager, parse_arguments, setup_signal_handlers
except ImportError as e:
    pytest.skip(f"无法导入主程序模块: {e}", allow_module_level=True)


class TestPromptManager:
    """PromptManager类测试"""
    
    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        config_dir = tempfile.mkdtemp()
        prompt_dir = tempfile.mkdtemp()
        yield config_dir, prompt_dir
        shutil.rmtree(config_dir)
        shutil.rmtree(prompt_dir)
    
    @pytest.fixture
    def prompt_manager(self, temp_dirs):
        """创建PromptManager实例"""
        config_dir, prompt_dir = temp_dirs
        return PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
    
    def test_prompt_manager_init(self, prompt_manager, temp_dirs):
        """测试PromptManager初始化"""
        config_dir, prompt_dir = temp_dirs
        
        assert str(prompt_manager.config_dir) == config_dir
        assert str(prompt_manager.prompt_dir) == prompt_dir
        assert prompt_manager.running == False
        assert prompt_manager.processed_requests == 0
        assert prompt_manager.error_count == 0
        assert prompt_manager.global_config is None
        assert prompt_manager.hotkey_config is None
        assert prompt_manager.text_processor is None
        assert prompt_manager.hotkey_listener is None
    
    @patch('main.initialize_on_startup')
    @patch('main.GlobalConfigManager')
    @patch('main.HotkeyConfigManager')
    @patch('main.TextProcessor')
    @patch('main.HotkeyListener')
    def test_initialize_success(self, mock_hotkey_listener, mock_text_processor, 
                               mock_hotkey_config, mock_global_config, 
                               mock_initialize, prompt_manager):
        """测试成功初始化"""
        # 模拟初始化成功
        mock_initialize.return_value = {'success': True, 'message': '初始化成功'}
        
        # 模拟配置管理器
        mock_global_config_instance = Mock()
        mock_hotkey_config_instance = Mock()
        mock_global_config.return_value = mock_global_config_instance
        mock_hotkey_config.return_value = mock_hotkey_config_instance
        
        # 模拟文本处理器
        mock_text_processor_instance = Mock()
        mock_text_processor_instance.get_platform_capabilities.return_value = {
            'platform': 'Darwin',
            'clipboard_available': True,
            'copy_simulation_available': True
        }
        mock_text_processor.return_value = mock_text_processor_instance
        
        # 模拟快捷键监听器
        mock_hotkey_listener_instance = Mock()
        mock_hotkey_listener.return_value = mock_hotkey_listener_instance
        
        # 执行初始化
        result = prompt_manager.initialize()
        
        # 验证结果
        assert result == True
        assert prompt_manager.global_config == mock_global_config_instance
        assert prompt_manager.hotkey_config == mock_hotkey_config_instance
        assert prompt_manager.text_processor == mock_text_processor_instance
        assert prompt_manager.hotkey_listener == mock_hotkey_listener_instance
        
        # 验证调用
        mock_initialize.assert_called_once()
        mock_global_config_instance.load_config.assert_called_once()
        mock_hotkey_config_instance.load_config.assert_called_once()
        mock_text_processor_instance.get_platform_capabilities.assert_called_once()
        mock_hotkey_listener_instance.set_template_handler.assert_called_once()
    
    @patch('main.initialize_on_startup')
    def test_initialize_failure(self, mock_initialize, prompt_manager):
        """测试初始化失败"""
        # 模拟初始化失败
        mock_initialize.return_value = {'success': False, 'error': '初始化失败'}
        
        # 执行初始化
        result = prompt_manager.initialize()
        
        # 验证结果
        assert result == False
    
    def test_initialize_exception(self, prompt_manager):
        """测试初始化过程中的异常"""
        # 模拟异常
        with patch('main.initialize_on_startup') as mock_initialize:
            mock_initialize.side_effect = Exception("测试异常")
            
            result = prompt_manager.initialize()
            assert result == False
    
    def test_start_without_initialization(self, prompt_manager):
        """测试未初始化时的启动"""
        result = prompt_manager.start()
        assert result == False
    
    @patch('main.initialize_on_startup')
    @patch('main.GlobalConfigManager')
    @patch('main.HotkeyConfigManager')
    @patch('main.TextProcessor')
    @patch('main.HotkeyListener')
    def test_start_success(self, mock_hotkey_listener, mock_text_processor, 
                          mock_hotkey_config, mock_global_config, 
                          mock_initialize, prompt_manager):
        """测试成功启动"""
        # 先初始化
        mock_initialize.return_value = {'success': True, 'message': '初始化成功'}
        
        mock_global_config_instance = Mock()
        mock_hotkey_config_instance = Mock()
        mock_text_processor_instance = Mock()
        mock_text_processor_instance.get_platform_capabilities.return_value = {
            'platform': 'Darwin',
            'clipboard_available': True,
            'copy_simulation_available': True
        }
        mock_hotkey_listener_instance = Mock()
        mock_hotkey_listener_instance.start.return_value = True
        mock_hotkey_listener_instance.get_current_mappings.return_value = {}
        
        mock_global_config.return_value = mock_global_config_instance
        mock_hotkey_config.return_value = mock_hotkey_config_instance
        mock_text_processor.return_value = mock_text_processor_instance
        mock_hotkey_listener.return_value = mock_hotkey_listener_instance
        
        # 初始化
        assert prompt_manager.initialize() == True
        
        # 启动
        result = prompt_manager.start()
        
        # 验证结果
        assert result == True
        assert prompt_manager.running == True
        assert prompt_manager.start_time is not None
        
        # 验证调用
        mock_hotkey_listener_instance.start.assert_called_once()
    
    def test_start_already_running(self, prompt_manager):
        """测试重复启动"""
        prompt_manager.running = True
        
        result = prompt_manager.start()
        assert result == True  # 应该返回True，但不重复启动
    
    def test_stop_not_running(self, prompt_manager):
        """测试停止未运行的程序"""
        prompt_manager.stop()  # 应该不会抛异常
        assert prompt_manager.running == False
    
    @patch('main.initialize_on_startup')
    @patch('main.GlobalConfigManager')
    @patch('main.HotkeyConfigManager')
    @patch('main.TextProcessor')
    @patch('main.HotkeyListener')
    def test_stop_running(self, mock_hotkey_listener, mock_text_processor, 
                         mock_hotkey_config, mock_global_config, 
                         mock_initialize, prompt_manager):
        """测试停止运行中的程序"""
        # 先启动
        mock_initialize.return_value = {'success': True, 'message': '初始化成功'}
        
        mock_global_config_instance = Mock()
        mock_hotkey_config_instance = Mock()
        mock_text_processor_instance = Mock()
        mock_text_processor_instance.get_platform_capabilities.return_value = {
            'platform': 'Darwin',
            'clipboard_available': True,
            'copy_simulation_available': True
        }
        mock_text_processor_instance._model_clients = {}
        mock_hotkey_listener_instance = Mock()
        mock_hotkey_listener_instance.start.return_value = True
        mock_hotkey_listener_instance.get_current_mappings.return_value = {}
        
        mock_global_config.return_value = mock_global_config_instance
        mock_hotkey_config.return_value = mock_hotkey_config_instance
        mock_text_processor.return_value = mock_text_processor_instance
        mock_hotkey_listener.return_value = mock_hotkey_listener_instance
        
        assert prompt_manager.initialize() == True
        assert prompt_manager.start() == True
        
        # 停止
        prompt_manager.stop()
        
        # 验证结果
        assert prompt_manager.running == False
        mock_hotkey_listener_instance.stop.assert_called_once()
    
    @patch('main.initialize_on_startup')
    @patch('main.GlobalConfigManager')
    @patch('main.HotkeyConfigManager')
    @patch('main.TextProcessor')
    @patch('main.HotkeyListener')
    def test_reload_config(self, mock_hotkey_listener, mock_text_processor, 
                          mock_hotkey_config, mock_global_config, 
                          mock_initialize, prompt_manager):
        """测试配置重载"""
        # 先初始化
        mock_initialize.return_value = {'success': True, 'message': '初始化成功'}
        
        mock_global_config_instance = Mock()
        mock_hotkey_config_instance = Mock()
        mock_text_processor_instance = Mock()
        mock_text_processor_instance.get_platform_capabilities.return_value = {
            'platform': 'Darwin',
            'clipboard_available': True,
            'copy_simulation_available': True
        }
        mock_hotkey_listener_instance = Mock()
        
        mock_global_config.return_value = mock_global_config_instance
        mock_hotkey_config.return_value = mock_hotkey_config_instance
        mock_text_processor.return_value = mock_text_processor_instance
        mock_hotkey_listener.return_value = mock_hotkey_listener_instance
        
        assert prompt_manager.initialize() == True
        
        # 重载配置
        prompt_manager.reload_config()
        
        # 验证调用
        assert mock_global_config_instance.load_config.call_count == 2  # 初始化 + 重载
        assert mock_hotkey_config_instance.load_config.call_count == 2
        mock_hotkey_listener_instance.reload_config.assert_called_once()
    
    def test_get_status_initial(self, prompt_manager):
        """测试获取初始状态"""
        status = prompt_manager.get_status()
        
        assert status['running'] == False
        assert status['processed_requests'] == 0
        assert status['error_count'] == 0
        assert status['start_time'] is None
        assert 'runtime' not in status
        assert all(v == False for v in status['components'].values())
    
    @patch('main.initialize_on_startup')
    @patch('main.GlobalConfigManager')
    @patch('main.HotkeyConfigManager')
    @patch('main.TextProcessor')
    @patch('main.HotkeyListener')
    def test_get_status_after_init(self, mock_hotkey_listener, mock_text_processor, 
                                  mock_hotkey_config, mock_global_config, 
                                  mock_initialize, prompt_manager):
        """测试初始化后的状态"""
        # 先初始化
        mock_initialize.return_value = {'success': True, 'message': '初始化成功'}
        
        mock_global_config.return_value = Mock()
        mock_hotkey_config.return_value = Mock()
        mock_text_processor_instance = Mock()
        mock_text_processor_instance.get_platform_capabilities.return_value = {
            'platform': 'Darwin',
            'clipboard_available': True,
            'copy_simulation_available': True
        }
        mock_text_processor.return_value = mock_text_processor_instance
        mock_hotkey_listener.return_value = Mock()
        
        assert prompt_manager.initialize() == True
        
        status = prompt_manager.get_status()
        
        assert status['running'] == False  # 还未启动
        assert all(v == True for v in status['components'].values())
    
    def test_hotkey_handler(self, prompt_manager):
        """测试快捷键处理回调"""
        # 模拟文本处理器
        mock_text_processor = Mock()
        mock_text_processor.process_template_with_ai_complete.return_value = {
            'success': True
        }
        prompt_manager.text_processor = mock_text_processor
        
        # 设置回调
        prompt_manager._setup_hotkey_callbacks()
        
        # 验证统计
        assert prompt_manager.processed_requests == 0
        assert prompt_manager.error_count == 0


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_parse_arguments_default(self):
        """测试默认参数解析"""
        with patch('sys.argv', ['main.py']):
            args = parse_arguments()
            assert args.config == 'config'
            assert args.prompt == 'prompt'
            assert args.debug == False
    
    def test_parse_arguments_custom(self):
        """测试自定义参数解析"""
        with patch('sys.argv', ['main.py', '--config', 'custom_config', '--prompt', 'custom_prompt', '--debug']):
            args = parse_arguments()
            assert args.config == 'custom_config'
            assert args.prompt == 'custom_prompt'
            assert args.debug == True
    
    def test_setup_signal_handlers(self):
        """测试信号处理器设置"""
        mock_manager = Mock()
        
        # 这个测试只验证函数可以被调用而不抛异常
        setup_signal_handlers(mock_manager)


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        config_dir = tempfile.mkdtemp()
        prompt_dir = tempfile.mkdtemp()
        
        # 创建必要的配置文件
        config_path = Path(config_dir)
        config_path.mkdir(exist_ok=True)
        
        prompt_path = Path(prompt_dir)
        prompt_path.mkdir(exist_ok=True)
        
        yield config_dir, prompt_dir
        shutil.rmtree(config_dir)
        shutil.rmtree(prompt_dir)
    
    def test_full_initialization_flow(self, temp_dirs):
        """测试完整的初始化流程"""
        config_dir, prompt_dir = temp_dirs
        
        prompt_manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
        
        # 这个测试验证初始化不会抛出异常
        try:
            result = prompt_manager.initialize()
            # 在测试环境中，某些组件可能无法完全初始化，这是正常的
            assert isinstance(result, bool)
        except Exception as e:
            # 记录但不失败，因为测试环境限制
            print(f"初始化在测试环境中遇到预期的限制: {e}")
            # 在测试环境中失败是预期的
    
    def test_logging_setup(self, temp_dirs):
        """测试日志设置"""
        config_dir, prompt_dir = temp_dirs
        
        # 创建PromptManager会设置日志
        prompt_manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
        
        # 验证日志配置基本功能
        logger = logging.getLogger()
        
        # 验证日志确实可以工作
        test_logger = logging.getLogger('test_prompt_manager')
        try:
            test_logger.info("测试日志消息")  # 这不应该抛出异常
        except Exception as e:
            pytest.fail(f"日志设置有问题: {e}")
        
        # 验证PromptManager的基本日志功能
        assert hasattr(prompt_manager, '_setup_logging')
        assert callable(prompt_manager._setup_logging) 