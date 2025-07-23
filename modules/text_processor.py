"""
文本处理模块

负责获取当前选中的文本内容，处理文本插入和流式输出功能。
支持跨平台的剪贴板操作和文本处理。
"""

import logging
import platform
import time
import threading
import subprocess
import sys
from typing import Optional, Dict, Any, Callable, List, Union
from pathlib import Path
import pyperclip
from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from .template_parser import AdvancedTemplateParser, TemplateContent, TemplateParsingError
from .model_client import (
    ModelClientFactory, ModelType, ModelRequest, StreamChunk, StreamBuffer,
    StreamProcessor, StreamingManager, ModelClientError
)
from .config_manager import GlobalConfigManager

logger = logging.getLogger(__name__)


class TextProcessor:
    """文本处理器"""
    
    def __init__(self, template_dir: Union[str, Path] = "prompt", config_dir: Union[str, Path] = "config"):
        """
        初始化文本处理器
        
        Args:
            template_dir: 模板目录路径
            config_dir: 配置目录路径
        """
        self._platform = platform.system()
        self._last_clipboard_content = ""
        self._selection_timeout = 2.0  # 选中文本获取超时时间（秒）
        self._copy_retry_count = 3     # 复制操作重试次数
        self._copy_retry_delay = 0.1   # 复制重试间隔（秒）
        
        # 模板处理器
        self.template_parser = AdvancedTemplateParser(template_dir)
        self.template_dir = Path(template_dir)
        
        # 配置管理器
        self.config_manager = GlobalConfigManager(config_dir)
        self.config_dir = Path(config_dir)
        
        # AI模型客户端
        self._model_clients = {}  # 缓存客户端实例
        
        # 流式处理组件
        self.stream_processor = StreamProcessor()
        self.streaming_manager = StreamingManager()
        
        # 输出配置
        self._typing_speed = 0.02  # 打字速度（秒/字符）
        self._chunk_output_delay = 0.05  # 块输出延迟（秒）
        self._max_output_length = 10000  # 最大输出长度限制
        
        # 平台特定配置
        self._platform_config = {
            'Darwin': {  # macOS
                'copy_shortcut': [Key.cmd, 'c'],
                'paste_shortcut': [Key.cmd, 'v'],
                'accessibility_required': True
            },
            'Windows': {
                'copy_shortcut': [Key.ctrl, 'c'],
                'paste_shortcut': [Key.ctrl, 'v'],
                'accessibility_required': False
            },
            'Linux': {
                'copy_shortcut': [Key.ctrl, 'c'],
                'paste_shortcut': [Key.ctrl, 'v'],
                'accessibility_required': False
            }
        }
        
        logger.info(f"文本处理器初始化完成 (平台: {self._platform})")
    
    def get_selected_text(self) -> Optional[str]:
        """
        获取当前选中的文本内容
        
        Returns:
            Optional[str]: 选中的文本内容，如果获取失败返回None
        """
        try:
            # 保存当前剪贴板内容
            original_clipboard = self._get_clipboard_content()
            
            # 清空剪贴板以确保获取到的是新内容
            pyperclip.copy("")
            time.sleep(0.05)  # 短暂等待确保剪贴板被清空
            
            # 执行复制操作
            success = self._execute_copy_operation()
            
            if not success:
                logger.warning("复制操作失败")
                self._restore_clipboard(original_clipboard)
                return None
            
            # 获取复制的内容
            selected_text = self._get_clipboard_content()
            
            # 恢复原始剪贴板内容
            self._restore_clipboard(original_clipboard)
            
            if not selected_text or selected_text.strip() == "":
                logger.debug("未检测到选中文本")
                return None
                
            logger.debug(f"成功获取选中文本: {len(selected_text)} 字符")
            return selected_text.strip()
            
        except Exception as e:
            logger.error(f"获取选中文本失败: {e}")
            return None
    
    def _get_clipboard_content(self) -> str:
        """
        获取剪贴板内容
        
        Returns:
            str: 剪贴板内容
        """
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.error(f"获取剪贴板内容失败: {e}")
            return ""
    
    def _restore_clipboard(self, content: str) -> None:
        """
        恢复剪贴板内容
        
        Args:
            content: 要恢复的内容
        """
        try:
            if content:
                pyperclip.copy(content)
        except Exception as e:
            logger.error(f"恢复剪贴板内容失败: {e}")
    
    def _execute_copy_operation(self) -> bool:
        """
        执行复制操作
        
        Returns:
            bool: 是否成功执行复制操作
        """
        try:
            platform_config = self._platform_config.get(self._platform, self._platform_config['Linux'])
            
            # 获取复制快捷键
            copy_keys = platform_config['copy_shortcut']
            
            # 多次尝试复制操作
            for attempt in range(self._copy_retry_count):
                try:
                    # 模拟按键操作
                    success = self._simulate_copy_keys(copy_keys)
                    
                    if success:
                        # 等待剪贴板更新
                        time.sleep(self._copy_retry_delay * 2)
                        return True
                        
                except Exception as e:
                    logger.debug(f"复制操作尝试 {attempt + 1} 失败: {e}")
                
                if attempt < self._copy_retry_count - 1:
                    time.sleep(self._copy_retry_delay)
            
            return False
            
        except Exception as e:
            logger.error(f"执行复制操作失败: {e}")
            return False
    
    def _simulate_copy_keys(self, keys: List) -> bool:
        """
        模拟按键操作
        
        Args:
            keys: 按键列表
            
        Returns:
            bool: 是否成功执行按键操作
        """
        try:
            from pynput.keyboard import Controller
            
            keyboard_controller = Controller()
            
            # 按下修饰键
            modifier_keys = [key for key in keys[:-1] if isinstance(key, Key)]
            for key in modifier_keys:
                keyboard_controller.press(key)
            
            # 按下主键
            main_key = keys[-1]
            if isinstance(main_key, str):
                keyboard_controller.press(main_key)
                keyboard_controller.release(main_key)
            else:
                keyboard_controller.press(main_key)
                keyboard_controller.release(main_key)
            
            # 释放修饰键
            for key in reversed(modifier_keys):
                keyboard_controller.release(key)
            
            return True
            
        except Exception as e:
            logger.error(f"模拟按键操作失败: {e}")
            return False
    
    def validate_text_selection(self, text: Optional[str]) -> Dict[str, Any]:
        """
        验证选中文本的有效性
        
        Args:
            text: 要验证的文本
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            'is_valid': False,
            'text': text,
            'length': 0,
            'is_empty': True,
            'error_message': None
        }
        
        try:
            if text is None:
                result['error_message'] = "文本为空"
                return result
            
            text = text.strip()
            result['text'] = text
            result['length'] = len(text)
            result['is_empty'] = len(text) == 0
            
            if result['is_empty']:
                result['error_message'] = "选中文本为空"
                return result
            
            # 检查文本长度限制
            if len(text) > 50000:  # 50KB限制
                result['error_message'] = "选中文本过长"
                return result
            
            # 检查是否包含可读字符
            if not any(c.isprintable() and not c.isspace() for c in text):
                result['error_message'] = "选中文本不包含可读内容"
                return result
            
            result['is_valid'] = True
            return result
            
        except Exception as e:
            result['error_message'] = f"文本验证失败: {e}"
            return result
    
    def get_platform_capabilities(self) -> Dict[str, Any]:
        """
        获取当前平台的文本处理能力
        
        Returns:
            Dict[str, Any]: 平台能力信息
        """
        capabilities = {
            'platform': self._platform,
            'clipboard_available': False,
            'copy_simulation_available': False,
            'accessibility_required': False,
            'supported_shortcuts': {}
        }
        
        try:
            # 测试剪贴板可用性
            test_content = "test_clipboard_availability"
            pyperclip.copy(test_content)
            if pyperclip.paste() == test_content:
                capabilities['clipboard_available'] = True
            
            # 获取平台配置
            platform_config = self._platform_config.get(self._platform, {})
            capabilities.update(platform_config)
            
            # 测试按键模拟可用性
            try:
                from pynput.keyboard import Controller
                Controller()
                capabilities['copy_simulation_available'] = True
            except Exception:
                capabilities['copy_simulation_available'] = False
            
        except Exception as e:
            logger.error(f"检测平台能力失败: {e}")
        
        return capabilities
    
    def check_accessibility_permission(self) -> bool:
        """
        检查辅助功能权限（主要针对macOS）
        
        Returns:
            bool: 是否具有必要的权限
        """
        if self._platform != "Darwin":
            return True  # 非macOS平台默认返回True
        
        try:
            # 尝试创建键盘控制器来测试权限
            from pynput.keyboard import Controller
            controller = Controller()
            
            # 尝试一个无害的按键操作
            controller.press(Key.shift)
            controller.release(Key.shift)
            
            return True
            
        except Exception as e:
            logger.warning(f"辅助功能权限检查失败: {e}")
            return False
    
    def get_text_statistics(self, text: str) -> Dict[str, Any]:
        """
        获取文本统计信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict[str, Any]: 文本统计信息
        """
        try:
            stats = {
                'length': len(text),
                'word_count': len(text.split()),
                'line_count': text.count('\n') + 1,
                'char_count_no_spaces': len(text.replace(' ', '')),
                'has_chinese': any('\u4e00' <= char <= '\u9fff' for char in text),
                'has_english': any(char.isalpha() and ord(char) < 128 for char in text),
                'has_numbers': any(char.isdigit() for char in text),
                'encoding': 'utf-8' if text.encode('utf-8') else 'unknown'
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"文本统计分析失败: {e}")
            return {'error': str(e)}
    
    # ================= 模板处理功能 =================
    
    def process_template_with_selected_text(self, template_name: str) -> Dict[str, Any]:
        """
        处理模板：获取选中文本并插入到模板占位符中
        
        Args:
            template_name: 模板名称
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        result = {
            'success': False,
            'template_name': template_name,
            'selected_text': None,
            'processed_content': None,
            'template_content': None,
            'error': None,
            'validation': {}
        }
        
        try:
            # 1. 获取选中文本
            selected_text = self.get_selected_text()
            result['selected_text'] = selected_text
            
            # 2. 验证选中文本
            text_validation = self.validate_text_selection(selected_text)
            result['validation']['text'] = text_validation
            
            if not text_validation['is_valid']:
                result['error'] = f"选中文本无效: {text_validation['error_message']}"
                return result
            
            # 3. 插入文本到模板
            template_result = self.insert_text_into_template(template_name, selected_text)
            result.update(template_result)
            
            if template_result['success']:
                result['success'] = True
                logger.info(f"成功处理模板 {template_name}，文本长度: {len(selected_text)}")
            else:
                result['error'] = template_result.get('error', '模板处理失败')
                
        except Exception as e:
            result['error'] = f"处理过程中发生异常: {e}"
            logger.error(f"模板处理异常: {e}")
            
        return result
    
    def insert_text_into_template(self, template_name: str, text: str) -> Dict[str, Any]:
        """
        将文本插入指定模板的占位符中
        
        Args:
            template_name: 模板名称
            text: 要插入的文本
            
        Returns:
            Dict[str, Any]: 插入结果
        """
        result = {
            'success': False,
            'template_name': template_name,
            'input_text': text,
            'processed_content': None,
            'template_content': None,
            'error': None,
            'validation': {}
        }
        
        try:
            # 1. 验证模板存在性
            if not self._template_exists(template_name):
                result['error'] = f"模板文件不存在: {template_name}"
                return result
            
            # 2. 解析模板
            try:
                template_content = self.template_parser.parse_template(template_name)
                result['template_content'] = {
                    'model_name': template_content.get_model_name(),
                    'model_config': template_content.model_config,
                    'placeholders': template_content.find_placeholders(),
                    'placeholder_count': template_content.get_placeholder_count()
                }
            except TemplateParsingError as e:
                result['error'] = f"模板解析失败: {e}"
                return result
            
            # 3. 验证模板占位符
            template_validation = self._validate_template_for_processing(template_content)
            result['validation']['template'] = template_validation
            
            if not template_validation['is_valid']:
                result['error'] = f"模板验证失败: {template_validation['error']}"
                return result
            
            # 4. 执行文本替换
            try:
                processed_content = template_content.replace_primary_placeholder(text)
                result['processed_content'] = processed_content
                result['success'] = True
                
                logger.debug(f"成功将文本插入模板 {template_name}")
                
            except ValueError as e:
                result['error'] = f"占位符替换失败: {e}"
                return result
                
        except Exception as e:
            result['error'] = f"插入过程中发生异常: {e}"
            logger.error(f"文本插入异常: {e}")
            
        return result
    
    def get_template_with_text(self, template_name: str, text: str) -> Optional[str]:
        """
        获取插入文本后的完整模板内容（简化接口）
        
        Args:
            template_name: 模板名称
            text: 要插入的文本
            
        Returns:
            Optional[str]: 处理后的模板内容，失败时返回None
        """
        try:
            result = self.insert_text_into_template(template_name, text)
            return result['processed_content'] if result['success'] else None
        except Exception as e:
            logger.error(f"获取模板内容失败: {e}")
            return None
    
    def validate_template_processing(self, template_name: str) -> Dict[str, Any]:
        """
        验证模板是否可以进行文本处理
        
        Args:
            template_name: 模板名称
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            'is_valid': False,
            'template_name': template_name,
            'errors': [],
            'warnings': [],
            'details': {}
        }
        
        try:
            # 1. 检查模板文件存在性
            if not self._template_exists(template_name):
                result['errors'].append(f"模板文件不存在: {template_name}")
                return result
            
            # 2. 解析模板
            try:
                template_content = self.template_parser.parse_template(template_name)
            except TemplateParsingError as e:
                result['errors'].append(f"模板解析失败: {e}")
                return result
            
            # 3. 详细验证
            template_validation = self._validate_template_for_processing(template_content)
            result['details'] = template_validation
            
            if not template_validation['is_valid']:
                result['errors'].append(template_validation['error'])
            else:
                result['is_valid'] = True
                
            # 4. 添加模板信息
            result['details'].update({
                'model_name': template_content.get_model_name(),
                'model_config': template_content.model_config,
                'placeholders': template_content.find_placeholders(),
                'prompt_length': len(template_content.prompt_content)
            })
            
        except Exception as e:
            result['errors'].append(f"验证过程中发生异常: {e}")
            
        return result
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """
        获取可用的模板列表
        
        Returns:
            List[Dict[str, Any]]: 模板信息列表
        """
        try:
            template_names = self.template_parser.get_available_templates()
            template_list = []
            
            for template_name in template_names:
                try:
                    validation = self.validate_template_processing(template_name)
                    template_info = {
                        'name': template_name,
                        'is_valid': validation['is_valid'],
                        'errors': validation['errors'],
                        'warnings': validation['warnings']
                    }
                    
                    if validation['is_valid']:
                        template_info.update(validation['details'])
                    
                    template_list.append(template_info)
                    
                except Exception as e:
                    template_list.append({
                        'name': template_name,
                        'is_valid': False,
                        'errors': [f"模板信息获取失败: {e}"]
                    })
            
            return template_list
            
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return []
    
    def _template_exists(self, template_name: str) -> bool:
        """
        检查模板文件是否存在
        
        Args:
            template_name: 模板名称
            
        Returns:
            bool: 是否存在
        """
        try:
            template_path = self.template_parser.scanner.find_template_by_name(template_name)
            return template_path is not None and template_path.exists()
        except Exception:
            return False
    
    def _validate_template_for_processing(self, template_content: TemplateContent) -> Dict[str, Any]:
        """
        验证模板是否适合进行文本处理
        
        Args:
            template_content: 模板内容对象
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            'is_valid': False,
            'error': None,
            'placeholder_count': 0,
            'placeholders': [],
            'has_single_placeholder': False
        }
        
        try:
            placeholders = template_content.find_placeholders()
            placeholder_count = len(placeholders)
            
            result['placeholder_count'] = placeholder_count
            result['placeholders'] = placeholders
            result['has_single_placeholder'] = placeholder_count == 1
            
            # 检查是否只有一个占位符（根据PRD要求）
            if placeholder_count == 0:
                result['error'] = "模板缺少必需的占位符"
            elif placeholder_count > 1:
                result['error'] = f"模板包含多个占位符（{placeholder_count}个），但要求只能有一个"
            else:
                # 正好一个占位符，验证通过
                result['is_valid'] = True
                result['primary_placeholder'] = placeholders[0]
                
        except Exception as e:
            result['error'] = f"模板验证过程中发生异常: {e}"
            
        return result
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        获取文本处理统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            available_templates = self.get_available_templates()
            valid_templates = [t for t in available_templates if t['is_valid']]
            invalid_templates = [t for t in available_templates if not t['is_valid']]
            
            platform_capabilities = self.get_platform_capabilities()
            
            return {
                'platform': self._platform,
                'template_directory': str(self.template_dir),
                'total_templates': len(available_templates),
                'valid_templates': len(valid_templates),
                'invalid_templates': len(invalid_templates),
                'platform_capabilities': platform_capabilities,
                'template_parser_info': {
                    'type': type(self.template_parser).__name__,
                    'directory': str(self.template_parser.template_directory)
                },
                'valid_template_names': [t['name'] for t in valid_templates],
                'invalid_template_names': [t['name'] for t in invalid_templates]
            }
            
        except Exception as e:
            logger.error(f"获取处理统计信息失败: {e}")
            return {'error': str(e)}
    
    # ================= 流式输出功能 =================
    
    def get_model_client(self, model_name: str) -> Optional[Any]:
        """
        获取模型客户端实例
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[Any]: 模型客户端实例，失败时返回None
        """
        try:
            # 检查缓存
            if model_name in self._model_clients:
                return self._model_clients[model_name]
            
            # 确定模型类型
            model_type = self._determine_model_type(model_name)
            if not model_type:
                logger.error(f"不支持的模型: {model_name}")
                return None
            
            # 获取API密钥
            api_key = self._get_api_key_for_model(model_type)
            if not api_key:
                logger.error(f"未配置 {model_type.value} 的API密钥")
                return None
            
            # 创建客户端
            client = ModelClientFactory.create_client(model_type, api_key)
            if client:
                self._model_clients[model_name] = client
                logger.debug(f"创建模型客户端: {model_name} ({model_type.value})")
            
            return client
            
        except Exception as e:
            logger.error(f"获取模型客户端失败: {e}")
            return None
    
    def _determine_model_type(self, model_name: str) -> Optional[ModelType]:
        """
        根据模型名称确定模型类型
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[ModelType]: 模型类型
        """
        model_name_lower = model_name.lower()
        
        if 'deepseek' in model_name_lower:
            return ModelType.DEEPSEEK
        elif 'kimi' in model_name_lower or 'moonshot' in model_name_lower:
            return ModelType.KIMI
        else:
            # 默认尝试deepseek
            logger.warning(f"未知模型类型: {model_name}，默认使用 Deepseek")
            return ModelType.DEEPSEEK
    
    def _get_api_key_for_model(self, model_type: ModelType) -> Optional[str]:
        """
        获取指定模型类型的API密钥
        
        Args:
            model_type: 模型类型
            
        Returns:
            Optional[str]: API密钥
        """
        try:
            self.config_manager.load_config()
            
            if model_type == ModelType.DEEPSEEK:
                return self.config_manager.get('deepseek.api_key')
            elif model_type == ModelType.KIMI:
                return self.config_manager.get('kimi.api_key')
            else:
                logger.error(f"不支持的模型类型: {model_type}")
                return None
                
        except Exception as e:
            logger.error(f"获取API密钥失败: {e}")
            return None
    
    def process_with_ai_streaming(self, template_name: str, 
                                 output_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        处理模板并使用AI进行流式响应
        
        Args:
            template_name: 模板名称
            output_callback: 输出回调函数，接收每个字符作为参数
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        result = {
            'success': False,
            'template_name': template_name,
            'selected_text': None,
            'processed_content': None,
            'ai_response': None,
            'total_tokens': None,
            'response_time': None,
            'error': None
        }
        
        start_time = time.time()
        
        try:
            # 1. 获取选中文本并插入模板
            template_result = self.process_template_with_selected_text(template_name)
            result['selected_text'] = template_result.get('selected_text')
            result['processed_content'] = template_result.get('processed_content')
            
            if not template_result['success']:
                result['error'] = template_result.get('error', '模板处理失败')
                return result
            
            # 2. 获取模板配置
            template_content = template_result.get('template_content', {})
            model_name = template_content.get('model_name')
            model_config = template_content.get('model_config', {})
            
            if not model_name:
                result['error'] = "模板中未配置模型名称"
                return result
            
            # 3. 获取模型客户端
            client = self.get_model_client(model_name)
            if not client:
                result['error'] = f"无法创建模型客户端: {model_name}"
                return result
            
            # 4. 创建API请求
            request = ModelRequest(
                message=result['processed_content'],
                model=model_name,
                temperature=model_config.get('temperature', 0.7),
                max_tokens=model_config.get('max_tokens', 2000),
                stream=True
            )
            
            # 5. 执行流式响应并实时输出
            ai_response = self._execute_streaming_request(client, request, output_callback)
            result['ai_response'] = ai_response['content']
            result['total_tokens'] = ai_response.get('total_tokens')
            result['response_time'] = time.time() - start_time
            result['success'] = ai_response['success']
            
            if not ai_response['success']:
                result['error'] = ai_response.get('error', 'AI响应失败')
            
            logger.info(f"AI流式处理完成: {template_name}, 响应时间: {result['response_time']:.2f}s")
            
        except Exception as e:
            result['error'] = f"AI流式处理异常: {e}"
            result['response_time'] = time.time() - start_time
            logger.error(f"AI流式处理异常: {e}")
        
        return result
    
    def _execute_streaming_request(self, client: Any, request: ModelRequest,
                                  output_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        执行流式AI请求
        
        Args:
            client: 模型客户端
            request: 请求对象
            output_callback: 输出回调函数
            
        Returns:
            Dict[str, Any]: 响应结果
        """
        result = {
            'success': False,
            'content': '',
            'total_tokens': None,
            'error': None
        }
        
        try:
            # 创建流式缓冲区
            buffer = StreamBuffer()
            
            # 设置实时输出回调
            def chunk_handler(chunk: StreamChunk):
                try:
                    if chunk.content:
                        # 立即输出到光标位置
                        if output_callback:
                            self._output_text_streaming(chunk.content, output_callback)
                        else:
                            self._output_text_to_cursor(chunk.content)
                            
                except Exception as e:
                    logger.error(f"输出处理失败: {e}")
            
            # 处理流式响应
            result_buffer = self.streaming_manager.process_client_stream(
                client, request, chunk_handler
            )
            
            # 获取完整响应
            if result_buffer.error_occurred:
                result['error'] = "流式响应过程中发生错误"
            else:
                result['success'] = True
                result['content'] = result_buffer.get_content()
                result['total_tokens'] = result_buffer.total_tokens
                
        except ModelClientError as e:
            result['error'] = f"模型API调用失败: {e}"
        except Exception as e:
            result['error'] = f"流式请求执行失败: {e}"
            
        return result
    
    def _output_text_streaming(self, text: str, callback: Callable[[str], None]):
        """
        通过回调函数流式输出文本
        
        Args:
            text: 要输出的文本
            callback: 输出回调函数
        """
        try:
            for char in text:
                callback(char)
                if self._typing_speed > 0:
                    time.sleep(self._typing_speed)
        except Exception as e:
            logger.error(f"回调输出失败: {e}")
    
    def _output_text_to_cursor(self, text: str):
        """
        将文本输出到当前光标位置
        
        Args:
            text: 要输出的文本
        """
        try:
            # 先过滤文本
            filtered_text = self.filter_output_text(text)
            
            from pynput.keyboard import Controller
            controller = Controller()
            
            # 逐字符输出以模拟打字效果
            for char in filtered_text:
                controller.type(char)
                if self._typing_speed > 0:
                    time.sleep(self._typing_speed)
                    
        except Exception as e:
            logger.error(f"光标位置输出失败: {e}")
            # 备用方案：输出到剪贴板
            self._output_to_clipboard_fallback(text)
    
    def _output_to_clipboard_fallback(self, text: str):
        """
        备用输出方案：将文本复制到剪贴板
        
        Args:
            text: 要输出的文本
        """
        try:
            pyperclip.copy(text)
            logger.info("文本已复制到剪贴板（备用输出方案）")
        except Exception as e:
            logger.error(f"剪贴板备用输出也失败: {e}")
    
    def set_typing_speed(self, speed: float):
        """
        设置打字速度
        
        Args:
            speed: 每个字符的延迟时间（秒）
        """
        self._typing_speed = max(0, speed)
        logger.debug(f"设置打字速度: {self._typing_speed}秒/字符")
    
    def process_template_with_ai_complete(self, template_name: str) -> Dict[str, Any]:
        """
        完整的模板处理流程：获取选中文本 -> 插入模板 -> AI处理 -> 流式输出
        
        Args:
            template_name: 模板名称
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"开始完整的AI模板处理流程: {template_name}")
        
        # 检查文本为空的情况
        selected_text = self.get_selected_text()
        if not selected_text:
            error_message = "!!文本为空!!"
            self._output_text_to_cursor(error_message)
            return {
                'success': False,
                'error': '选中文本为空',
                'output_text': error_message
            }
        
        # 执行AI流式处理
        result = self.process_with_ai_streaming(template_name)
        
        # 处理API不可用的情况
        if not result['success'] and 'API' in str(result.get('error', '')):
            error_message = "!!api不可用!!"
            self._output_text_to_cursor(error_message)
            result['output_text'] = error_message
        
        return result
    
    def get_streaming_statistics(self) -> Dict[str, Any]:
        """
        获取流式处理统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            processing_stats = self.get_processing_statistics()
            streaming_stats = self.streaming_manager.stats
            
            # 模型客户端统计
            client_stats = {}
            for model_name, client in self._model_clients.items():
                if hasattr(client, 'get_stats'):
                    client_stats[model_name] = client.get_stats()
            
            return {
                'processing': processing_stats,
                'streaming': streaming_stats,
                'model_clients': client_stats,
                'output_config': {
                    'typing_speed': self._typing_speed,
                    'chunk_output_delay': self._chunk_output_delay,
                    'max_output_length': self._max_output_length
                },
                'platform_capabilities': self.get_platform_capabilities()
            }
            
        except Exception as e:
            logger.error(f"获取流式统计信息失败: {e}")
            return {'error': str(e)}
    
    # ================= 字符编码和过滤功能 =================
    
    def process_text_encoding(self, text: str) -> Dict[str, Any]:
        """
        处理文本编码和特殊字符过滤
        
        Args:
            text: 要处理的文本
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        result = {
            'success': False,
            'original_text': text,
            'processed_text': None,
            'encoding_info': {},
            'filtered_characters': [],
            'warnings': [],
            'error': None
        }
        
        try:
            # 1. 编码检测和验证
            encoding_result = self._detect_and_validate_encoding(text)
            result['encoding_info'] = encoding_result
            
            if not encoding_result['is_valid']:
                result['error'] = f"编码验证失败: {encoding_result['error']}"
                return result
            
            # 2. 特殊字符过滤
            filter_result = self._filter_special_characters(text)
            result['processed_text'] = filter_result['filtered_text']
            result['filtered_characters'] = filter_result['filtered_chars']
            result['warnings'].extend(filter_result['warnings'])
            
            # 3. 文本清理和标准化
            cleaned_text = self._clean_and_normalize_text(result['processed_text'])
            result['processed_text'] = cleaned_text['text']
            result['warnings'].extend(cleaned_text['warnings'])
            
            # 4. 输出长度验证
            if len(result['processed_text']) > self._max_output_length:
                result['processed_text'] = result['processed_text'][:self._max_output_length]
                result['warnings'].append(f"文本被截断到{self._max_output_length}字符")
            
            result['success'] = True
            logger.debug(f"文本编码处理完成，原长度: {len(text)}, 处理后长度: {len(result['processed_text'])}")
            
        except Exception as e:
            result['error'] = f"文本编码处理异常: {e}"
            logger.error(f"文本编码处理异常: {e}")
        
        return result
    
    def _detect_and_validate_encoding(self, text: str) -> Dict[str, Any]:
        """
        检测和验证文本编码
        
        Args:
            text: 要检测的文本
            
        Returns:
            Dict[str, Any]: 编码检测结果
        """
        result = {
            'is_valid': False,
            'encoding': None,
            'encoding_confidence': 0.0,
            'byte_length': 0,
            'char_length': len(text),
            'has_bom': False,
            'error': None
        }
        
        try:
            # 尝试UTF-8编码
            try:
                encoded_bytes = text.encode('utf-8')
                decoded_text = encoded_bytes.decode('utf-8')
                
                if decoded_text == text:
                    result['is_valid'] = True
                    result['encoding'] = 'utf-8'
                    result['encoding_confidence'] = 1.0
                    result['byte_length'] = len(encoded_bytes)
                    
                    # 检查BOM
                    if encoded_bytes.startswith(b'\xef\xbb\xbf'):
                        result['has_bom'] = True
                        
            except UnicodeEncodeError as e:
                result['error'] = f"UTF-8编码失败: {e}"
                return result
            except UnicodeDecodeError as e:
                result['error'] = f"UTF-8解码失败: {e}"
                return result
            
            # 检查是否包含代理对（不完整的Unicode字符）
            if '\ud800' <= text <= '\udfff':
                result['error'] = "文本包含不完整的Unicode代理对"
                result['is_valid'] = False
                return result
            
            # 检查控制字符比例
            control_char_count = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
            if len(text) > 0 and control_char_count / len(text) > 0.1:  # 超过10%的控制字符
                result['error'] = f"文本包含过多控制字符 ({control_char_count}/{len(text)})"
                result['is_valid'] = False
                return result
            
        except Exception as e:
            result['error'] = f"编码检测异常: {e}"
            
        return result
    
    def _filter_special_characters(self, text: str) -> Dict[str, Any]:
        """
        过滤特殊字符
        
        Args:
            text: 要过滤的文本
            
        Returns:
            Dict[str, Any]: 过滤结果
        """
        result = {
            'filtered_text': '',
            'filtered_chars': [],
            'warnings': []
        }
        
        try:
            filtered_chars = []
            output_chars = []
            
            for i, char in enumerate(text):
                char_code = ord(char)
                should_filter = False
                filter_reason = ""
                
                # 1. 过滤危险控制字符
                if char_code < 32:
                    if char not in '\n\r\t':
                        should_filter = True
                        filter_reason = f"控制字符 (U+{char_code:04X})"
                
                # 2. 过滤不可见字符（除了空格）
                elif char_code == 127:  # DEL字符
                    should_filter = True
                    filter_reason = "删除字符 (U+007F)"
                
                # 3. 过滤某些Unicode块中的问题字符
                elif 0x200B <= char_code <= 0x200F:  # 零宽字符
                    should_filter = True
                    filter_reason = f"零宽字符 (U+{char_code:04X})"
                    
                elif 0x2060 <= char_code <= 0x206F:  # 格式字符
                    should_filter = True
                    filter_reason = f"格式字符 (U+{char_code:04X})"
                    
                elif 0xFE00 <= char_code <= 0xFE0F:  # 变体选择器
                    should_filter = True
                    filter_reason = f"变体选择器 (U+{char_code:04X})"
                    
                elif 0xFEFF == char_code:  # 字节顺序标记 (BOM)
                    should_filter = True
                    filter_reason = "字节顺序标记 (U+FEFF)"
                
                # 4. 过滤私用区字符
                elif 0xE000 <= char_code <= 0xF8FF:  # 私用区
                    should_filter = True
                    filter_reason = f"私用区字符 (U+{char_code:04X})"
                
                # 5. 平台特定字符处理
                elif self._platform == "Windows" and char_code in [0x0000, 0x0008, 0x000B, 0x000C]:
                    should_filter = True
                    filter_reason = f"Windows不兼容字符 (U+{char_code:04X})"
                
                if should_filter:
                    filtered_chars.append({
                        'char': char,
                        'position': i,
                        'code': char_code,
                        'reason': filter_reason
                    })
                else:
                    output_chars.append(char)
            
            result['filtered_text'] = ''.join(output_chars)
            result['filtered_chars'] = filtered_chars
            
            if filtered_chars:
                result['warnings'].append(f"过滤了 {len(filtered_chars)} 个特殊字符")
                
        except Exception as e:
            logger.error(f"特殊字符过滤失败: {e}")
            result['filtered_text'] = text  # 失败时返回原文本
            result['warnings'].append(f"字符过滤失败: {e}")
        
        return result
    
    def _clean_and_normalize_text(self, text: str) -> Dict[str, Any]:
        """
        清理和标准化文本
        
        Args:
            text: 要清理的文本
            
        Returns:
            Dict[str, Any]: 清理结果
        """
        result = {
            'text': text,
            'warnings': []
        }
        
        try:
            original_length = len(text)
            
            # 1. 标准化换行符
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            
            # 2. 移除行尾空白
            lines = text.split('\n')
            cleaned_lines = [line.rstrip() for line in lines]
            text = '\n'.join(cleaned_lines)
            
            # 3. 限制连续空行
            import re
            text = re.sub(r'\n{4,}', '\n\n\n', text)  # 最多3个连续换行
            
            # 4. 移除首尾空白
            text = text.strip()
            
            # 5. 标准化空白字符
            text = re.sub(r'[ \t]+', ' ', text)  # 多个空格/制表符替换为单个空格
            
            # 6. 验证最终文本
            if len(text) != original_length:
                result['warnings'].append(f"文本长度从 {original_length} 变为 {len(text)}")
            
            result['text'] = text
            
        except Exception as e:
            logger.error(f"文本清理失败: {e}")
            result['warnings'].append(f"文本清理失败: {e}")
        
        return result
    
    def filter_output_text(self, text: str) -> str:
        """
        过滤输出文本（简化接口）
        
        Args:
            text: 要过滤的文本
            
        Returns:
            str: 过滤后的文本
        """
        try:
            result = self.process_text_encoding(text)
            if result['success']:
                return result['processed_text']
            else:
                logger.warning(f"文本过滤失败，使用原文本: {result.get('error')}")
                return text
        except Exception as e:
            logger.error(f"文本过滤异常: {e}")
            return text
    
    def validate_output_safety(self, text: str) -> Dict[str, Any]:
        """
        验证输出文本的安全性
        
        Args:
            text: 要验证的文本
            
        Returns:
            Dict[str, Any]: 安全性验证结果
        """
        result = {
            'is_safe': True,
            'issues': [],
            'risk_level': 'low',  # low, medium, high
            'recommendations': []
        }
        
        try:
            # 1. 检查长度
            if len(text) > self._max_output_length:
                result['issues'].append(f"文本过长 ({len(text)} > {self._max_output_length})")
                result['risk_level'] = 'medium'
            
            # 2. 检查控制字符
            control_chars = [char for char in text if ord(char) < 32 and char not in '\n\r\t']
            if control_chars:
                result['issues'].append(f"包含 {len(control_chars)} 个控制字符")
                result['risk_level'] = 'high'
                result['recommendations'].append("建议过滤控制字符")
            
            # 3. 检查不可见字符
            invisible_chars = [char for char in text if ord(char) in [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0xFEFF]]
            if invisible_chars:
                result['issues'].append(f"包含 {len(invisible_chars)} 个不可见字符")
                if result['risk_level'] == 'low':
                    result['risk_level'] = 'medium'
                result['recommendations'].append("建议过滤不可见字符")
            
            # 4. 检查编码问题
            try:
                text.encode('utf-8')
            except UnicodeEncodeError:
                result['issues'].append("编码问题：无法转换为UTF-8")
                result['risk_level'] = 'high'
                result['recommendations'].append("建议进行编码修复")
            
            # 5. 检查平台兼容性
            if self._platform == "Windows":
                problematic_chars = [char for char in text if ord(char) in [0x0000, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008, 0x000B, 0x000C, 0x000E, 0x000F]]
                if problematic_chars:
                    result['issues'].append(f"包含 {len(problematic_chars)} 个Windows不兼容字符")
                    if result['risk_level'] == 'low':
                        result['risk_level'] = 'medium'
            
            # 6. 更新安全状态
            if result['issues']:
                result['is_safe'] = False
            
        except Exception as e:
            result['is_safe'] = False
            result['issues'].append(f"验证异常: {e}")
            result['risk_level'] = 'high'
        
        return result
    
    def get_encoding_statistics(self, text: str) -> Dict[str, Any]:
        """
        获取文本编码统计信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict[str, Any]: 编码统计信息
        """
        try:
            stats = {
                'char_count': len(text),
                'byte_count_utf8': len(text.encode('utf-8')),
                'byte_count_utf16': len(text.encode('utf-16')),
                'ascii_chars': 0,
                'latin1_chars': 0,
                'unicode_chars': 0,
                'control_chars': 0,
                'whitespace_chars': 0,
                'printable_chars': 0,
                'special_chars': 0,
                'line_count': text.count('\n') + 1 if text else 0,
                'max_char_code': 0,
                'min_char_code': float('inf') if text else 0,
                'encoding_efficiency': 0.0
            }
            
            for char in text:
                char_code = ord(char)
                stats['max_char_code'] = max(stats['max_char_code'], char_code)
                stats['min_char_code'] = min(stats['min_char_code'], char_code)
                
                if char_code < 128:
                    stats['ascii_chars'] += 1
                elif char_code < 256:
                    stats['latin1_chars'] += 1
                else:
                    stats['unicode_chars'] += 1
                
                if char.isspace():
                    stats['whitespace_chars'] += 1
                elif char_code < 32:
                    stats['control_chars'] += 1
                elif char.isprintable():
                    stats['printable_chars'] += 1
                else:
                    stats['special_chars'] += 1
            
            # 计算编码效率
            if stats['char_count'] > 0:
                stats['encoding_efficiency'] = stats['char_count'] / stats['byte_count_utf8']
            
            if stats['min_char_code'] == float('inf'):
                stats['min_char_code'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"编码统计分析失败: {e}")
            return {'error': str(e)} 