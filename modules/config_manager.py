"""
配置文件管理模块

负责处理全局配置和快捷键映射的读取、写入、验证和动态重新加载功能。
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化监听器"""
    
    def __init__(self, config_manager, config_path: Path):
        self.config_manager = config_manager
        self.config_path = config_path
        
    def on_modified(self, event):
        """当配置文件被修改时触发重新加载"""
        if not event.is_directory and Path(event.src_path) == self.config_path:
            logger.info(f"检测到配置文件变化: {event.src_path}")
            self.config_manager.reload_config()


class ConfigManager:
    """配置文件管理器"""
    
    def __init__(self, config_path: Union[str, Path]):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self._observer: Optional[Observer] = None
        self._is_watching = False
        
        # 确保配置文件目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置数据字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML格式错误
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"配置文件不存在: {self.config_path}")
                return {}
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f) or {}
                
            logger.info(f"成功加载配置文件: {self.config_path}")
            return self.config_data
            
        except yaml.YAMLError as e:
            logger.error(f"YAML格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
            
    def save_config(self, config_data: Optional[Dict[str, Any]] = None) -> None:
        """
        保存配置到文件
        
        Args:
            config_data: 要保存的配置数据，如果为None则保存当前的config_data
        """
        try:
            data_to_save = config_data if config_data is not None else self.config_data
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data_to_save, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
                         
            logger.info(f"成功保存配置文件: {self.config_path}")
            
            # 更新内存中的配置数据
            if config_data is not None:
                self.config_data = config_data
                
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置项键名，支持点号分隔的嵌套键（如 'api.deepseek.key'）
            default: 默认值
            
        Returns:
            配置项值
        """
        keys = key.split('.')
        current = self.config_data
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
            
    def set(self, key: str, value: Any) -> None:
        """
        设置配置项
        
        Args:
            key: 配置项键名，支持点号分隔的嵌套键
            value: 配置项值
        """
        keys = key.split('.')
        current = self.config_data
        
        # 创建嵌套字典结构
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
            
        current[keys[-1]] = value
        
    def validate_config(self) -> bool:
        """
        验证配置文件格式和必需字段
        
        Returns:
            验证是否通过
        """
        return True  # 基类的默认验证，子类可以重写
        
    def reload_config(self) -> None:
        """重新加载配置文件"""
        try:
            self.load_config()
            if self.validate_config():
                logger.info("配置文件重新加载成功")
            else:
                logger.error("配置文件验证失败")
        except Exception as e:
            logger.error(f"重新加载配置文件失败: {e}")
            
    def start_watching(self) -> None:
        """开始监控配置文件变化"""
        if self._is_watching:
            return
            
        try:
            self._observer = Observer()
            event_handler = ConfigFileHandler(self, self.config_path)
            self._observer.schedule(event_handler, str(self.config_path.parent), recursive=False)
            self._observer.start()
            self._is_watching = True
            logger.info(f"开始监控配置文件变化: {self.config_path}")
        except Exception as e:
            logger.error(f"启动配置文件监控失败: {e}")
            
    def stop_watching(self) -> None:
        """停止监控配置文件变化"""
        if self._observer and self._is_watching:
            self._observer.stop()
            self._observer.join()
            self._is_watching = False
            logger.info("停止监控配置文件变化")


class GlobalConfigManager(ConfigManager):
    """全局配置管理器"""
    
    def __init__(self, config_dir: Union[str, Path] = "config"):
        """
        初始化全局配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        config_path = Path(config_dir) / "global_config.yaml"
        super().__init__(config_path)
        
        # 如果配置文件不存在，创建默认配置
        if not self.config_path.exists():
            self._create_default_config()
            
    def _create_default_config(self) -> None:
        """创建默认全局配置文件"""
        default_config = {
            'api': {
                'deepseek': {
                    'key': '',
                    'base_url': 'https://api.deepseek.com',
                    'model': 'deepseek-chat'
                },
                'kimi': {
                    'key': '',
                    'base_url': 'https://api.moonshot.cn',
                    'model': 'moonshot-v1-8k'
                }
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'performance': {
                'response_timeout': 30,
                'max_retries': 3,
                'retry_delay': 1
            }
        }
        
        self.save_config(default_config)
        logger.info("创建默认全局配置文件")
        
    def validate_config(self) -> bool:
        """验证全局配置文件格式"""
        required_keys = ['api', 'api.deepseek', 'api.kimi']
        
        for key in required_keys:
            if self.get(key) is None:
                logger.error(f"缺少必需的配置项: {key}")
                return False
                
        return True
        
    def get_api_key(self, provider: str) -> Optional[str]:
        """获取API密钥"""
        return self.get(f'api.{provider}.key')
        
    def set_api_key(self, provider: str, key: str) -> None:
        """设置API密钥"""
        self.set(f'api.{provider}.key', key)
        self.save_config()


class HotkeyConfigManager(ConfigManager):
    """快捷键配置管理器"""
    
    def __init__(self, config_dir: Union[str, Path] = "config"):
        """
        初始化快捷键配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        config_path = Path(config_dir) / "hotkey_mapping.yaml"
        super().__init__(config_path)
        
        # 如果配置文件不存在，创建默认配置
        if not self.config_path.exists():
            self._create_default_config()
            
    def _create_default_config(self) -> None:
        """创建默认快捷键配置文件"""
        default_config = {
            'hotkeys': {
                'ctrl+alt+cmd+1': 'template1.md',
                'ctrl+alt+cmd+2': 'template2.md',
                'ctrl+alt+cmd+3': 'template3.md',
                'ctrl+alt+cmd+4': 'template4.md',
                'ctrl+alt+cmd+5': 'template5.md',
                'ctrl+alt+cmd+6': 'template6.md',
                'ctrl+alt+cmd+7': 'template7.md',
                'ctrl+alt+cmd+8': 'template8.md',
                'ctrl+alt+cmd+9': 'template9.md'
            },
            'settings': {
                'enabled': True,
                'response_delay': 100  # 毫秒
            }
        }
        
        self.save_config(default_config)
        logger.info("创建默认快捷键配置文件")
        
    def validate_config(self) -> bool:
        """验证快捷键配置文件格式"""
        hotkeys = self.get('hotkeys', {})
        
        if not isinstance(hotkeys, dict):
            logger.error("hotkeys必须是字典格式")
            return False
            
        # 验证快捷键格式
        for hotkey, template in hotkeys.items():
            if not isinstance(hotkey, str) or not isinstance(template, str):
                logger.error(f"快捷键配置格式错误: {hotkey} -> {template}")
                return False
                
        return True
        
    def get_template_for_hotkey(self, hotkey: str) -> Optional[str]:
        """根据快捷键获取对应的模板文件名"""
        return self.get(f'hotkeys.{hotkey}')
        
    def set_hotkey_mapping(self, hotkey: str, template: str) -> None:
        """设置快捷键映射"""
        self.set(f'hotkeys.{hotkey}', template)
        self.save_config()
        
    def get_all_mappings(self) -> Dict[str, str]:
        """获取所有快捷键映射"""
        return self.get('hotkeys', {}) 