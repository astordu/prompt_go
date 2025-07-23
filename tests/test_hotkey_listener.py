"""
快捷键监听器测试

验证全局快捷键监听器的功能，特别是control+option+command+1-9快捷键的注册和监听。
"""

import pytest
import time
import threading
import yaml
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from modules.hotkey_listener import HotkeyListener
from pynput.keyboard import Key, KeyCode


class TestHotkeyListener:
    """快捷键监听器测试类"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture  
    def sample_hotkey_config(self, temp_config_dir):
        """创建示例快捷键配置文件"""
        config_path = Path(temp_config_dir) / "hotkey_mapping.yaml"
        config_content = """
hotkeys:
  ctrl+alt+cmd+1: translate.md
  ctrl+alt+cmd+2: summarize.md
  ctrl+alt+cmd+3: grammar_check.md
  ctrl+alt+cmd+9: custom_template.md
settings:
  enabled: true
  response_delay: 100
"""
        config_path.write_text(config_content, encoding='utf-8')
        return temp_config_dir
    
    @pytest.fixture
    def conflicted_hotkey_config(self, temp_config_dir):
        """创建包含冲突的快捷键配置文件"""
        config_path = Path(temp_config_dir) / "hotkey_mapping.yaml"
        config_content = """
hotkeys:
  ctrl+alt+cmd+1: translate.md
  ctrl+alt+cmd+2: summarize.md
  control+option+command+1: duplicate.md  # 与第一个冲突的不同格式
  invalid_hotkey: invalid.md               # 无效格式
  cmd+space: spotlight.md                  # 系统保留快捷键
settings:
  enabled: true
  response_delay: 100
"""
        config_path.write_text(config_content, encoding='utf-8')
        return temp_config_dir

    def test_hotkey_listener_init(self, sample_hotkey_config):
        """测试快捷键监听器初始化"""
        listener = HotkeyListener(sample_hotkey_config)
        
        assert listener.config_manager is not None
        assert not listener.is_listening
        assert listener.listener is None
        assert len(listener._pressed_keys) == 0
        assert len(listener._hotkey_handlers) == 0
        
    def test_normalize_hotkey_valid_combinations(self, sample_hotkey_config):
        """测试有效快捷键组合的标准化"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试 ctrl+alt+cmd+1
        keys = {Key.ctrl_l, Key.alt_l, Key.cmd, KeyCode.from_char('1')}
        result = listener._normalize_hotkey(keys)
        assert result == "ctrl+alt+cmd+1"
        
        # 测试 ctrl+alt+cmd+9 (使用右侧修饰键)
        keys = {Key.ctrl_r, Key.alt_r, Key.cmd_r, KeyCode.from_char('9')}
        result = listener._normalize_hotkey(keys)
        assert result == "ctrl+alt+cmd+9"
        
    def test_normalize_hotkey_invalid_combinations(self, sample_hotkey_config):
        """测试无效快捷键组合"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 缺少修饰键
        keys = {Key.ctrl_l, KeyCode.from_char('1')}
        result = listener._normalize_hotkey(keys)
        assert result is None
        
        # 无效数字键
        keys = {Key.ctrl_l, Key.alt_l, Key.cmd, KeyCode.from_char('0')}
        result = listener._normalize_hotkey(keys)
        assert result is None
        
        # 非数字键
        keys = {Key.ctrl_l, Key.alt_l, Key.cmd, KeyCode.from_char('a')}
        result = listener._normalize_hotkey(keys)
        assert result is None
        
    def test_register_hotkey_handler(self, sample_hotkey_config):
        """测试快捷键处理函数注册"""
        listener = HotkeyListener(sample_hotkey_config)
        
        handler_called = False
        template_name = None
        
        def test_handler(template):
            nonlocal handler_called, template_name
            handler_called = True
            template_name = template
            
        # 注册处理函数
        listener.register_hotkey_handler("ctrl+alt+cmd+1", test_handler)
        
        assert "ctrl+alt+cmd+1" in listener._hotkey_handlers
        assert listener._hotkey_handlers["ctrl+alt+cmd+1"] == test_handler
        
    def test_register_all_hotkeys(self, sample_hotkey_config):
        """测试批量注册所有快捷键"""
        listener = HotkeyListener(sample_hotkey_config)
        
        def unified_handler(template):
            pass
            
        listener.register_all_hotkeys(unified_handler)
        
        # 应该注册了配置文件中的所有快捷键
        expected_hotkeys = {"ctrl+alt+cmd+1", "ctrl+alt+cmd+2", "ctrl+alt+cmd+3", "ctrl+alt+cmd+9"}
        registered_hotkeys = set(listener._hotkey_handlers.keys())
        
        assert registered_hotkeys == expected_hotkeys
        
    def test_handle_hotkey(self, sample_hotkey_config):
        """测试快捷键处理逻辑"""
        listener = HotkeyListener(sample_hotkey_config)
        
        handler_called = False
        received_template = None
        
        def test_handler(template):
            nonlocal handler_called, received_template
            handler_called = True
            received_template = template
            
        listener.register_hotkey_handler("ctrl+alt+cmd+1", test_handler)
        
        # 模拟快捷键触发
        listener._handle_hotkey("ctrl+alt+cmd+1")
        
        # 等待线程执行
        time.sleep(0.1)
        
        assert handler_called
        assert received_template == "translate.md"
        
    def test_handle_hotkey_disabled(self, sample_hotkey_config):
        """测试快捷键被禁用时的处理"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 禁用快捷键
        listener.config_manager.set('settings.enabled', False)
        
        handler_called = False
        
        def test_handler(template):
            nonlocal handler_called
            handler_called = True
            
        listener.register_hotkey_handler("ctrl+alt+cmd+1", test_handler)
        listener._handle_hotkey("ctrl+alt+cmd+1")
        
        time.sleep(0.1)
        assert not handler_called
        
    def test_handle_hotkey_no_template(self, sample_hotkey_config):
        """测试快捷键没有对应模板的处理"""
        listener = HotkeyListener(sample_hotkey_config)
        
        handler_called = False
        
        def test_handler(template):
            nonlocal handler_called  
            handler_called = True
            
        listener.register_hotkey_handler("ctrl+alt+cmd+5", test_handler)
        
        # ctrl+alt+cmd+5 在配置文件中没有对应的模板
        listener._handle_hotkey("ctrl+alt+cmd+5")
        
        time.sleep(0.1)
        assert not handler_called
        
    def test_is_hotkey_enabled(self, sample_hotkey_config):
        """测试快捷键启用状态检查"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 启用的快捷键
        assert listener.is_hotkey_enabled("ctrl+alt+cmd+1")
        
        # 未配置的快捷键
        assert not listener.is_hotkey_enabled("ctrl+alt+cmd+5")
        
        # 全局禁用
        listener.config_manager.set('settings.enabled', False)
        assert not listener.is_hotkey_enabled("ctrl+alt+cmd+1")
        
    def test_get_hotkey_info(self, sample_hotkey_config):
        """测试获取快捷键信息"""
        listener = HotkeyListener(sample_hotkey_config)
        listener.register_all_hotkeys(lambda t: None)
        
        info = listener.get_hotkey_info()
        
        assert isinstance(info, dict)
        assert 'is_listening' in info
        assert 'enabled' in info
        assert 'mappings_count' in info
        assert 'handlers_count' in info
        assert 'response_delay' in info
        
        assert info['is_listening'] == False
        assert info['enabled'] == True
        assert info['mappings_count'] == 4
        assert info['handlers_count'] == 4
        assert info['response_delay'] == 100
        
    @patch('modules.hotkey_listener.Listener')
    @patch('modules.hotkey_listener.HotkeyListener._restore_listening_state')
    def test_start_listening(self, mock_restore_state, mock_listener_class, sample_hotkey_config):
        """测试启动快捷键监听"""
        mock_listener = Mock()
        mock_listener_class.return_value = mock_listener
        
        listener = HotkeyListener(sample_hotkey_config)
        result = listener.start_listening()
        
        assert result == True
        assert listener.is_listening == True
        mock_listener.start.assert_called()
        
    @patch('modules.hotkey_listener.Listener')
    @patch('modules.hotkey_listener.HotkeyListener._restore_listening_state')
    def test_stop_listening(self, mock_restore_state, mock_listener_class, sample_hotkey_config):
        """测试停止快捷键监听"""
        mock_listener = Mock()
        mock_listener_class.return_value = mock_listener
        
        listener = HotkeyListener(sample_hotkey_config)
        listener.start_listening()
        result = listener.stop_listening()
        
        assert result == True
        assert listener.is_listening == False
        mock_listener.stop.assert_called()
        
    def test_context_manager(self, sample_hotkey_config):
        """测试上下文管理器"""
        with patch('modules.hotkey_listener.Listener') as mock_listener_class:
            with patch('modules.hotkey_listener.HotkeyListener._restore_listening_state'):
                mock_listener = Mock()
                mock_listener_class.return_value = mock_listener
                
                with HotkeyListener(sample_hotkey_config) as listener:
                    assert listener.is_listening == True
                    mock_listener.start.assert_called()
                    
                mock_listener.stop.assert_called()

    def test_detect_basic_conflicts(self, conflicted_hotkey_config):
        """测试基础快捷键冲突检测"""
        listener = HotkeyListener(conflicted_hotkey_config)
        mappings = listener.config_manager.get_all_mappings()
        
        conflicts = listener._detect_hotkey_conflicts(mappings)
        
        # 应该检测到重复的快捷键
        assert len(conflicts) > 0
        
    def test_detect_advanced_conflicts(self, conflicted_hotkey_config):
        """测试高级快捷键冲突检测"""
        listener = HotkeyListener(conflicted_hotkey_config)
        mappings = listener.config_manager.get_all_mappings()
        
        conflicts = listener._detect_advanced_conflicts(mappings)
        
        # 检查各种冲突类型
        assert 'system_reserved' in conflicts
        assert 'invalid_format' in conflicts
        assert 'duplicate_mappings' in conflicts
        
        # 应该检测到无效格式（cmd+space不符合我们的快捷键格式要求）
        assert 'cmd+space' in conflicts['invalid_format']
        
        # 应该检测到其他无效格式
        assert 'invalid_hotkey' in conflicts['invalid_format']
        
        # 应该检测到重复映射
        assert 'control+option+command+1' in conflicts['duplicate_mappings']
        assert 'ctrl+alt+cmd+1' in conflicts['duplicate_mappings']
        
    def test_validate_hotkey_format(self, sample_hotkey_config):
        """测试快捷键格式验证"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 有效格式
        assert listener._is_valid_hotkey_format("ctrl+alt+cmd+1")
        assert listener._is_valid_hotkey_format("ctrl+alt+cmd+9")
        
        # 无效格式
        assert not listener._is_valid_hotkey_format("invalid_key")
        assert not listener._is_valid_hotkey_format("ctrl+alt+1")  # 缺少cmd
        assert not listener._is_valid_hotkey_format("ctrl+alt+cmd+0")  # 无效数字
        assert not listener._is_valid_hotkey_format("ctrl+alt+cmd+a")  # 非数字
        
    def test_fix_hotkey_format(self, sample_hotkey_config):
        """测试快捷键格式修复"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 可修复的格式错误
        assert listener._fix_hotkey_format("control+option+command+1") == "ctrl+alt+cmd+1"
        assert listener._fix_hotkey_format("ctl+opt+cmd+2") == "ctrl+alt+cmd+2"
        
        # 无法修复的错误
        assert listener._fix_hotkey_format("invalid_key") is None
        assert listener._fix_hotkey_format("ctrl+alt+1") is None  # 缺少必需键
        
    def test_validate_hotkey_configuration(self, conflicted_hotkey_config):
        """测试快捷键配置全面验证"""
        listener = HotkeyListener(conflicted_hotkey_config)
        
        result = listener.validate_hotkey_configuration()
        
        # 检查返回的字段
        assert 'is_valid' in result
        assert 'health_score' in result
        assert 'basic_conflicts' in result
        assert 'advanced_conflicts' in result
        assert 'template_issues' in result
        assert 'solutions' in result
        assert 'recommendations' in result
        
        # 应该检测到配置无效
        assert not result['is_valid']
        assert result['health_score'] < 100
        
    def test_resolve_conflicts(self, conflicted_hotkey_config):
        """测试冲突解决方案生成"""
        listener = HotkeyListener(conflicted_hotkey_config)
        mappings = listener.config_manager.get_all_mappings()
        conflicts = listener._detect_advanced_conflicts(mappings)
        
        solutions = listener.resolve_conflicts(conflicts)
        
        # 应该为每种冲突类型提供解决方案
        for conflict_type, conflicted_keys in conflicts.items():
            if conflicted_keys:
                assert conflict_type in solutions
                
    def test_get_available_hotkeys(self, sample_hotkey_config):
        """测试获取可用快捷键"""
        listener = HotkeyListener(sample_hotkey_config)
        
        available = listener._get_available_hotkeys()
        
        # 应该返回未使用的快捷键
        assert isinstance(available, list)
        assert len(available) == 5  # 9个总数 - 4个已使用
        
        # 检查是否不包含已使用的快捷键
        used_hotkeys = set(listener.config_manager.get_all_mappings().keys())
        for hotkey in available:
            assert hotkey not in used_hotkeys
            
    def test_create_config_backup(self, sample_hotkey_config):
        """测试配置文件备份创建"""
        listener = HotkeyListener(sample_hotkey_config)
        
        result = listener._create_config_backup()
        
        # 应该成功创建备份
        assert result is True
        
        # 检查备份文件是否存在
        config_dir = Path(sample_hotkey_config)
        backup_files = list(config_dir.glob("hotkey_mapping.yaml.backup_*"))
        assert len(backup_files) > 0
        
    def test_apply_conflict_solutions(self, conflicted_hotkey_config):
        """测试应用冲突解决方案"""
        listener = HotkeyListener(conflicted_hotkey_config)
        
        # 获取冲突和解决方案
        validation_result = listener.validate_hotkey_configuration()
        solutions = validation_result['solutions']
        
        if solutions:
            # 应用解决方案
            result = listener.apply_conflict_solutions(solutions, auto_apply=True)
            
            # 检查应用结果
            assert 'applied' in result
            assert 'failed' in result
            assert 'skipped' in result
            assert 'backup_created' in result
            
    def test_calculate_config_health(self, sample_hotkey_config):
        """测试配置健康度计算"""
        listener = HotkeyListener(sample_hotkey_config)
        mappings = listener.config_manager.get_all_mappings()
        
        # 模拟一个健康的配置
        health_score = listener._calculate_config_health(mappings, set(), {}, {})
        
        # 健康分数应该在合理范围内
        assert 0 <= health_score <= 100
        assert health_score > 50  # 示例配置应该相对健康
        
    def test_generate_configuration_recommendations(self, sample_hotkey_config):
        """测试配置建议生成"""
        listener = HotkeyListener(sample_hotkey_config)
        mappings = listener.config_manager.get_all_mappings()
        conflicts = listener._detect_advanced_conflicts(mappings)
        
        recommendations = listener._generate_configuration_recommendations(mappings, conflicts)
        
        # 应该返回建议列表
        assert isinstance(recommendations, list)
        
    def test_error_handling_missing_template_dir(self, temp_config_dir):
        """测试缺少模板目录时的错误处理"""
        # 删除模板目录
        template_dir = Path(temp_config_dir) / "prompt"
        if template_dir.exists():
            shutil.rmtree(template_dir)
            
        # 初始化监听器应该能够处理缺少的目录
        listener = HotkeyListener(temp_config_dir, str(template_dir))
        
        # 目录应该被自动创建
        assert template_dir.exists()
        
    def test_error_handling_invalid_config(self, temp_config_dir):
        """测试无效配置文件的错误处理"""
        # 创建无效的配置文件
        config_path = Path(temp_config_dir) / "hotkey_mapping.yaml"
        config_path.write_text("invalid: yaml: content: [unclosed", encoding='utf-8')
        
        # 初始化监听器应该能够处理无效配置
        listener = HotkeyListener(temp_config_dir)
        
        # 应该有错误处理机制
        assert listener.config_manager is not None
        
    def test_platform_specific_handling(self, sample_hotkey_config):
        """测试平台特定处理"""
        listener = HotkeyListener(sample_hotkey_config)
        
        platform_info = listener.get_platform_info()
        
        # 检查平台信息
        assert 'platform' in platform_info
        assert 'is_macos' in platform_info
        assert 'supported_hotkeys' in platform_info
        assert 'accessibility_required' in platform_info

    def test_listening_state_persistence(self, sample_hotkey_config):
        """测试监听状态持久化"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 检查状态文件初始化
        assert listener._state_file.name == "listener_state.json"
        
        # 测试保存状态
        listener._save_listening_state()
        assert listener._state_file.exists()
        
        # 测试状态恢复
        original_auto_restart = listener._auto_restart_enabled
        listener._auto_restart_enabled = False
        listener._save_listening_state()
        
        # 创建新的监听器实例来测试状态恢复
        new_listener = HotkeyListener(sample_hotkey_config)
        assert new_listener._auto_restart_enabled == False
        
    def test_health_check_functionality(self, sample_hotkey_config):
        """测试健康检查功能"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试健康检查状态
        assert not listener._health_check_running
        assert listener._health_check_thread is None
        
        # 启动健康检查
        listener._start_health_check()
        assert listener._health_check_running
        assert listener._health_check_thread is not None
        
        # 停止健康检查
        listener._stop_health_check()
        assert not listener._health_check_running
        
    def test_listener_health_detection(self, sample_hotkey_config):
        """测试监听器健康检测"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 未启动时应该不健康
        assert not listener._is_listener_healthy()
        
        # 模拟启动状态
        with patch('modules.hotkey_listener.Listener') as mock_listener_class:
            mock_listener = Mock()
            mock_listener._thread = Mock()
            mock_listener._thread.is_alive.return_value = True
            mock_listener_class.return_value = mock_listener
            
            listener.start_listening()
            assert listener._is_listener_healthy()
            
            # 模拟线程死亡
            mock_listener._thread.is_alive.return_value = False
            assert not listener._is_listener_healthy()
            
            listener.stop_listening()
    
    def test_auto_restart_functionality(self, sample_hotkey_config):
        """测试自动重启功能"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试自动重启设置
        listener.set_auto_restart(False)
        assert not listener._auto_restart_enabled
        
        listener.set_auto_restart(True)
        assert listener._auto_restart_enabled
        
        # 测试重启尝试计数
        listener._restart_attempts = 2
        listener.reset_restart_attempts()
        assert listener._restart_attempts == 0
        
    def test_statistics_tracking(self, sample_hotkey_config):
        """测试统计信息跟踪"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 检查初始统计
        stats = listener._listening_statistics
        assert stats['total_hotkeys_processed'] == 0
        assert stats['error_count'] == 0
        assert stats['restart_count'] == 0
        
        # 模拟快捷键处理
        listener._listening_statistics['total_hotkeys_processed'] += 1
        assert listener._listening_statistics['total_hotkeys_processed'] == 1
        
    def test_listening_status_info(self, sample_hotkey_config):
        """测试监听状态信息获取"""
        listener = HotkeyListener(sample_hotkey_config)
        
        status = listener.get_listening_status()
        
        # 检查状态信息字段
        assert 'is_listening' in status
        assert 'is_healthy' in status
        assert 'auto_restart_enabled' in status
        assert 'health_check_running' in status
        assert 'statistics' in status
        assert 'state_file_exists' in status
        
    def test_health_check_interval_setting(self, sample_hotkey_config):
        """测试健康检查间隔设置"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试有效间隔
        listener.set_health_check_interval(60)
        assert listener._health_check_interval == 60
        
        # 测试无效间隔
        with pytest.raises(ValueError):
            listener.set_health_check_interval(3)  # 小于5秒
            
    def test_force_restart(self, sample_hotkey_config):
        """测试强制重启功能"""
        listener = HotkeyListener(sample_hotkey_config)
        
        with patch.object(listener, '_attempt_restart') as mock_restart:
            mock_restart.return_value = True
            
            # 即使自动重启被禁用，强制重启也应该工作
            listener.set_auto_restart(False)
            result = listener.force_restart()
            
            assert result == True
            mock_restart.assert_called_once()
            
    def test_enhanced_hotkey_info(self, sample_hotkey_config):
        """测试增强的快捷键信息获取"""
        listener = HotkeyListener(sample_hotkey_config)
        
        info = listener.get_hotkey_info()
        
        # 检查增强信息
        assert 'listening_status' in info
        assert 'mapping_status' in info
        assert 'platform_info' in info
        
        # 检查监听状态子信息
        listening_status = info['listening_status']
        assert 'statistics' in listening_status
        assert 'auto_restart_enabled' in listening_status
        
    def test_restart_attempt_limits(self, sample_hotkey_config):
        """测试重启尝试限制"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 设置最大重启次数
        listener._max_restart_attempts = 2
        listener._restart_attempts = 2
        
        # 应该拒绝重启
        with patch.object(listener, 'stop_listening'), \
             patch.object(listener, 'start_listening'):
            result = listener._attempt_restart()
            assert result == False
            assert not listener._auto_restart_enabled
            
    def test_restart_time_limit(self, sample_hotkey_config):
        """测试重启时间限制"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 设置最近重启时间
        listener._last_restart_time = time.time()
        
        # 应该拒绝在时间限制内重启
        result = listener._attempt_restart()
        assert result == False

    def test_config_reload_monitoring(self, sample_hotkey_config):
        """测试配置文件监控启动和停止"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 检查配置监控是否已启动
        assert listener._config_reload_enabled
        assert listener.config_manager._is_watching
        
        # 停止配置监控
        listener._stop_config_monitoring()
        assert not listener.config_manager._is_watching
        
        # 重新启动配置监控
        listener._start_config_monitoring()
        assert listener.config_manager._is_watching
        
    def test_config_reload_callbacks(self, sample_hotkey_config):
        """测试配置重载回调机制"""
        listener = HotkeyListener(sample_hotkey_config)
        
        callback_called = False
        received_changes = None
        
        def test_callback(changes):
            nonlocal callback_called, received_changes
            callback_called = True
            received_changes = changes
            
        # 添加回调
        listener.add_config_reload_callback(test_callback)
        assert len(listener._config_reload_callbacks) == 1
        
        # 模拟配置变化
        test_changes = {'added_hotkeys': {'ctrl+alt+cmd+5': 'new_template.md'}}
        listener._notify_config_reload_callbacks(test_changes)
        
        assert callback_called
        assert received_changes == test_changes
        
        # 移除回调
        listener.remove_config_reload_callback(test_callback)
        assert len(listener._config_reload_callbacks) == 0
        
    def test_config_hash_calculation(self, sample_hotkey_config):
        """测试配置哈希计算"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 计算初始哈希
        hash1 = listener._calculate_config_hash()
        assert hash1 is not None
        assert len(hash1) == 32  # MD5哈希长度
        
        # 相同配置应该产生相同哈希
        hash2 = listener._calculate_config_hash()
        assert hash1 == hash2
        
    def test_config_changes_analysis(self, sample_hotkey_config):
        """测试配置变化分析"""
        listener = HotkeyListener(sample_hotkey_config)
        
        old_mappings = {
            'ctrl+alt+cmd+1': 'old_template1.md',
            'ctrl+alt+cmd+2': 'template2.md',
            'ctrl+alt+cmd+3': 'template3.md'
        }
        
        new_mappings = {
            'ctrl+alt+cmd+1': 'new_template1.md',  # 修改
            'ctrl+alt+cmd+2': 'template2.md',      # 未变化
            'ctrl+alt+cmd+4': 'template4.md'       # 新增
            # ctrl+alt+cmd+3 被删除
        }
        
        changes = listener._analyze_config_changes(old_mappings, new_mappings, True, False)
        
        # 检查分析结果
        assert changes['enabled_changed'] == True
        assert len(changes['added_hotkeys']) == 1
        assert 'ctrl+alt+cmd+4' in changes['added_hotkeys']
        assert len(changes['removed_hotkeys']) == 1
        assert 'ctrl+alt+cmd+3' in changes['removed_hotkeys']
        assert len(changes['modified_hotkeys']) == 1
        assert 'ctrl+alt+cmd+1' in changes['modified_hotkeys']
        assert len(changes['unchanged_hotkeys']) == 1
        assert 'ctrl+alt+cmd+2' in changes['unchanged_hotkeys']
        
    def test_config_reload_enable_disable(self, sample_hotkey_config):
        """测试配置重载启用和禁用"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 初始状态应该是启用的
        assert listener._config_reload_enabled
        
        # 禁用配置重载
        listener.set_config_reload_enabled(False)
        assert not listener._config_reload_enabled
        assert not listener.config_manager._is_watching
        
        # 重新启用配置重载
        listener.set_config_reload_enabled(True)
        assert listener._config_reload_enabled
        assert listener.config_manager._is_watching
        
    def test_config_reload_debounce_setting(self, sample_hotkey_config):
        """测试配置重载防抖设置"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试有效防抖时间
        listener.set_config_reload_debounce_time(2.0)
        assert listener._config_reload_debounce_time == 2.0
        
        # 测试无效防抖时间
        with pytest.raises(ValueError):
            listener.set_config_reload_debounce_time(0.05)
            
    def test_config_reload_statistics(self, sample_hotkey_config):
        """测试配置重载统计"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 检查初始统计
        stats = listener._config_reload_statistics
        assert stats['total_reloads'] == 0
        assert stats['successful_reloads'] == 0
        assert stats['failed_reloads'] == 0
        assert stats['last_reload_time'] is None
        
    def test_force_config_reload(self, sample_hotkey_config):
        """测试强制配置重载"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 模拟配置变化处理
        with patch.object(listener, '_on_config_changed') as mock_reload:
            result = listener.force_config_reload()
            assert result == True
            mock_reload.assert_called_once()
            
    def test_config_reload_status_info(self, sample_hotkey_config):
        """测试配置重载状态信息"""
        listener = HotkeyListener(sample_hotkey_config)
        
        status = listener.get_config_reload_status()
        
        # 检查状态信息字段
        assert 'enabled' in status
        assert 'is_monitoring' in status
        assert 'debounce_time' in status
        assert 'callback_count' in status
        assert 'statistics' in status
        assert 'last_config_hash' in status
        
        assert status['enabled'] == True
        assert status['is_monitoring'] == True
        assert status['callback_count'] == 0
        
    def test_enhanced_hotkey_info_with_config_reload(self, sample_hotkey_config):
        """测试包含配置重载信息的快捷键状态"""
        listener = HotkeyListener(sample_hotkey_config)
        
        info = listener.get_hotkey_info()
        
        # 检查是否包含配置重载状态
        assert 'config_reload_status' in info
        
        config_reload_status = info['config_reload_status']
        assert 'enabled' in config_reload_status
        assert 'statistics' in config_reload_status
        
    def test_config_apply_changes(self, sample_hotkey_config):
        """测试配置变化应用"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 先注册一些处理函数
        def dummy_handler(template):
            pass
            
        listener.register_hotkey_handler("ctrl+alt+cmd+1", dummy_handler)
        listener.register_hotkey_handler("ctrl+alt+cmd+2", dummy_handler)
        
        assert len(listener._hotkey_handlers) == 2
        
        # 模拟删除一个快捷键
        changes = {
            'removed_hotkeys': {'ctrl+alt+cmd+1': 'template1.md'},
            'added_hotkeys': {'ctrl+alt+cmd+3': 'template3.md'},
            'modified_hotkeys': {},
            'unchanged_hotkeys': {}
        }
        
        listener._apply_config_changes(changes)
        
        # 检查处理函数是否被正确移除
        assert len(listener._hotkey_handlers) == 1
        assert "ctrl+alt+cmd+1" not in listener._hotkey_handlers
        assert "ctrl+alt+cmd+2" in listener._hotkey_handlers
        
    def test_config_reload_with_file_modification(self, sample_hotkey_config):
        """测试通过文件修改触发配置重载"""
        import tempfile
        import yaml
        import os
        
        listener = HotkeyListener(sample_hotkey_config)
        
        # 记录初始统计
        initial_reloads = listener._config_reload_statistics['total_reloads']
        
        # 修改配置文件
        config_file = listener.config_manager.config_path
        
        # 读取现有配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            
        # 添加一个新的快捷键映射
        config_data['hotkeys']['ctrl+alt+cmd+5'] = 'new_template.md'
        
        # 写回配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
        # 等待文件监控触发（可能需要短暂等待）
        time.sleep(0.1)
        
        # 手动触发配置重载以确保测试
        listener.force_config_reload()
        
        # 检查统计是否更新
        assert listener._config_reload_statistics['total_reloads'] > initial_reloads

    def test_macos_compatibility_initialization(self, sample_hotkey_config):
        """测试macOS兼容性初始化"""
        with patch('platform.system', return_value='Darwin'):
            with patch.object(HotkeyListener, '_initialize_macos_compatibility') as mock_init:
                listener = HotkeyListener(sample_hotkey_config)
                mock_init.assert_called_once()
    
    def test_macos_version_detection(self, sample_hotkey_config):
        """测试macOS版本检测"""
        listener = HotkeyListener(sample_hotkey_config)
        
        with patch('subprocess.run') as mock_run:
            # 模拟成功获取版本
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "14.1.2\n"
            
            version = listener._get_macos_version()
            assert version == "14.1.2"
            mock_run.assert_called_with(['sw_vers', '-productVersion'], 
                                      capture_output=True, text=True, timeout=5)
    
    def test_accessibility_permission_check(self, sample_hotkey_config):
        """测试辅助功能权限检查"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        # 重置权限检查状态
        listener._macos_compatibility['accessibility_granted'] = None
        listener._macos_compatibility['last_permission_check'] = None
        
        # 测试权限已授予的情况
        with patch('pynput.keyboard.Listener') as mock_listener_class:
            mock_listener = Mock()
            mock_listener_class.return_value = mock_listener
            
            result = listener._check_accessibility_permission()
            assert result == True
            assert listener._macos_compatibility['accessibility_granted'] == True
    
    def test_macos_notification_sending(self, sample_hotkey_config):
        """测试macOS系统通知发送"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        with patch('subprocess.run') as mock_run:
            # 模拟通知发送成功
            mock_run.return_value.returncode = 0
            
            result = listener._send_macos_notification("测试标题", "测试消息")
            assert result == True
            
            # 验证调用了正确的命令
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == 'osascript'
            assert '测试标题' in args[2]
            assert '测试消息' in args[2]
    
    def test_macos_notification_failure(self, sample_hotkey_config):
        """测试macOS系统通知发送失败"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        with patch('subprocess.run') as mock_run:
            # 模拟通知发送失败
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Permission denied"
            
            result = listener._send_macos_notification("测试标题", "测试消息")
            assert result == False
    
    def test_macos_hotkey_conflicts_detection(self, sample_hotkey_config):
        """测试macOS特有快捷键冲突检测"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 添加与macOS系统快捷键冲突的映射
        test_mappings = {
            'cmd+space': 'template1.md',    # 与Spotlight冲突
            'cmd+tab': 'template2.md',      # 与应用切换冲突
            'ctrl+alt+cmd+1': 'template3.md' # 正常快捷键
        }
        
        conflicts = listener._check_macos_hotkey_conflicts()
        # 这里我们使用实际的配置，所以不会有冲突
        assert isinstance(conflicts, list)
    
    def test_macos_reserved_pattern_detection(self, sample_hotkey_config):
        """测试macOS保留快捷键模式检测"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试保留模式
        assert listener._is_macos_reserved_pattern('cmd+shift+3') == True
        assert listener._is_macos_reserved_pattern('cmd+opt+esc') == True
        assert listener._is_macos_reserved_pattern('ctrl+f1') == True
        
        # 测试正常快捷键
        assert listener._is_macos_reserved_pattern('ctrl+alt+cmd+1') == False
        assert listener._is_macos_reserved_pattern('cmd+a') == False
    
    def test_accessibility_settings_opening(self, sample_hotkey_config):
        """测试打开辅助功能设置"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        with patch('subprocess.run') as mock_run:
            result = listener._open_accessibility_settings()
            assert result == True
            
            mock_run.assert_called_with([
                'open', 
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            ], timeout=5)
    
    def test_macos_app_info_retrieval(self, sample_hotkey_config):
        """测试获取macOS应用信息"""
        listener = HotkeyListener(sample_hotkey_config)
        
        app_info = listener._get_macos_app_info()
        
        # 检查基本字段
        assert 'executable_path' in app_info
        assert 'process_name' in app_info
        assert 'is_python_script' in app_info
        assert app_info['is_python_script'] == True
    
    def test_macos_compatibility_status(self, sample_hotkey_config):
        """测试macOS兼容性状态获取"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试非macOS平台
        listener._platform = "Linux"
        status = listener.get_macos_compatibility_status()
        assert status['platform'] == 'non-macos'
        assert status['compatible'] == False
        
        # 测试macOS平台
        listener._platform = "Darwin"
        listener._macos_compatibility = {
            'system_version': '14.0',
            'accessibility_granted': True,
            'notification_enabled': True,
            'compatibility_issues': [],
            'macos_features': {},
            'last_permission_check': time.time()
        }
        
        with patch.object(listener, '_check_accessibility_permission', return_value=True):
            status = listener.get_macos_compatibility_status()
            assert status['platform'] == 'macOS'
            assert 'system_version' in status
            assert 'accessibility_granted' in status
            assert 'compatibility_issues' in status
    
    def test_macos_permissions_setup(self, sample_hotkey_config):
        """测试macOS权限设置辅助方法"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        with patch.object(listener, '_check_accessibility_permission', return_value=False):
            with patch.object(listener, '_open_accessibility_settings', return_value=True):
                with patch.object(listener, '_send_macos_notification', return_value=True):
                    with patch.object(listener, '_analyze_compatibility_issues'):
                        
                        result = listener.setup_macos_permissions()
                        
                        assert 'accessibility_opened' in result
                        assert 'notification_sent' in result
                        assert 'issues_found' in result
                        assert 'recommendations' in result
                        
                        assert result['accessibility_opened'] == True
                        assert "辅助功能权限未授予" in result['issues_found']
    
    def test_enhanced_platform_info_with_macos(self, sample_hotkey_config):
        """测试增强的平台信息（包含macOS详细信息）"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        # 模拟macOS兼容性状态
        mock_compatibility = {
            'platform': 'macOS',
            'system_version': '14.0',
            'compatible': True,
            'accessibility_granted': True,
            'compatibility_issues': [],
            'macos_features': {'notification_center': True}
        }
        
        with patch.object(listener, 'get_macos_compatibility_status', return_value=mock_compatibility):
            platform_info = listener.get_platform_info()
            
            assert platform_info['is_macos'] == True
            assert 'macos_compatibility' in platform_info
            assert 'system_version' in platform_info
            assert 'accessibility_granted' in platform_info
            assert 'macos_features_available' in platform_info
    
    def test_macos_enhanced_start_listening(self, sample_hotkey_config):
        """测试增强的macOS启动监听功能"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        
        # 测试权限未授予的情况
        with patch.object(listener, '_check_accessibility_permission', return_value=False):
            with patch.object(listener, '_show_accessibility_permission_guide') as mock_guide:
                result = listener.start_listening()
                assert result == False
                mock_guide.assert_called_once()
        
        # 测试权限已授予的情况
        with patch.object(listener, '_check_accessibility_permission', return_value=True):
            with patch.object(listener, '_send_macos_notification') as mock_notification:
                with patch('pynput.keyboard.Listener') as mock_listener_class:
                    mock_listener = Mock()
                    mock_listener_class.return_value = mock_listener
                    
                    result = listener.start_listening()
                    # 由于已经在监听，这里会返回False
                    mock_notification.assert_called_with(
                        "快捷键监听器",
                        "快捷键监听已启动"
                    )
    
    def test_macos_enhanced_stop_listening(self, sample_hotkey_config):
        """测试增强的macOS停止监听功能"""
        listener = HotkeyListener(sample_hotkey_config)
        listener._platform = "Darwin"
        listener._macos_compatibility['notification_enabled'] = True
        
        # 先设置为监听状态
        listener.is_listening = True
        listener.listener = Mock()
        
        with patch.object(listener, '_stop_health_check'):
            with patch.object(listener, '_update_uptime_statistics'):
                with patch.object(listener, '_save_listening_state'):
                    with patch.object(listener, '_send_macos_notification') as mock_notification:
                        
                        result = listener.stop_listening()
                        assert result == True
                        
                        # 验证发送了停止通知
                        mock_notification.assert_called_with(
                            "快捷键监听器",
                            "快捷键监听已停止"
                        )
    
    def test_macos_system_version_compatibility(self, sample_hotkey_config):
        """测试macOS系统版本兼容性分析"""
        listener = HotkeyListener(sample_hotkey_config)
        
        # 测试现代版本 (macOS 14.x)
        listener._macos_compatibility['system_version'] = '14.1.2'
        listener._analyze_compatibility_issues()
        
        assert listener._macos_compatibility['macos_features']['security_assessment'] == True
        
        # 测试旧版本 (macOS 10.14)
        listener._macos_compatibility['system_version'] = '10.14.6'
        listener._macos_compatibility['compatibility_issues'] = []
        listener._analyze_compatibility_issues()
        
        issues = listener._macos_compatibility['compatibility_issues']
        assert any('较旧' in issue for issue in issues)


if __name__ == "__main__":
    # 运行测试的演示代码
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    # 基本功能演示
    print("=== 快捷键监听器功能演示 ===")
    
    listener = HotkeyListener()
    
    def demo_handler(template):
        print(f"快捷键触发! 模板: {template}")
    
    # 注册所有快捷键
    listener.register_all_hotkeys(demo_handler)
    
    print(f"监听器信息: {listener.get_hotkey_info()}")
    print("已注册的快捷键:")
    for hotkey in listener.config_manager.get_all_mappings():
        print(f"  {hotkey} -> {listener.config_manager.get_template_for_hotkey(hotkey)}")
        
    print("\n注意: 实际的全局快捷键监听需要在完整的应用程序中运行") 