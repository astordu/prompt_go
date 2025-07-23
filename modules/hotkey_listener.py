"""
全局快捷键监听系统

负责监听全局快捷键 control+option+command+1-9，并将快捷键事件映射到对应的模板处理流程。
支持快捷键配置的动态重新加载和错误处理。
"""

import logging
import threading
import platform
import time
import datetime
import json
import subprocess
import sys
from typing import Dict, Callable, Optional, Any, Set, List, Tuple
from pathlib import Path
from pynput import keyboard
from pynput.keyboard import Key, KeyCode, Listener
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config_manager import HotkeyConfigManager
from .template_parser import BasicTemplateParser

logger = logging.getLogger(__name__)


class TemplateDirectoryHandler(FileSystemEventHandler):
    """模板目录监控处理器"""
    
    def __init__(self, hotkey_listener):
        self.hotkey_listener = hotkey_listener
        self.last_update = 0
        
    def on_any_event(self, event):
        """当模板目录发生变化时触发重新映射"""
        if event.is_directory:
            return
            
        # 防止频繁更新
        current_time = time.time()
        if current_time - self.last_update < 1.0:  # 1秒内只更新一次
            return
            
        self.last_update = current_time
        
        if event.src_path.endswith('.md'):
            logger.info(f"检测到模板文件变化: {event.src_path}")
            self.hotkey_listener._update_template_mappings()


class HotkeyListener:
    """全局快捷键监听器"""
    
    # macOS平台的快捷键映射 (control+option+command对应ctrl+alt+cmd)
    MACOS_KEY_MAPPING = {
        Key.ctrl_l: Key.ctrl,
        Key.ctrl_r: Key.ctrl,
        Key.alt_l: Key.alt,  # Option键
        Key.alt_r: Key.alt,
        Key.cmd: Key.cmd,    # Command键
        Key.cmd_r: Key.cmd,
    }
    
    # macOS系统版本特有的快捷键处理
    MACOS_SYSTEM_SHORTCUTS = {
        'cmd+space': 'Spotlight搜索',
        'cmd+tab': '应用切换',
        'cmd+shift+3': '屏幕截图',
        'cmd+shift+4': '区域截图',
        'cmd+shift+5': '截图工具栏',
        'ctrl+up': 'Mission Control',
        'ctrl+down': '应用窗口',
        'cmd+ctrl+space': '字符查看器',
        'cmd+ctrl+f': '全屏切换',
        'cmd+opt+esc': '强制退出应用',
        'cmd+shift+q': '注销用户',
    }
    
    def __init__(self, config_dir: str = "config", template_dir: str = "prompt"):
        """
        初始化快捷键监听器
        
        Args:
            config_dir: 配置文件目录
            template_dir: 模板文件目录
        """
        self.config_manager = HotkeyConfigManager(config_dir)
        self.template_parser = BasicTemplateParser(template_dir)
        self.template_dir = Path(template_dir)
        self.listener: Optional[Listener] = None
        self.is_listening = False
        self._pressed_keys = set()
        self._hotkey_handlers: Dict[str, Callable] = {}
        self._platform = platform.system()
        self._template_observer: Optional[Observer] = None
        self._template_cache: Dict[str, Dict[str, Any]] = {}
        
        # macOS跨平台兼容性管理
        self._macos_compatibility = {
            'accessibility_granted': None,  # 辅助功能权限状态
            'system_version': None,         # macOS系统版本
            'notification_enabled': False,  # 系统通知是否启用
            'last_permission_check': None,  # 最后权限检查时间
            'permission_check_interval': 300,  # 权限检查间隔（5分钟）
            'compatibility_issues': [],     # 兼容性问题列表
            'macos_features': {             # macOS特有功能状态
                'dock_integration': False,
                'notification_center': False,
                'security_assessment': False,
            }
        }
        
        # 后台监听状态管理
        self._state_file = Path(config_dir) / "listener_state.json"
        self._health_check_thread: Optional[threading.Thread] = None
        self._health_check_running = False
        self._health_check_interval = 30  # 秒
        self._restart_attempts = 0
        self._max_restart_attempts = 3
        self._last_restart_time = None
        self._listening_statistics = {
            'start_time': None,
            'uptime': 0,
            'total_hotkeys_processed': 0,
            'restart_count': 0,
            'last_error': None,
            'error_count': 0
        }
        self._auto_restart_enabled = True
        self._graceful_shutdown = False
        
        # 配置热重载功能
        self._config_reload_enabled = True
        self._config_reload_callbacks: List[Callable] = []
        self._config_reload_statistics = {
            'total_reloads': 0,
            'successful_reloads': 0,
            'failed_reloads': 0,
            'last_reload_time': None,
            'last_reload_duration': 0,
            'last_reload_error': None
        }
        self._last_config_hash = None
        self._config_reload_debounce_time = 1.0  # 秒
        self._last_config_reload_time = 0
        
        # 确保模板目录存在
        self.template_dir.mkdir(exist_ok=True)
        
        # 初始化macOS兼容性检查
        if self._platform == "Darwin":
            self._initialize_macos_compatibility()
        
        # 加载配置
        try:
            self.config_manager.load_config()
            if not self.config_manager.validate_config():
                logger.warning("快捷键配置验证失败，使用默认配置")
        except Exception as e:
            logger.error(f"加载快捷键配置失败: {e}")
            
        # 初始化快捷键映射
        self._setup_hotkey_mappings()
        
        # 启动模板目录监控
        self._start_template_monitoring()
        
        # 启动配置文件热重载监控
        self._start_config_monitoring()
        
        # 恢复上次的监听状态
        self._restore_listening_state()
    
    def _setup_hotkey_mappings(self) -> None:
        """设置快捷键映射"""
        try:
            mappings = self.config_manager.get_all_mappings()
            logger.info(f"加载快捷键映射: {len(mappings)} 个快捷键")
            
            # 执行全面的配置验证
            validation_result = self.validate_hotkey_configuration()
            
            # 记录验证结果
            if not validation_result['is_valid']:
                logger.warning(f"快捷键配置验证失败，健康度评分: {validation_result['health_score']}")
                
                # 记录基础冲突
                if validation_result['basic_conflicts']:
                    logger.warning(f"检测到基础快捷键冲突: {validation_result['basic_conflicts']}")
                
                # 记录高级冲突
                for conflict_type, conflicted_keys in validation_result['advanced_conflicts'].items():
                    if conflicted_keys:
                        logger.warning(f"检测到{conflict_type}冲突: {conflicted_keys}")
                
                # 记录模板问题
                for issue_type, issues in validation_result['template_issues'].items():
                    if issues:
                        logger.warning(f"模板{issue_type}: {issues}")
                
                # 提供解决建议
                if validation_result['solutions']:
                    logger.info("可用的冲突解决方案:")
                    for conflict_type, solutions in validation_result['solutions'].items():
                        for old_key, new_key in solutions.items():
                            logger.info(f"  {conflict_type}: {old_key} -> {new_key}")
                
                # 自动应用格式修复
                auto_fix_result = self.apply_conflict_solutions(validation_result['solutions'], auto_apply=False)
                if auto_fix_result['applied']:
                    logger.info(f"自动修复了 {len(auto_fix_result['applied'])} 个配置问题")
                    
            else:
                logger.info(f"快捷键配置验证通过，健康度评分: {validation_result['health_score']}")
            
            # 验证模板文件映射
            self._validate_template_mappings(mappings)
                
            for hotkey, template in mappings.items():
                logger.debug(f"映射快捷键: {hotkey} -> {template}")
                
        except Exception as e:
            logger.error(f"设置快捷键映射失败: {e}")
    
    def _validate_template_mappings(self, mappings: Dict[str, str]) -> None:
        """
        验证模板文件映射
        
        Args:
            mappings: 快捷键映射字典
        """
        invalid_mappings = []
        
        for hotkey, template in mappings.items():
            if not self._is_template_valid(template):
                invalid_mappings.append((hotkey, template))
                logger.warning(f"模板文件不存在或无效: {hotkey} -> {template}")
                
        if invalid_mappings:
            # 生成修复建议
            suggestions = self._generate_mapping_suggestions(invalid_mappings)
            if suggestions:
                logger.info(f"建议的修复方案: {suggestions}")
    
    def _is_template_valid(self, template_name: str) -> bool:
        """
        检查模板文件是否有效
        
        Args:
            template_name: 模板文件名
            
        Returns:
            bool: 模板文件是否有效
        """
        try:
            return self.template_parser.template_exists(template_name)
        except Exception as e:
            logger.error(f"验证模板文件失败: {e}")
            return False
    
    def _generate_mapping_suggestions(self, invalid_mappings: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        为无效映射生成修复建议
        
        Args:
            invalid_mappings: 无效映射列表 [(hotkey, template), ...]
            
        Returns:
            Dict[str, str]: 建议的修复方案 {hotkey: suggested_template}
        """
        suggestions = {}
        available_templates = self.get_available_templates()
        
        for hotkey, invalid_template in invalid_mappings:
            # 尝试找到最相似的模板文件
            best_match = self._find_best_template_match(invalid_template, available_templates)
            if best_match:
                suggestions[hotkey] = best_match
                
        return suggestions
    
    def _find_best_template_match(self, target: str, available: List[str]) -> Optional[str]:
        """
        找到最匹配的模板文件
        
        Args:
            target: 目标模板名
            available: 可用模板列表
            
        Returns:
            Optional[str]: 最匹配的模板文件名
        """
        if not available:
            return None
            
        target_lower = target.lower().replace('.md', '').replace('_', '').replace('-', '')
        
        best_score = 0
        best_match = None
        
        for template in available:
            template_lower = template.lower().replace('.md', '').replace('_', '').replace('-', '')
            
            # 计算相似度（简单的字符串匹配）
            score = 0
            if target_lower in template_lower or template_lower in target_lower:
                score += 3
            
            # 计算共同字符数
            common_chars = sum(1 for c in target_lower if c in template_lower)
            score += common_chars
            
            if score > best_score:
                best_score = score
                best_match = template
                
        return best_match if best_score > 0 else available[0]
    
    def _start_template_monitoring(self) -> None:
        """启动模板目录监控"""
        try:
            if self._template_observer:
                return  # 已经在监控中
                
            event_handler = TemplateDirectoryHandler(self)
            self._template_observer = Observer()
            self._template_observer.schedule(
                event_handler, 
                str(self.template_dir), 
                recursive=False
            )
            self._template_observer.start()
            logger.info(f"启动模板目录监控: {self.template_dir}")
            
        except Exception as e:
            logger.error(f"启动模板目录监控失败: {e}")
    
    def _stop_template_monitoring(self) -> None:
        """停止模板目录监控"""
        try:
            if self._template_observer:
                self._template_observer.stop()
                self._template_observer.join(timeout=1.0)
                self._template_observer = None
                logger.info("停止模板目录监控")
                
        except Exception as e:
            logger.error(f"停止模板目录监控失败: {e}")
    
    def _update_template_mappings(self) -> None:
        """更新模板映射（当模板文件发生变化时调用）"""
        try:
            logger.info("更新模板映射...")
            
            # 重新验证现有映射
            current_mappings = self.config_manager.get_all_mappings()
            self._validate_template_mappings(current_mappings)
            
            # 清除缓存
            self._template_cache.clear()
            
            # 检查是否有新的模板文件可以自动映射
            auto_mappings = self._generate_auto_mappings()
            if auto_mappings:
                logger.info(f"发现可自动映射的模板: {auto_mappings}")
                
        except Exception as e:
            logger.error(f"更新模板映射失败: {e}")
    
    def _generate_auto_mappings(self) -> Dict[str, str]:
        """
        生成自动映射建议
        
        Returns:
            Dict[str, str]: 自动映射建议 {hotkey: template}
        """
        auto_mappings = {}
        available_templates = self.get_available_templates()
        current_mappings = self.config_manager.get_all_mappings()
        used_templates = set(current_mappings.values())
        available_hotkeys = self.get_available_hotkeys()
        
        # 找到未被映射的模板
        unmapped_templates = [t for t in available_templates if t not in used_templates]
        
        # 找到未被使用的快捷键
        unused_hotkeys = [h for h in available_hotkeys if h not in current_mappings]
        
        # 生成智能映射
        for i, template in enumerate(unmapped_templates[:len(unused_hotkeys)]):
            hotkey = unused_hotkeys[i]
            auto_mappings[hotkey] = template
            
        return auto_mappings
    
    def get_available_templates(self) -> List[str]:
        """
        获取可用的模板文件列表
        
        Returns:
            List[str]: 可用模板文件名列表
        """
        try:
            return self.template_parser.get_available_templates()
        except Exception as e:
            logger.error(f"获取可用模板列表失败: {e}")
            return []
    
    def get_available_hotkeys(self) -> List[str]:
        """
        获取可用的快捷键列表
        
        Returns:
            List[str]: 可用快捷键列表
        """
        return [f"ctrl+alt+cmd+{i}" for i in range(1, 10)]
    
    def add_dynamic_mapping(self, hotkey: str, template: str, validate: bool = True) -> bool:
        """
        动态添加快捷键映射
        
        Args:
            hotkey: 快捷键字符串
            template: 模板文件名
            validate: 是否验证模板文件
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 验证快捷键格式
            if hotkey not in self.get_supported_hotkeys():
                logger.error(f"不支持的快捷键格式: {hotkey}")
                return False
                
            # 验证模板文件
            if validate and not self._is_template_valid(template):
                logger.error(f"模板文件不存在或无效: {template}")
                return False
                
            # 更新配置
            self.config_manager.set_hotkey_mapping(hotkey, template)
            logger.info(f"动态添加映射: {hotkey} -> {template}")
            
            # 重新设置映射
            self._setup_hotkey_mappings()
            return True
            
        except Exception as e:
            logger.error(f"动态添加映射失败: {e}")
            return False
    
    def remove_dynamic_mapping(self, hotkey: str) -> bool:
        """
        动态移除快捷键映射
        
        Args:
            hotkey: 快捷键字符串
            
        Returns:
            bool: 移除是否成功
        """
        try:
            # 从配置中移除
            current_mappings = self.config_manager.get_all_mappings()
            if hotkey in current_mappings:
                del current_mappings[hotkey]
                self.config_manager.save_config({
                    'hotkeys': current_mappings,
                    'settings': self.config_manager.get('settings', {})
                })
                
                # 取消注册处理函数
                self.unregister_hotkey_handler(hotkey)
                logger.info(f"动态移除映射: {hotkey}")
                return True
            else:
                logger.warning(f"快捷键映射不存在: {hotkey}")
                return False
                
        except Exception as e:
            logger.error(f"动态移除映射失败: {e}")
            return False
    
    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        获取模板文件信息
        
        Args:
            template_name: 模板文件名
            
        Returns:
            Optional[Dict[str, Any]]: 模板信息，如果不存在则返回None
        """
        try:
            if template_name in self._template_cache:
                return self._template_cache[template_name]
                
            if not self._is_template_valid(template_name):
                return None
                
            template_path = self.template_parser.scanner.find_template_by_name(template_name)
            if template_path:
                info = {
                    'name': template_name,
                    'path': str(template_path),
                    'exists': True,
                    'size': template_path.stat().st_size,
                    'modified': template_path.stat().st_mtime
                }
                
                # 尝试解析模板内容获取更多信息
                try:
                    content = self.template_parser.reader.parse_template_file(template_path)
                    info.update({
                        'model': content.get_model_name(),
                        'placeholders': content.find_placeholders(),
                        'placeholder_count': content.get_placeholder_count()
                    })
                except Exception:
                    pass  # 解析失败不影响基本信息
                    
                # 缓存信息
                self._template_cache[template_name] = info
                return info
                
        except Exception as e:
            logger.error(f"获取模板信息失败: {e}")
            
        return None
    
    def get_mapping_status(self) -> Dict[str, Any]:
        """
        获取映射状态信息
        
        Returns:
            Dict[str, Any]: 映射状态信息
        """
        current_mappings = self.config_manager.get_all_mappings()
        available_templates = self.get_available_templates()
        
        valid_mappings = {}
        invalid_mappings = {}
        
        for hotkey, template in current_mappings.items():
            if self._is_template_valid(template):
                valid_mappings[hotkey] = template
            else:
                invalid_mappings[hotkey] = template
                
        return {
            'total_mappings': len(current_mappings),
            'valid_mappings': len(valid_mappings),
            'invalid_mappings': len(invalid_mappings),
            'available_templates': len(available_templates),
            'unused_templates': [t for t in available_templates if t not in current_mappings.values()],
            'unused_hotkeys': [h for h in self.get_available_hotkeys() if h not in current_mappings],
            'mappings': {
                'valid': valid_mappings,
                'invalid': invalid_mappings
            },
            'suggestions': self._generate_auto_mappings()
        }
    
    def _detect_hotkey_conflicts(self, mappings: Dict[str, str]) -> Set[str]:
        """
        检测快捷键冲突
        
        Args:
            mappings: 快捷键映射字典
            
        Returns:
            冲突的快捷键集合
        """
        conflicts = set()
        hotkeys = list(mappings.keys())
        
        for i, hotkey1 in enumerate(hotkeys):
            for hotkey2 in hotkeys[i+1:]:
                if self._normalize_hotkey_string(hotkey1) == self._normalize_hotkey_string(hotkey2):
                    conflicts.add(hotkey1)
                    conflicts.add(hotkey2)
                    
        return conflicts
    
    def _detect_advanced_conflicts(self, mappings: Dict[str, str]) -> Dict[str, List[str]]:
        """
        检测高级快捷键冲突，包括系统保留快捷键和应用冲突
        
        Args:
            mappings: 快捷键映射字典
            
        Returns:
            Dict[str, List[str]]: 冲突类型到快捷键列表的映射
        """
        conflicts = {
            'system_reserved': [],
            'application_conflicts': [],
            'duplicate_mappings': [],
            'invalid_format': []
        }
        
        # macOS系统保留的快捷键组合
        system_reserved = {
            'cmd+space': 'Spotlight搜索',
            'cmd+tab': '应用切换',
            'cmd+shift+3': '屏幕截图',
            'cmd+shift+4': '区域截图',
            'ctrl+up': 'Mission Control',
            'ctrl+down': '应用窗口',
            'cmd+ctrl+space': '字符查看器'
        }
        
        # 检查每个映射
        for hotkey in mappings.keys():
            # 检查格式是否有效
            if not self._is_valid_hotkey_format(hotkey):
                conflicts['invalid_format'].append(hotkey)
                continue
                
            # 检查是否与系统快捷键冲突
            normalized = self._normalize_hotkey_string(hotkey)
            if normalized in system_reserved:
                conflicts['system_reserved'].append(hotkey)
                
            # 检查是否与常见应用快捷键冲突
            if self._is_application_conflict(normalized):
                conflicts['application_conflicts'].append(hotkey)
        
        # 检查重复映射
        seen_hotkeys = {}
        for hotkey in mappings.keys():
            normalized = self._normalize_hotkey_string(hotkey)
            if normalized in seen_hotkeys:
                conflicts['duplicate_mappings'].extend([hotkey, seen_hotkeys[normalized]])
            else:
                seen_hotkeys[normalized] = hotkey
                
        return conflicts
    
    def _is_valid_hotkey_format(self, hotkey: str) -> bool:
        """
        验证快捷键格式是否有效
        
        Args:
            hotkey: 快捷键字符串
            
        Returns:
            bool: 格式是否有效
        """
        try:
            parts = hotkey.lower().split('+')
            
            # 必须包含修饰键和数字键
            if len(parts) != 4:
                return False
                
            # 检查修饰键
            required_modifiers = {'ctrl', 'alt', 'cmd'}
            modifier_parts = set(parts[:3])
            if not required_modifiers.issubset(modifier_parts):
                return False
                
            # 检查数字键
            number_part = parts[3]
            if not (number_part.isdigit() and number_part in '123456789'):
                return False
                
            return True
            
        except Exception:
            return False
    
    def _is_application_conflict(self, normalized_hotkey: str) -> bool:
        """
        检查是否与常见应用快捷键冲突
        
        Args:
            normalized_hotkey: 标准化的快捷键字符串
            
        Returns:
            bool: 是否存在应用冲突
        """
        # 常见应用快捷键模式
        common_app_shortcuts = [
            'cmd+c', 'cmd+v', 'cmd+x', 'cmd+z', 'cmd+y',  # 基本编辑
            'cmd+s', 'cmd+o', 'cmd+n', 'cmd+w', 'cmd+q',  # 文件操作
            'cmd+f', 'cmd+g', 'cmd+r', 'cmd+t',           # 查找和刷新
            'alt+tab', 'ctrl+tab',                        # 切换操作
        ]
        
        # 检查部分匹配
        for app_shortcut in common_app_shortcuts:
            if app_shortcut in normalized_hotkey or normalized_hotkey in app_shortcut:
                return True
                
        return False
    
    def resolve_conflicts(self, conflicts: Dict[str, List[str]]) -> Dict[str, Dict[str, str]]:
        """
        为冲突的快捷键提供解决方案
        
        Args:
            conflicts: 冲突信息字典
            
        Returns:
            Dict[str, Dict[str, str]]: 解决方案 {conflict_type: {old_hotkey: suggested_hotkey}}
        """
        solutions = {}
        available_hotkeys = self._get_available_hotkeys()
        
        for conflict_type, conflicted_hotkeys in conflicts.items():
            if not conflicted_hotkeys:
                continue
                
            solutions[conflict_type] = {}
            
            for hotkey in conflicted_hotkeys:
                if conflict_type == 'invalid_format':
                    # 尝试修复格式错误
                    fixed_hotkey = self._fix_hotkey_format(hotkey)
                    if fixed_hotkey and fixed_hotkey in available_hotkeys:
                        solutions[conflict_type][hotkey] = fixed_hotkey
                        available_hotkeys.remove(fixed_hotkey)
                        
                elif conflict_type in ['system_reserved', 'application_conflicts', 'duplicate_mappings']:
                    # 为冲突的快捷键分配新的可用快捷键
                    if available_hotkeys:
                        new_hotkey = available_hotkeys.pop(0)
                        solutions[conflict_type][hotkey] = new_hotkey
                        
        return solutions
    
    def _fix_hotkey_format(self, hotkey: str) -> Optional[str]:
        """
        尝试修复快捷键格式错误
        
        Args:
            hotkey: 有问题的快捷键字符串
            
        Returns:
            Optional[str]: 修复后的快捷键，如果无法修复则返回None
        """
        try:
            # 统一转换为小写并分割
            parts = hotkey.lower().replace(' ', '').split('+')
            
            # 尝试识别并修复常见错误
            fixed_parts = []
            number_found = False
            
            for part in parts:
                # 修复修饰键别名
                if part in ['control', 'ctl']:
                    fixed_parts.append('ctrl')
                elif part in ['option', 'opt']:
                    fixed_parts.append('alt')
                elif part in ['command', 'cmd']:
                    fixed_parts.append('cmd')
                elif part in ['ctrl', 'alt', 'cmd']:
                    fixed_parts.append(part)
                elif part.isdigit() and part in '123456789' and not number_found:
                    fixed_parts.append(part)
                    number_found = True
                    
            # 确保包含所有必需的修饰键
            required = {'ctrl', 'alt', 'cmd'}
            if required.issubset(set(fixed_parts)) and number_found:
                # 重新排序：ctrl+alt+cmd+数字
                result = ['ctrl', 'alt', 'cmd']
                for part in fixed_parts:
                    if part.isdigit():
                        result.append(part)
                        break
                return '+'.join(result)
                
        except Exception:
            pass
            
        return None
    
    def _get_available_hotkeys(self) -> List[str]:
        """
        获取当前可用的快捷键列表
        
        Returns:
            List[str]: 可用快捷键列表
        """
        all_possible = [f"ctrl+alt+cmd+{i}" for i in range(1, 10)]
        current_mappings = self.config_manager.get_all_mappings()
        used_hotkeys = set(current_mappings.keys())
        
        return [hk for hk in all_possible if hk not in used_hotkeys]
    
    def validate_hotkey_configuration(self) -> Dict[str, Any]:
        """
        全面验证快捷键配置
        
        Returns:
            Dict[str, Any]: 验证结果，包含错误、警告和建议
        """
        mappings = self.config_manager.get_all_mappings()
        
        # 基础冲突检测
        basic_conflicts = self._detect_hotkey_conflicts(mappings)
        
        # 高级冲突检测
        advanced_conflicts = self._detect_advanced_conflicts(mappings)
        
        # 模板文件验证
        template_issues = self._validate_all_templates(mappings)
        
        # 生成解决方案
        solutions = self.resolve_conflicts(advanced_conflicts)
        
        # 计算健康度评分
        health_score = self._calculate_config_health(mappings, basic_conflicts, advanced_conflicts, template_issues)
        
        return {
            'is_valid': len(basic_conflicts) == 0 and all(not v for v in advanced_conflicts.values()),
            'health_score': health_score,
            'basic_conflicts': list(basic_conflicts),
            'advanced_conflicts': advanced_conflicts,
            'template_issues': template_issues,
            'solutions': solutions,
            'total_mappings': len(mappings),
            'valid_mappings': len(mappings) - len(basic_conflicts) - sum(len(v) for v in advanced_conflicts.values()),
            'recommendations': self._generate_configuration_recommendations(mappings, advanced_conflicts)
        }
    
    def _validate_all_templates(self, mappings: Dict[str, str]) -> Dict[str, List[str]]:
        """
        验证所有模板文件
        
        Args:
            mappings: 快捷键映射字典
            
        Returns:
            Dict[str, List[str]]: 模板问题分类
        """
        issues = {
            'missing_files': [],
            'invalid_format': [],
            'empty_files': [],
            'permission_errors': []
        }
        
        for hotkey, template in mappings.items():
            try:
                if not self.template_parser.template_exists(template):
                    issues['missing_files'].append(f"{hotkey} -> {template}")
                    continue
                    
                # 检查文件是否可读
                template_path = self.template_parser.scanner.find_template_by_name(template)
                if template_path:
                    try:
                        content = template_path.read_text(encoding='utf-8')
                        if not content.strip():
                            issues['empty_files'].append(f"{hotkey} -> {template}")
                        else:
                            # 尝试解析模板验证格式
                            try:
                                self.template_parser.reader.parse_template_file(template_path)
                            except Exception:
                                issues['invalid_format'].append(f"{hotkey} -> {template}")
                    except PermissionError:
                        issues['permission_errors'].append(f"{hotkey} -> {template}")
                        
            except Exception as e:
                logger.error(f"验证模板文件时出错: {e}")
                issues['invalid_format'].append(f"{hotkey} -> {template}")
                
        return issues
    
    def _calculate_config_health(self, mappings: Dict[str, str], basic_conflicts: Set[str], 
                               advanced_conflicts: Dict[str, List[str]], template_issues: Dict[str, List[str]]) -> float:
        """
        计算配置健康度评分 (0-100)
        
        Args:
            mappings: 快捷键映射
            basic_conflicts: 基础冲突
            advanced_conflicts: 高级冲突  
            template_issues: 模板问题
            
        Returns:
            float: 健康度评分
        """
        if not mappings:
            return 0.0
            
        total_issues = (
            len(basic_conflicts) +
            sum(len(v) for v in advanced_conflicts.values()) +
            sum(len(v) for v in template_issues.values())
        )
        
        total_mappings = len(mappings)
        
        # 基础分数
        base_score = max(0, 100 - (total_issues / total_mappings * 50))
        
        # 奖励分：配置完整性
        completeness_bonus = min(20, total_mappings / 9 * 20)  # 最多9个快捷键
        
        # 惩罚：严重问题
        severe_penalty = len(template_issues.get('missing_files', [])) * 10
        
        final_score = min(100, max(0, base_score + completeness_bonus - severe_penalty))
        return round(final_score, 1)
    
    def _generate_configuration_recommendations(self, mappings: Dict[str, str], 
                                              conflicts: Dict[str, List[str]]) -> List[str]:
        """
        生成配置建议
        
        Args:
            mappings: 快捷键映射
            conflicts: 冲突信息
            
        Returns:
            List[str]: 建议列表
        """
        recommendations = []
        
        # 检查映射完整性
        if len(mappings) < 3:
            recommendations.append("建议至少配置3个常用的快捷键映射")
            
        if len(mappings) == 9:
            recommendations.append("已配置满所有可用的快捷键位置，配置非常完整")
            
        # 冲突相关建议
        if conflicts.get('system_reserved'):
            recommendations.append("避免使用系统保留的快捷键，可能导致功能冲突")
            
        if conflicts.get('duplicate_mappings'):
            recommendations.append("移除重复的快捷键映射，保持配置清洁")
            
        if conflicts.get('invalid_format'):
            recommendations.append("修复格式错误的快捷键定义")
            
        # 使用模式建议
        available = self._get_available_hotkeys()
        if available:
            recommendations.append(f"还有 {len(available)} 个快捷键位置可用，考虑添加更多模板")
            
        return recommendations
    
    def apply_conflict_solutions(self, solutions: Dict[str, Dict[str, str]], auto_apply: bool = False) -> Dict[str, Any]:
        """
        应用冲突解决方案
        
        Args:
            solutions: 解决方案字典
            auto_apply: 是否自动应用所有解决方案
            
        Returns:
            Dict[str, Any]: 应用结果
        """
        results = {
            'applied': [],
            'failed': [],
            'skipped': [],
            'backup_created': False
        }
        
        try:
            # 创建配置备份
            backup_success = self._create_config_backup()
            results['backup_created'] = backup_success
            
            current_mappings = self.config_manager.get_all_mappings().copy()
            
            for conflict_type, hotkey_solutions in solutions.items():
                for old_hotkey, new_hotkey in hotkey_solutions.items():
                    try:
                        if auto_apply or self._should_apply_solution(conflict_type, old_hotkey, new_hotkey):
                            # 获取原模板
                            template = current_mappings.get(old_hotkey)
                            if template:
                                # 移除旧映射
                                if old_hotkey in current_mappings:
                                    del current_mappings[old_hotkey]
                                    
                                # 添加新映射
                                current_mappings[new_hotkey] = template
                                
                                results['applied'].append({
                                    'conflict_type': conflict_type,
                                    'old_hotkey': old_hotkey,
                                    'new_hotkey': new_hotkey,
                                    'template': template
                                })
                                
                                logger.info(f"已应用冲突解决方案: {old_hotkey} -> {new_hotkey}")
                            else:
                                results['failed'].append({
                                    'hotkey': old_hotkey,
                                    'reason': '找不到对应的模板'
                                })
                        else:
                            results['skipped'].append({
                                'conflict_type': conflict_type,
                                'old_hotkey': old_hotkey,
                                'new_hotkey': new_hotkey
                            })
                            
                    except Exception as e:
                        results['failed'].append({
                            'hotkey': old_hotkey,
                            'reason': str(e)
                        })
                        logger.error(f"应用解决方案失败: {e}")
            
            # 保存更新后的配置
            if results['applied']:
                self.config_manager.save_config({
                    'hotkeys': current_mappings,
                    'settings': self.config_manager.get('settings', {})
                })
                
                # 重新设置映射
                self._setup_hotkey_mappings()
                
        except Exception as e:
            logger.error(f"应用冲突解决方案时出错: {e}")
            results['failed'].append({'error': str(e)})
            
        return results
    
    def _create_config_backup(self) -> bool:
        """
        创建配置文件备份
        
        Returns:
            bool: 备份是否成功
        """
        try:
            import shutil
            import datetime
            
            config_path = self.config_manager.config_path
            if config_path.exists():
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = config_path.with_suffix(f".yaml.backup_{timestamp}")
                shutil.copy2(config_path, backup_path)
                logger.info(f"配置备份已创建: {backup_path}")
                return True
                
        except Exception as e:
            logger.error(f"创建配置备份失败: {e}")
            
        return False
    
    def _should_apply_solution(self, conflict_type: str, old_hotkey: str, new_hotkey: str) -> bool:
        """
        判断是否应该应用某个解决方案（可扩展为交互式确认）
        
        Args:
            conflict_type: 冲突类型
            old_hotkey: 原快捷键
            new_hotkey: 新快捷键
            
        Returns:
            bool: 是否应该应用
        """
        # 默认策略：自动修复格式错误，其他类型需要确认
        auto_apply_types = ['invalid_format']
        return conflict_type in auto_apply_types
    
    def _normalize_hotkey_string(self, hotkey: str) -> str:
        """
        标准化快捷键字符串格式
        
        Args:
            hotkey: 快捷键字符串
            
        Returns:
            标准化的快捷键字符串
        """
        # 修饰键别名映射
        key_aliases = {
            'control': 'ctrl',
            'ctl': 'ctrl',
            'option': 'alt',
            'opt': 'alt',
            'command': 'cmd',
            'win': 'cmd',  # Windows键也映射到cmd
            'super': 'cmd'
        }
        
        parts = hotkey.lower().replace(' ', '').split('+')
        normalized_parts = []
        
        for part in parts:
            # 处理修饰键别名
            if part in key_aliases:
                normalized_parts.append(key_aliases[part])
            else:
                normalized_parts.append(part)
                
        # 排序以确保一致性
        normalized_parts.sort()
        return '+'.join(normalized_parts)
    
    def _normalize_hotkey(self, keys: set) -> Optional[str]:
        """
        将按键集合标准化为快捷键字符串
        
        Args:
            keys: 当前按下的按键集合
            
        Returns:
            标准化的快捷键字符串，如果不匹配则返回None
        """
        # macOS平台的按键映射处理
        if self._platform == "Darwin":
            normalized_keys = set()
            for key in keys:
                if key in self.MACOS_KEY_MAPPING:
                    normalized_keys.add(self.MACOS_KEY_MAPPING[key])
                else:
                    normalized_keys.add(key)
            keys = normalized_keys
        
        # 检查是否包含必需的修饰键: ctrl + alt + cmd
        has_ctrl = any(key in keys for key in [Key.ctrl_l, Key.ctrl_r, Key.ctrl])
        has_alt = any(key in keys for key in [Key.alt_l, Key.alt_r, Key.alt]) 
        has_cmd = any(key in keys for key in [Key.cmd, Key.cmd_r])
        
        if not (has_ctrl and has_alt and has_cmd):
            return None
            
        # 检查数字键 1-9
        number_key = None
        for key in keys:
            if hasattr(key, 'char') and key.char and key.char.isdigit():
                if key.char in '123456789':
                    number_key = key.char
                    break
            # 处理KeyCode类型的数字键
            elif hasattr(key, 'vk') and key.vk:
                # macOS数字键的virtual key codes (49-57对应1-9)
                if 49 <= key.vk <= 57:
                    number_key = str(key.vk - 48)
                    break
        
        if not number_key:
            return None
            
        return f"ctrl+alt+cmd+{number_key}"
    
    def _on_press(self, key):
        """按键按下事件处理"""
        try:
            self._pressed_keys.add(key)
            
            # 检查是否形成了完整的快捷键组合
            hotkey = self._normalize_hotkey(self._pressed_keys)
            if hotkey:
                logger.debug(f"检测到快捷键: {hotkey} (平台: {self._platform})")
                self._handle_hotkey(hotkey)
                
                # 防止重复触发，清除已按下的按键
                self._pressed_keys.clear()
                
        except Exception as e:
            logger.error(f"按键处理异常: {e}")
    
    def _on_release(self, key):
        """按键释放事件处理"""
        try:
            # 从已按下的按键集合中移除
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)
                
        except Exception as e:
            logger.error(f"按键释放处理异常: {e}")
    

    
    def register_hotkey_handler(self, hotkey: str, handler: Callable[[str], None]) -> None:
        """
        注册快捷键处理函数
        
        Args:
            hotkey: 快捷键字符串 (例如: "ctrl+alt+cmd+1")
            handler: 处理函数，接收模板文件名作为参数
        """
        self._hotkey_handlers[hotkey] = handler
        logger.info(f"注册快捷键处理函数: {hotkey}")
    
    def register_all_hotkeys(self, handler: Callable[[str], None]) -> None:
        """
        为所有配置的快捷键注册统一的处理函数
        
        Args:
            handler: 处理函数，接收模板文件名作为参数
        """
        mappings = self.config_manager.get_all_mappings()
        for hotkey in mappings.keys():
            self.register_hotkey_handler(hotkey, handler)
    
    def unregister_hotkey_handler(self, hotkey: str) -> bool:
        """
        取消注册快捷键处理函数
        
        Args:
            hotkey: 快捷键字符串
            
        Returns:
            True if successfully unregistered, False if not found
        """
        if hotkey in self._hotkey_handlers:
            del self._hotkey_handlers[hotkey]
            logger.info(f"取消注册快捷键处理函数: {hotkey}")
            return True
        return False
    

    

    
    def reload_config(self) -> None:
        """重新加载配置文件"""
        try:
            logger.info("重新加载快捷键配置")
            self.config_manager.reload_config()
            
            if self.config_manager.validate_config():
                self._setup_hotkey_mappings()
                logger.info("快捷键配置重新加载成功")
            else:
                logger.error("快捷键配置验证失败")
                
        except Exception as e:
            logger.error(f"重新加载快捷键配置失败: {e}")
    
    def is_hotkey_enabled(self, hotkey: str) -> bool:
        """
        检查指定快捷键是否启用
        
        Args:
            hotkey: 快捷键字符串
            
        Returns:
            True if enabled, False otherwise
        """
        if not self.config_manager.get('settings.enabled', True):
            return False
            
        template = self.config_manager.get_template_for_hotkey(hotkey)
        return template is not None and self._is_template_valid(template)
    
    def get_supported_hotkeys(self) -> Set[str]:
        """
        获取支持的快捷键列表
        
        Returns:
            支持的快捷键集合
        """
        return {f"ctrl+alt+cmd+{i}" for i in range(1, 10)}
    

    

    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_listening()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_listening()
        self._stop_template_monitoring() 
    
    # ================= 后台监听状态管理功能 =================
    
    def _save_listening_state(self) -> None:
        """保存监听状态到文件"""
        try:
            state_data = {
                'is_listening': self.is_listening,
                'last_update': datetime.datetime.now().isoformat(),
                'statistics': self._listening_statistics,
                'auto_restart_enabled': self._auto_restart_enabled,
                'health_check_interval': self._health_check_interval,
                'platform': self._platform
            }
            
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"监听状态已保存到: {self._state_file}")
            
        except Exception as e:
            logger.error(f"保存监听状态失败: {e}")
    
    def _restore_listening_state(self) -> None:
        """从文件恢复监听状态"""
        try:
            if not self._state_file.exists():
                logger.info("状态文件不存在，跳过状态恢复")
                return
                
            with open(self._state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
                
            # 恢复配置
            self._auto_restart_enabled = state_data.get('auto_restart_enabled', True)
            self._health_check_interval = state_data.get('health_check_interval', 30)
            
            # 恢复统计信息
            if 'statistics' in state_data:
                saved_stats = state_data['statistics']
                self._listening_statistics.update(saved_stats)
                
            # 检查是否需要自动启动监听
            was_listening = state_data.get('is_listening', False)
            auto_start_enabled = self.config_manager.get('settings.auto_start', True)
            
            if was_listening and auto_start_enabled:
                logger.info("检测到上次程序运行时处于监听状态，自动启动监听")
                self.start_listening()
                
            logger.info("监听状态恢复完成")
            
        except Exception as e:
            logger.error(f"恢复监听状态失败: {e}")
    
    def _start_health_check(self) -> None:
        """启动健康检查线程"""
        if self._health_check_running:
            return
            
        self._health_check_running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="HotkeyListenerHealthCheck"
        )
        self._health_check_thread.start()
        logger.info(f"健康检查线程已启动，检查间隔: {self._health_check_interval}秒")
    
    def _stop_health_check(self) -> None:
        """停止健康检查线程"""
        self._health_check_running = False
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=2.0)
        self._health_check_thread = None
        logger.info("健康检查线程已停止")
    
    def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._health_check_running:
            try:
                # 检查监听器健康状态
                if self.is_listening and not self._is_listener_healthy():
                    logger.warning("检测到监听器不健康，尝试重启")
                    self._attempt_restart()
                
                # 更新运行时间统计
                self._update_uptime_statistics()
                
                # 保存当前状态
                self._save_listening_state()
                
                # 等待下次检查
                time.sleep(self._health_check_interval)
                
            except Exception as e:
                logger.error(f"健康检查过程中出错: {e}")
                self._listening_statistics['error_count'] += 1
                self._listening_statistics['last_error'] = str(e)
                time.sleep(5)  # 出错后短暂等待
    
    def _is_listener_healthy(self) -> bool:
        """检查监听器是否健康"""
        try:
            # 检查监听器对象是否存在且处于运行状态
            if not self.listener:
                return False
                
            # 检查监听器线程是否活跃
            if hasattr(self.listener, '_thread') and self.listener._thread:
                if not self.listener._thread.is_alive():
                    return False
            
            # 检查是否有异常状态
            if self._graceful_shutdown:
                return True  # 正在优雅关闭，认为是健康的
                
            return True
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False
    
    def _attempt_restart(self) -> bool:
        """尝试重启监听器"""
        try:
            # 检查重启限制
            current_time = time.time()
            if self._last_restart_time and (current_time - self._last_restart_time) < 60:
                # 1分钟内不重复重启
                return False
                
            if self._restart_attempts >= self._max_restart_attempts:
                logger.error(f"重启尝试次数已达上限 ({self._max_restart_attempts})，停止自动重启")
                self._auto_restart_enabled = False
                return False
            
            if not self._auto_restart_enabled:
                logger.info("自动重启已禁用，跳过重启")
                return False
                
            logger.info(f"尝试重启监听器 (第 {self._restart_attempts + 1} 次)")
            
            # 停止当前监听器
            self.stop_listening()
            time.sleep(1)  # 短暂等待
            
            # 重新启动
            success = self.start_listening()
            
            if success:
                self._restart_attempts = 0  # 重置重启计数
                self._listening_statistics['restart_count'] += 1
                logger.info("监听器重启成功")
            else:
                self._restart_attempts += 1
                logger.error("监听器重启失败")
                
            self._last_restart_time = current_time
            return success
            
        except Exception as e:
            logger.error(f"重启监听器时出错: {e}")
            self._restart_attempts += 1
            return False
    
    def _update_uptime_statistics(self) -> None:
        """更新运行时间统计"""
        if self._listening_statistics['start_time']:
            start_time = datetime.datetime.fromisoformat(self._listening_statistics['start_time'])
            current_time = datetime.datetime.now()
            self._listening_statistics['uptime'] = (current_time - start_time).total_seconds()
    

    

    
    def _handle_hotkey(self, hotkey: str) -> None:
        """
        处理快捷键事件（增强版）
        
        Args:
            hotkey: 快捷键字符串
        """
        try:
            # 更新统计
            self._listening_statistics['total_hotkeys_processed'] += 1
            
            # 检查快捷键是否启用
            if not self.config_manager.get('settings.enabled', True):
                logger.debug("快捷键监听已禁用")
                return
                
            template = self.config_manager.get_template_for_hotkey(hotkey)
            if not template:
                logger.warning(f"未找到快捷键对应的模板: {hotkey}")
                return
                
            # 验证模板文件是否存在
            if not self._is_template_valid(template):
                logger.error(f"模板文件不存在或无效: {template}")
                return
                
            logger.info(f"触发快捷键: {hotkey} -> {template}")
            
            # 调用注册的处理函数
            if hotkey in self._hotkey_handlers:
                handler = self._hotkey_handlers[hotkey]
                # 在单独的线程中处理，避免阻塞监听器
                threading.Thread(
                    target=handler,
                    args=(template,),
                    daemon=True,
                    name=f"HotkeyHandler-{hotkey}"
                ).start()
            else:
                logger.warning(f"未注册处理函数: {hotkey}")
                
        except Exception as e:
            logger.error(f"快捷键处理失败: {e}")
            self._listening_statistics['error_count'] += 1
            self._listening_statistics['last_error'] = str(e)
    
    def get_listening_status(self) -> Dict[str, Any]:
        """
        获取详细的监听状态信息
        
        Returns:
            Dict[str, Any]: 监听状态信息
        """
        self._update_uptime_statistics()
        
        return {
            'is_listening': self.is_listening,
            'is_healthy': self._is_listener_healthy() if self.is_listening else None,
            'auto_restart_enabled': self._auto_restart_enabled,
            'health_check_running': self._health_check_running,
            'health_check_interval': self._health_check_interval,
            'restart_attempts': self._restart_attempts,
            'max_restart_attempts': self._max_restart_attempts,
            'statistics': self._listening_statistics.copy(),
            'state_file_exists': self._state_file.exists(),
            'graceful_shutdown': self._graceful_shutdown
        }
    
    def set_auto_restart(self, enabled: bool) -> None:
        """
        设置自动重启功能
        
        Args:
            enabled: 是否启用自动重启
        """
        self._auto_restart_enabled = enabled
        logger.info(f"自动重启功能已{'启用' if enabled else '禁用'}")
        self._save_listening_state()
    
    def set_health_check_interval(self, interval: int) -> None:
        """
        设置健康检查间隔
        
        Args:
            interval: 检查间隔（秒）
        """
        if interval < 5:
            raise ValueError("健康检查间隔不能小于5秒")
            
        self._health_check_interval = interval
        logger.info(f"健康检查间隔已设置为 {interval} 秒")
        self._save_listening_state()
    
    def reset_restart_attempts(self) -> None:
        """重置重启尝试计数"""
        self._restart_attempts = 0
        self._auto_restart_enabled = True
        logger.info("重启尝试计数已重置")
    
    def force_restart(self) -> bool:
        """
        强制重启监听器
        
        Returns:
            bool: 重启是否成功
        """
        logger.info("执行强制重启")
        old_auto_restart = self._auto_restart_enabled
        self._auto_restart_enabled = True
        
        success = self._attempt_restart()
        
        self._auto_restart_enabled = old_auto_restart
        return success
    
    def get_hotkey_info(self) -> Dict[str, Any]:
        """
        获取快捷键监听器状态信息（增强版）
        
        Returns:
            包含监听器状态的字典
        """
        mapping_status = self.get_mapping_status()
        listening_status = self.get_listening_status()
        config_reload_status = self.get_config_reload_status()
        
        return {
            'is_listening': self.is_listening,
            'enabled': self.config_manager.get('settings.enabled', True),
            'mappings_count': len(self.config_manager.get_all_mappings()),
            'handlers_count': len(self._hotkey_handlers),
            'response_delay': self.config_manager.get('settings.response_delay', 100),
            'platform_info': self.get_platform_info(),
            'mapping_status': mapping_status,
            'template_monitoring': self._template_observer is not None,
            'listening_status': listening_status,
            'config_reload_status': config_reload_status
        } 
    
    # ================= 配置热重载功能 =================
    
    def _start_config_monitoring(self) -> None:
        """启动配置文件监控"""
        try:
            if not self._config_reload_enabled:
                logger.info("配置热重载已禁用，跳过监控启动")
                return
                
            # 启动配置管理器的文件监控
            self.config_manager.start_watching()
            
            # 注册配置变化回调
            original_reload = self.config_manager.reload_config
            
            def enhanced_reload():
                """增强的配置重载函数"""
                self._on_config_changed()
                
            # 替换原来的重载方法
            self.config_manager.reload_config = enhanced_reload
            
            # 计算初始配置哈希
            self._last_config_hash = self._calculate_config_hash()
            
            logger.info("配置文件热重载监控已启动")
            
        except Exception as e:
            logger.error(f"启动配置文件监控失败: {e}")
    
    def _stop_config_monitoring(self) -> None:
        """停止配置文件监控"""
        try:
            self.config_manager.stop_watching()
            logger.info("配置文件热重载监控已停止")
        except Exception as e:
            logger.error(f"停止配置文件监控失败: {e}")
    
    def _on_config_changed(self) -> None:
        """配置文件变化处理"""
        import time
        import hashlib
        
        current_time = time.time()
        
        # 防抖处理
        if (current_time - self._last_config_reload_time) < self._config_reload_debounce_time:
            logger.debug("配置重载防抖，跳过本次重载")
            return
            
        self._last_config_reload_time = current_time
        
        try:
            start_time = time.time()
            self._config_reload_statistics['total_reloads'] += 1
            
            logger.info("检测到配置文件变化，开始热重载...")
            
            # 备份当前配置
            old_mappings = self.config_manager.get_all_mappings().copy()
            old_enabled = self.config_manager.get('settings.enabled', True)
            
            # 重新加载配置
            self.config_manager.load_config()
            
            # 验证新配置
            if not self.config_manager.validate_config():
                logger.error("新配置验证失败，保持当前配置")
                self._config_reload_statistics['failed_reloads'] += 1
                return
                
            # 检查配置是否真正发生变化
            new_config_hash = self._calculate_config_hash()
            if new_config_hash == self._last_config_hash:
                logger.debug("配置内容未发生实际变化，跳过重载")
                return
                
            # 获取新配置
            new_mappings = self.config_manager.get_all_mappings()
            new_enabled = self.config_manager.get('settings.enabled', True)
            
            # 分析配置变化
            changes = self._analyze_config_changes(old_mappings, new_mappings, old_enabled, new_enabled)
            
            # 应用配置变化
            self._apply_config_changes(changes)
            
            # 重新设置快捷键映射
            self._setup_hotkey_mappings()
            
            # 更新配置哈希
            self._last_config_hash = new_config_hash
            
            # 更新统计信息
            reload_duration = time.time() - start_time
            self._config_reload_statistics.update({
                'successful_reloads': self._config_reload_statistics['successful_reloads'] + 1,
                'last_reload_time': datetime.datetime.now().isoformat(),
                'last_reload_duration': reload_duration,
                'last_reload_error': None
            })
            
            # 调用回调函数
            self._notify_config_reload_callbacks(changes)
            
            logger.info(f"配置热重载成功完成，耗时 {reload_duration:.2f} 秒")
            
        except Exception as e:
            error_msg = f"配置热重载失败: {e}"
            logger.error(error_msg)
            
            self._config_reload_statistics.update({
                'failed_reloads': self._config_reload_statistics['failed_reloads'] + 1,
                'last_reload_error': str(e)
            })
    
    def _calculate_config_hash(self) -> str:
        """计算配置内容的哈希值"""
        import hashlib
        import json
        
        try:
            # 获取关键配置项
            config_data = {
                'hotkeys': self.config_manager.get('hotkeys', {}),
                'settings': self.config_manager.get('settings', {})
            }
            
            # 计算哈希
            config_str = json.dumps(config_data, sort_keys=True)
            return hashlib.md5(config_str.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"计算配置哈希失败: {e}")
            return ""
    
    def _analyze_config_changes(self, old_mappings: Dict[str, str], new_mappings: Dict[str, str],
                              old_enabled: bool, new_enabled: bool) -> Dict[str, Any]:
        """分析配置变化"""
        changes = {
            'enabled_changed': old_enabled != new_enabled,
            'old_enabled': old_enabled,
            'new_enabled': new_enabled,
            'added_hotkeys': {},
            'removed_hotkeys': {},
            'modified_hotkeys': {},
            'unchanged_hotkeys': {}
        }
        
        # 找出新增的快捷键
        for hotkey, template in new_mappings.items():
            if hotkey not in old_mappings:
                changes['added_hotkeys'][hotkey] = template
                
        # 找出删除的快捷键
        for hotkey, template in old_mappings.items():
            if hotkey not in new_mappings:
                changes['removed_hotkeys'][hotkey] = template
                
        # 找出修改的快捷键
        for hotkey, template in new_mappings.items():
            if hotkey in old_mappings and old_mappings[hotkey] != template:
                changes['modified_hotkeys'][hotkey] = {
                    'old': old_mappings[hotkey],
                    'new': template
                }
                
        # 找出未变化的快捷键
        for hotkey, template in new_mappings.items():
            if hotkey in old_mappings and old_mappings[hotkey] == template:
                changes['unchanged_hotkeys'][hotkey] = template
                
        return changes
    
    def _apply_config_changes(self, changes: Dict[str, Any]) -> None:
        """应用配置变化"""
        try:
            # 移除已删除的快捷键处理函数
            for hotkey in changes['removed_hotkeys']:
                self.unregister_hotkey_handler(hotkey)
                logger.info(f"移除快捷键处理函数: {hotkey}")
                
            # 为新增和修改的快捷键重新注册处理函数
            # 注意：这里需要外部调用者重新注册处理函数
            # 因为HotkeyListener不知道具体的处理逻辑
            
            logger.info(f"配置变化应用完成: 新增 {len(changes['added_hotkeys'])} 个，"
                       f"删除 {len(changes['removed_hotkeys'])} 个，"
                       f"修改 {len(changes['modified_hotkeys'])} 个")
                       
        except Exception as e:
            logger.error(f"应用配置变化失败: {e}")
    
    def _notify_config_reload_callbacks(self, changes: Dict[str, Any]) -> None:
        """通知配置重载回调函数"""
        for callback in self._config_reload_callbacks:
            try:
                callback(changes)
            except Exception as e:
                logger.error(f"执行配置重载回调失败: {e}")
    
    def add_config_reload_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        添加配置重载回调函数
        
        Args:
            callback: 回调函数，接收配置变化信息作为参数
        """
        if callback not in self._config_reload_callbacks:
            self._config_reload_callbacks.append(callback)
            logger.info("已添加配置重载回调函数")
    
    def remove_config_reload_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        移除配置重载回调函数
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._config_reload_callbacks:
            self._config_reload_callbacks.remove(callback)
            logger.info("已移除配置重载回调函数")
    
    def set_config_reload_enabled(self, enabled: bool) -> None:
        """
        启用或禁用配置热重载
        
        Args:
            enabled: 是否启用热重载
        """
        old_enabled = self._config_reload_enabled
        self._config_reload_enabled = enabled
        
        if enabled and not old_enabled:
            self._start_config_monitoring()
        elif not enabled and old_enabled:
            self._stop_config_monitoring()
            
        logger.info(f"配置热重载已{'启用' if enabled else '禁用'}")
    
    def set_config_reload_debounce_time(self, seconds: float) -> None:
        """
        设置配置重载防抖时间
        
        Args:
            seconds: 防抖时间（秒）
        """
        if seconds < 0.1:
            raise ValueError("防抖时间不能小于0.1秒")
            
        self._config_reload_debounce_time = seconds
        logger.info(f"配置重载防抖时间已设置为 {seconds} 秒")
    
    def force_config_reload(self) -> bool:
        """
        强制重新加载配置
        
        Returns:
            bool: 重载是否成功
        """
        try:
            logger.info("执行强制配置重载")
            self._on_config_changed()
            return True
        except Exception as e:
            logger.error(f"强制配置重载失败: {e}")
            return False
    
    def get_config_reload_status(self) -> Dict[str, Any]:
        """
        获取配置重载状态信息
        
        Returns:
            Dict[str, Any]: 重载状态信息
        """
        return {
            'enabled': self._config_reload_enabled,
            'is_monitoring': self.config_manager._is_watching,
            'debounce_time': self._config_reload_debounce_time,
            'callback_count': len(self._config_reload_callbacks),
            'statistics': self._config_reload_statistics.copy(),
            'last_config_hash': self._last_config_hash
        }
    
    def reload_config(self) -> None:
        """重新加载配置文件（增强版）"""
        try:
            logger.info("手动重新加载快捷键配置")
            
            # 如果启用了热重载，使用热重载机制
            if self._config_reload_enabled:
                self._on_config_changed()
            else:
                # 使用传统重载方式
                self.config_manager.load_config()
                
                if self.config_manager.validate_config():
                    self._setup_hotkey_mappings()
                    logger.info("快捷键配置重新加载成功")
                else:
                    logger.error("快捷键配置验证失败")
                    
        except Exception as e:
            logger.error(f"重新加载快捷键配置失败: {e}")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口（增强版）"""
        self.stop_listening()
        self._stop_template_monitoring()
        self._stop_config_monitoring()
    
    # ================= macOS跨平台兼容性处理 =================
    
    def _initialize_macos_compatibility(self) -> None:
        """初始化macOS兼容性检查"""
        try:
            logger.info("初始化macOS兼容性检查...")
            
            # 获取macOS系统版本
            self._macos_compatibility['system_version'] = self._get_macos_version()
            
            # 检查辅助功能权限
            self._check_accessibility_permission()
            
            # 检查系统通知权限
            self._check_notification_permission()
            
            # 分析兼容性问题
            self._analyze_compatibility_issues()
            
            logger.info(f"macOS兼容性检查完成 (系统版本: {self._macos_compatibility['system_version']})")
            
        except Exception as e:
            logger.error(f"macOS兼容性初始化失败: {e}")
            self._macos_compatibility['compatibility_issues'].append(f"初始化失败: {e}")
    
    def _get_macos_version(self) -> Optional[str]:
        """获取macOS系统版本"""
        try:
            result = subprocess.run(['sw_vers', '-productVersion'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.debug(f"检测到macOS版本: {version}")
                return version
        except Exception as e:
            logger.warning(f"获取macOS版本失败: {e}")
        return None
    
    def _check_accessibility_permission(self) -> bool:
        """检查辅助功能权限"""
        try:
            current_time = time.time()
            
            # 检查是否需要重新验证权限
            last_check = self._macos_compatibility.get('last_permission_check', 0)
            check_interval = self._macos_compatibility.get('permission_check_interval', 300)
            
            if (last_check and current_time - last_check < check_interval and 
               self._macos_compatibility['accessibility_granted'] is not None):
                return self._macos_compatibility['accessibility_granted']
            
            # 尝试创建一个简单的监听器来测试权限
            try:
                test_listener = Listener(on_press=lambda key: None, on_release=lambda key: None)
                test_listener.start()
                test_listener.stop()
                
                self._macos_compatibility['accessibility_granted'] = True
                logger.info("✅ 辅助功能权限已授予")
                
            except Exception as e:
                self._macos_compatibility['accessibility_granted'] = False
                error_msg = str(e)
                
                if "Accessibility" in error_msg or "permission" in error_msg.lower():
                    logger.warning("❌ 辅助功能权限未授予")
                    self._show_accessibility_permission_guide()
                else:
                    logger.error(f"权限检查异常: {e}")
            
            self._macos_compatibility['last_permission_check'] = current_time
            return self._macos_compatibility['accessibility_granted']
            
        except Exception as e:
            logger.error(f"辅助功能权限检查失败: {e}")
            return False
    
    def _show_accessibility_permission_guide(self) -> None:
        """显示辅助功能权限设置指南"""
        guide_message = """
🔐 需要授予辅助功能权限

为了监听全局快捷键，需要在macOS系统偏好设置中授予辅助功能权限：

📋 设置步骤：
1. 打开 "系统偏好设置" (System Preferences)
2. 点击 "安全性与隐私" (Security & Privacy)  
3. 选择 "隐私" (Privacy) 标签
4. 在左侧列表中选择 "辅助功能" (Accessibility)
5. 点击锁图标并输入管理员密码
6. 勾选当前应用程序或终端应用
7. 重启本程序

🔗 快速打开设置：
   可以运行命令：open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        """
        
        logger.warning(guide_message)
        self._macos_compatibility['compatibility_issues'].append("需要辅助功能权限")
        
        # 尝试系统通知
        self._send_macos_notification(
            "需要辅助功能权限",
            "请在系统偏好设置中授予辅助功能权限以启用快捷键监听"
        )
    
    def _check_notification_permission(self) -> bool:
        """检查系统通知权限"""
        try:
            # 尝试发送测试通知
            result = self._send_macos_notification(
                "快捷键监听器",
                "通知功能已启用",
                test_mode=True
            )
            
            self._macos_compatibility['notification_enabled'] = result
            self._macos_compatibility['macos_features']['notification_center'] = result
            
            if result:
                logger.info("✅ 系统通知功能可用")
            else:
                logger.info("ℹ️  系统通知功能不可用")
                
            return result
            
        except Exception as e:
            logger.warning(f"通知权限检查失败: {e}")
            return False
    
    def _send_macos_notification(self, title: str, message: str, test_mode: bool = False) -> bool:
        """发送macOS系统通知"""
        try:
            if not self._platform == "Darwin":
                return False
                
            # 构建osascript命令
            script = f'''
            display notification "{message}" with title "{title}"
            '''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            success = result.returncode == 0
            
            if not test_mode:
                if success:
                    logger.debug(f"系统通知已发送: {title}")
                else:
                    logger.warning(f"系统通知发送失败: {result.stderr}")
                    
            return success
            
        except Exception as e:
            if not test_mode:
                logger.error(f"发送系统通知失败: {e}")
            return False
    
    def _analyze_compatibility_issues(self) -> None:
        """分析兼容性问题"""
        issues = []
        
        # 检查系统版本兼容性
        system_version = self._macos_compatibility.get('system_version')
        if system_version:
            try:
                major_version = int(system_version.split('.')[0])
                minor_version = int(system_version.split('.')[1]) if '.' in system_version else 0
                
                # macOS 10.15 (Catalina) 及以上版本有更严格的权限要求
                if major_version >= 11 or (major_version == 10 and minor_version >= 15):
                    logger.info("✅ macOS版本支持现代权限管理")
                    self._macos_compatibility['macos_features']['security_assessment'] = True
                else:
                    issues.append(f"macOS版本较旧 ({system_version})，可能存在兼容性问题")
                    
            except (ValueError, IndexError):
                issues.append(f"无法解析macOS版本: {system_version}")
        
        # 检查权限状态
        if not self._macos_compatibility.get('accessibility_granted', False):
            issues.append("辅助功能权限未授予")
        
        # 检查快捷键冲突
        hotkey_conflicts = self._check_macos_hotkey_conflicts()
        if hotkey_conflicts:
            issues.extend([f"快捷键冲突: {conflict}" for conflict in hotkey_conflicts])
        
        self._macos_compatibility['compatibility_issues'] = issues
        
        if issues:
            logger.warning(f"发现 {len(issues)} 个兼容性问题")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("✅ 未发现兼容性问题")
    
    def _check_macos_hotkey_conflicts(self) -> List[str]:
        """检查macOS特有的快捷键冲突"""
        conflicts = []
        current_mappings = self.config_manager.get_all_mappings()
        
        for hotkey in current_mappings.keys():
            normalized = self._normalize_hotkey_string(hotkey)
            
            # 检查与macOS系统快捷键的冲突
            if normalized in self.MACOS_SYSTEM_SHORTCUTS:
                system_function = self.MACOS_SYSTEM_SHORTCUTS[normalized]
                conflicts.append(f"{hotkey} 与系统功能冲突: {system_function}")
                
            # 检查特殊的macOS快捷键模式
            if self._is_macos_reserved_pattern(normalized):
                conflicts.append(f"{hotkey} 使用了macOS保留的快捷键模式")
                
        return conflicts
    
    def _is_macos_reserved_pattern(self, normalized_hotkey: str) -> bool:
        """检查是否为macOS保留的快捷键模式"""
        # macOS保留的快捷键模式
        reserved_patterns = [
            'cmd+shift+3',  'cmd+shift+4',  'cmd+shift+5',  # 截图
            'cmd+ctrl+q',   'cmd+opt+esc',  'cmd+shift+q',  # 系统操作
            'ctrl+f1',      'ctrl+f2',      'ctrl+f3',      # 功能键
            'fn+',          'globe+',                       # 特殊键
        ]
        
        for pattern in reserved_patterns:
            if pattern in normalized_hotkey:
                return True
                
        return False
    
    def _open_accessibility_settings(self) -> bool:
        """打开macOS辅助功能设置"""
        try:
            if self._platform != "Darwin":
                return False
                
            # 打开辅助功能设置页面
            subprocess.run([
                'open', 
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            ], timeout=5)
            
            logger.info("已打开辅助功能设置页面")
            return True
            
        except Exception as e:
            logger.error(f"打开辅助功能设置失败: {e}")
            return False
    
    def _get_macos_app_info(self) -> Dict[str, Any]:
        """获取当前应用在macOS中的信息"""
        try:
            app_info = {
                'bundle_id': None,
                'app_name': None,
                'executable_path': sys.executable,
                'process_name': Path(sys.executable).name,
                'is_python_script': True
            }
            
            # 尝试获取bundle信息（如果是打包的应用）
            try:
                result = subprocess.run(
                    ['mdls', '-name', 'kMDItemCFBundleIdentifier', sys.executable],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and 'null' not in result.stdout:
                    app_info['bundle_id'] = result.stdout.split('=')[1].strip().strip('"')
            except:
                pass
                
            return app_info
            
        except Exception as e:
            logger.error(f"获取应用信息失败: {e}")
            return {}
    
    def get_macos_compatibility_status(self) -> Dict[str, Any]:
        """获取macOS兼容性状态"""
        if self._platform != "Darwin":
            return {'platform': 'non-macos', 'compatible': False}
            
        # 刷新权限检查
        self._check_accessibility_permission()
        
        status = {
            'platform': 'macOS',
            'system_version': self._macos_compatibility.get('system_version'),
            'compatible': len(self._macos_compatibility.get('compatibility_issues', [])) == 0,
            'accessibility_granted': self._macos_compatibility.get('accessibility_granted'),
            'notification_enabled': self._macos_compatibility.get('notification_enabled'),
            'compatibility_issues': self._macos_compatibility.get('compatibility_issues', []),
            'macos_features': self._macos_compatibility.get('macos_features', {}),
            'last_permission_check': self._macos_compatibility.get('last_permission_check'),
            'app_info': self._get_macos_app_info()
        }
        
        return status
    
    def setup_macos_permissions(self) -> Dict[str, Any]:
        """设置macOS权限的辅助方法"""
        result = {
            'accessibility_opened': False,
            'notification_sent': False,
            'issues_found': [],
            'recommendations': []
        }
        
        try:
            # 检查当前权限状态
            accessibility_granted = self._check_accessibility_permission()
            
            if not accessibility_granted:
                # 尝试打开辅助功能设置
                result['accessibility_opened'] = self._open_accessibility_settings()
                
                # 发送通知提醒
                notification_sent = self._send_macos_notification(
                    "需要设置权限",
                    "请在打开的设置页面中授予辅助功能权限"
                )
                result['notification_sent'] = notification_sent
                
                result['issues_found'].append("辅助功能权限未授予")
                result['recommendations'].append("在系统偏好设置中授予辅助功能权限")
            
            # 检查其他兼容性问题
            self._analyze_compatibility_issues()
            issues = self._macos_compatibility.get('compatibility_issues', [])
            result['issues_found'].extend(issues)
            
            # 生成建议
            if not self._macos_compatibility.get('notification_enabled'):
                result['recommendations'].append("考虑启用系统通知以获得更好的用户体验")
                
            if self._macos_compatibility.get('system_version'):
                version = self._macos_compatibility['system_version']
                try:
                    major = int(version.split('.')[0])
                    if major < 11:
                        result['recommendations'].append("建议升级到macOS Big Sur (11.0) 或更高版本")
                except:
                    pass
            
            return result
            
        except Exception as e:
            logger.error(f"设置macOS权限失败: {e}")
            result['issues_found'].append(f"权限设置过程出错: {e}")
            return result
    
    def get_platform_info(self) -> Dict[str, Any]:
        """获取平台信息（增强版）"""
        base_info = {
            'platform': self._platform,
            'is_macos': self._platform == "Darwin",
            'supported_hotkeys': list(self.get_supported_hotkeys()),
            'accessibility_required': self._platform == "Darwin"
        }
        
        # 如果是macOS，添加详细的兼容性信息
        if self._platform == "Darwin":
            macos_status = self.get_macos_compatibility_status()
            base_info.update({
                'macos_compatibility': macos_status,
                'system_version': macos_status.get('system_version'),
                'accessibility_granted': macos_status.get('accessibility_granted'),
                'compatibility_issues': macos_status.get('compatibility_issues', []),
                'macos_features_available': macos_status.get('macos_features', {})
            })
        
        return base_info
    
    def start_listening(self) -> bool:
        """开始监听全局快捷键（增强版 - 包含macOS兼容性检查）"""
        if self.is_listening:
            logger.warning("快捷键监听器已经在运行")
            return False
            
        # macOS特殊处理
        if self._platform == "Darwin":
            # 检查辅助功能权限
            if not self._check_accessibility_permission():
                logger.error("❌ 辅助功能权限未授予，无法启动快捷键监听")
                self._show_accessibility_permission_guide()
                return False
            
            # 发送启动通知
            self._send_macos_notification(
                "快捷键监听器",
                "快捷键监听已启动"
            )
            
        try:
            self.listener = Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False  # 不抑制其他程序接收按键事件
            )
            
            self.listener.start()
            self.is_listening = True
            
            # 更新统计信息
            self._listening_statistics['start_time'] = datetime.datetime.now().isoformat()
            self._listening_statistics['total_hotkeys_processed'] = 0
            
            # 启动健康检查
            self._start_health_check()
            
            # 保存状态
            self._save_listening_state()
            
            logger.info(f"全局快捷键监听器启动成功 (平台: {self._platform})")
            return True
            
        except Exception as e:
            logger.error(f"启动快捷键监听器失败: {e}")
            
            # macOS特殊错误处理
            if self._platform == "Darwin":
                if "Accessibility" in str(e) or "permission" in str(e).lower():
                    logger.error("❌ macOS辅助功能权限问题")
                    self._show_accessibility_permission_guide()
                else:
                    # 发送错误通知
                    self._send_macos_notification(
                        "启动失败",
                        f"快捷键监听器启动失败: {str(e)[:50]}"
                    )
            
            self._listening_statistics['error_count'] += 1
            self._listening_statistics['last_error'] = str(e)
            return False
    
    def stop_listening(self) -> bool:
        """停止监听全局快捷键（增强版 - 包含macOS通知）"""
        if not self.is_listening:
            logger.warning("快捷键监听器未运行")
            return False
            
        try:
            self._graceful_shutdown = True
            
            # 停止健康检查
            self._stop_health_check()
            
            if self.listener:
                self.listener.stop()
                self.listener = None
                
            self.is_listening = False
            self._pressed_keys.clear()
            
            # 更新统计信息
            self._update_uptime_statistics()
            
            # 保存状态
            self._save_listening_state()
            
            # macOS通知
            if self._platform == "Darwin" and self._macos_compatibility.get('notification_enabled'):
                self._send_macos_notification(
                    "快捷键监听器",
                    "快捷键监听已停止"
                )
            
            self._graceful_shutdown = False
            logger.info("全局快捷键监听器已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止快捷键监听器失败: {e}")
            self._graceful_shutdown = False
            return False