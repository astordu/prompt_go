"""
提示词模板解析模块

负责解析 .md 文件格式的提示词模板，提取模型配置和提示词内容
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

# 占位符的正则表达式模式
PLACEHOLDER_PATTERN = re.compile(r'\{\{([^}]+)\}\}')


class TemplateParsingError(Exception):
    """模板解析异常"""
    pass


@dataclass
class TemplateContent:
    """模板内容数据类"""
    
    # 模型配置信息
    model_config: Dict[str, Any]
    
    # 提示词内容
    prompt_content: str
    
    # 原始文件内容
    raw_content: str
    
    # 模板文件信息
    file_info: Optional[Dict[str, Any]] = None
    
    def get_model_name(self) -> Optional[str]:
        """获取模型名称"""
        return self.model_config.get('model')
    
    def get_provider_name(self) -> Optional[str]:
        """
        获取厂商名称（如果是厂商,模型格式）
        
        Returns:
            Optional[str]: 厂商名称，如果不是厂商,模型格式则返回None
        """
        model = self.get_model_name()
        if model and ',' in model and len(model.split(',')) == 2:
            return model.split(',', 1)[0].strip()
        return None
    
    def get_specific_model_name(self) -> Optional[str]:
        """
        获取具体模型名称
        
        Returns:
            Optional[str]: 如果是厂商,模型格式则返回具体模型名，否则返回原模型名
        """
        model = self.get_model_name()
        if model and ',' in model and len(model.split(',')) == 2:
            return model.split(',', 1)[1].strip()
        return model
    
    def is_provider_model_format(self) -> bool:
        """
        检查是否使用厂商,模型格式
        
        Returns:
            bool: 是否使用厂商,模型格式
        """
        model = self.get_model_name()
        return model and ',' in model and len(model.split(',')) == 2
        
    def get_temperature(self) -> Optional[float]:
        """获取温度参数"""
        temp = self.model_config.get('temperature')
        return float(temp) if temp is not None else None
        
    def get_max_tokens(self) -> Optional[int]:
        """获取最大令牌数"""
        tokens = self.model_config.get('max_tokens')
        return int(tokens) if tokens is not None else None
        
    def has_config(self, key: str) -> bool:
        """检查是否包含指定的配置项"""
        return key in self.model_config
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项值"""
        return self.model_config.get(key, default)
        
    def find_placeholders(self) -> List[str]:
        """
        查找提示词内容中的所有占位符
        
        Returns:
            List[str]: 占位符变量名列表
        """
        matches = PLACEHOLDER_PATTERN.findall(self.prompt_content)
        return [match.strip() for match in matches]
        
    def get_placeholder_count(self) -> int:
        """
        获取占位符数量
        
        Returns:
            int: 占位符数量
        """
        return len(self.find_placeholders())
        
    def has_placeholders(self) -> bool:
        """
        检查是否包含占位符
        
        Returns:
            bool: 是否包含占位符
        """
        return self.get_placeholder_count() > 0
        
    def get_primary_placeholder(self) -> Optional[str]:
        """
        获取主要的占位符变量名（第一个）
        
        Returns:
            Optional[str]: 主要占位符变量名，如果没有则返回None
        """
        placeholders = self.find_placeholders()
        return placeholders[0] if placeholders else None
        
    def replace_placeholders(self, replacements: Dict[str, str]) -> str:
        """
        替换提示词内容中的占位符
        
        Args:
            replacements: 占位符替换字典，键为占位符变量名，值为替换内容
            
        Returns:
            str: 替换后的提示词内容
        """
        result = self.prompt_content
        
        for placeholder_var, replacement_text in replacements.items():
            # 构建完整的占位符格式
            full_placeholder = f"{{{{{placeholder_var}}}}}"
            result = result.replace(full_placeholder, replacement_text)
            
        return result
        
    def replace_primary_placeholder(self, replacement_text: str) -> str:
        """
        替换主要占位符（第一个占位符）
        
        Args:
            replacement_text: 替换文本
            
        Returns:
            str: 替换后的提示词内容
            
        Raises:
            ValueError: 如果没有找到占位符
        """
        primary_placeholder = self.get_primary_placeholder()
        
        if primary_placeholder is None:
            raise ValueError("模板中没有找到占位符")
            
        return self.replace_placeholders({primary_placeholder: replacement_text})
        
    def validate_single_placeholder(self) -> bool:
        """
        验证模板是否只包含一个占位符
        
        Returns:
            bool: 是否只包含一个占位符
        """
        return self.get_placeholder_count() == 1


class TemplateReader:
    """模板文件读取器"""
    
    def __init__(self):
        """初始化模板读取器"""
        self.supported_extensions = ['.md']
        
    def read_template_file(self, file_path: Union[str, Path]) -> str:
        """
        读取模板文件内容
        
        Args:
            file_path: 模板文件路径
            
        Returns:
            str: 文件内容
            
        Raises:
            TemplateParsingError: 文件读取失败时抛出异常
        """
        file_path = Path(file_path)
        
        # 验证文件存在
        if not file_path.exists():
            raise TemplateParsingError(f"模板文件不存在: {file_path}")
            
        # 验证文件扩展名
        if file_path.suffix.lower() not in self.supported_extensions:
            raise TemplateParsingError(f"不支持的文件格式: {file_path.suffix}")
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            logger.debug(f"成功读取模板文件: {file_path} (大小: {len(content)} 字符)")
            return content
            
        except UnicodeDecodeError as e:
            raise TemplateParsingError(f"文件编码错误 ({file_path}): {e}")
        except IOError as e:
            raise TemplateParsingError(f"文件读取失败 ({file_path}): {e}")
            
    def validate_file_format(self, file_path: Union[str, Path]) -> bool:
        """
        验证文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否支持该格式
        """
        file_path = Path(file_path)
        return file_path.suffix.lower() in self.supported_extensions
        
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        获取文件基本信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            dict: 文件信息
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {'exists': False}
            
        try:
            stat = file_path.stat()
            return {
                'exists': True,
                'name': file_path.name,
                'stem': file_path.stem,
                'suffix': file_path.suffix,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'is_supported': self.validate_file_format(file_path)
            }
        except Exception as e:
            logger.error(f"获取文件信息失败 ({file_path}): {e}")
            return {'exists': True, 'error': str(e)}


class TemplateScanner:
    """模板文件扫描器"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化模板扫描器
        
        Args:
            template_directory: 模板目录路径
        """
        self.template_directory = Path(template_directory)
        self.reader = TemplateReader()
        
    def scan_template_files(self, recursive: bool = False) -> List[Path]:
        """
        扫描模板目录下的所有模板文件
        
        Args:
            recursive: 是否递归扫描子目录
            
        Returns:
            List[Path]: 模板文件路径列表
        """
        if not self.template_directory.exists():
            logger.warning(f"模板目录不存在: {self.template_directory}")
            return []
            
        if not self.template_directory.is_dir():
            logger.error(f"模板路径不是目录: {self.template_directory}")
            return []
            
        try:
            if recursive:
                pattern = "**/*.md"
            else:
                pattern = "*.md"
                
            template_files = list(self.template_directory.glob(pattern))
            
            # 过滤掉非支持的文件（额外的验证）
            supported_files = [
                f for f in template_files 
                if self.reader.validate_file_format(f)
            ]
            
            logger.info(f"在 {self.template_directory} 中发现 {len(supported_files)} 个模板文件")
            
            return sorted(supported_files)  # 返回排序后的列表，便于调试
            
        except Exception as e:
            logger.error(f"扫描模板文件失败: {e}")
            return []
            
    def get_template_list(self) -> List[Dict[str, Any]]:
        """
        获取模板文件列表及其基本信息
        
        Returns:
            List[Dict]: 模板文件信息列表
        """
        template_files = self.scan_template_files()
        template_info = []
        
        for file_path in template_files:
            info = self.reader.get_file_info(file_path)
            info['path'] = file_path
            info['relative_path'] = file_path.relative_to(self.template_directory)
            template_info.append(info)
            
        return template_info
        
    def find_template_by_name(self, template_name: str) -> Optional[Path]:
        """
        根据模板名称查找模板文件
        
        Args:
            template_name: 模板名称（支持带或不带.md扩展名）
            
        Returns:
            Optional[Path]: 找到的模板文件路径，未找到则返回None
        """
        # 确保模板名称有.md扩展名
        if not template_name.endswith('.md'):
            template_name += '.md'
            
        template_path = self.template_directory / template_name
        
        if template_path.exists() and self.reader.validate_file_format(template_path):
            return template_path
            
        return None


class BasicTemplateParser:
    """基础模板解析器"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化基础模板解析器
        
        Args:
            template_directory: 模板目录路径
        """
        self.template_directory = Path(template_directory)
        self.reader = TemplateReader()
        self.scanner = TemplateScanner(template_directory)
        
    def load_template(self, template_name: str) -> str:
        """
        加载指定的模板文件
        
        Args:
            template_name: 模板名称
            
        Returns:
            str: 模板文件内容
            
        Raises:
            TemplateParsingError: 模板加载失败时抛出异常
        """
        # 查找模板文件
        template_path = self.scanner.find_template_by_name(template_name)
        
        if template_path is None:
            raise TemplateParsingError(f"未找到模板文件: {template_name}")
            
        # 读取模板内容
        return self.reader.read_template_file(template_path)
        
    def load_template_by_path(self, template_path: Union[str, Path]) -> str:
        """
        根据路径加载模板文件
        
        Args:
            template_path: 模板文件路径
            
        Returns:
            str: 模板文件内容
        """
        return self.reader.read_template_file(template_path)
        
    def get_available_templates(self) -> List[str]:
        """
        获取可用的模板名称列表
        
        Returns:
            List[str]: 模板名称列表
        """
        template_info = self.scanner.get_template_list()
        return [info['name'] for info in template_info if info.get('is_supported', False)]
    
    def template_exists(self, template_name: str) -> bool:
        """
        检查指定的模板文件是否存在
        
        Args:
            template_name: 模板名称
            
        Returns:
            bool: 模板文件是否存在
        """
        template_path = self.scanner.find_template_by_name(template_name)
        return template_path is not None


class TemplateParser(BasicTemplateParser):
    """完整模板解析器 - 支持"---"分隔符和YAML配置解析"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化模板解析器
        
        Args:
            template_directory: 模板目录路径
        """
        super().__init__(template_directory)
        self.separator = "---"
        
    def parse_template_content(self, content: str) -> TemplateContent:
        """
        解析模板内容，分离模型配置和提示词内容
        
        Args:
            content: 原始模板内容
            
        Returns:
            TemplateContent: 解析后的模板内容对象
            
        Raises:
            TemplateParsingError: 解析失败时抛出异常
        """
        if not content or not content.strip():
            raise TemplateParsingError("模板内容为空")
            
        # 分割内容
        parts = content.split(self.separator, 1)
        
        if len(parts) != 2:
            raise TemplateParsingError(
                f"模板格式错误：必须包含 '{self.separator}' 分隔符，将模型配置和提示词内容分开"
            )
            
        config_part = parts[0].strip()
        prompt_part = parts[1].strip()
        
        # 解析模型配置部分
        try:
            model_config = self._parse_model_config(config_part)
        except Exception as e:
            raise TemplateParsingError(f"模型配置解析失败: {e}")
            
        # 验证提示词内容不为空
        if not prompt_part:
            raise TemplateParsingError("提示词内容不能为空")
            
        return TemplateContent(
            model_config=model_config,
            prompt_content=prompt_part,
            raw_content=content
        )
        
    def _parse_model_config(self, config_content: str) -> Dict[str, Any]:
        """
        解析模型配置YAML内容
        
        Args:
            config_content: YAML格式的配置内容
            
        Returns:
            Dict[str, Any]: 解析后的配置字典
            
        Raises:
            TemplateParsingError: YAML解析失败时抛出异常
        """
        if not config_content:
            raise TemplateParsingError("模型配置不能为空")
            
        try:
            config = yaml.safe_load(config_content)
            
            if config is None:
                config = {}
            elif not isinstance(config, dict):
                raise TemplateParsingError("模型配置必须是YAML对象格式")
                
            # 验证必需的配置项
            self._validate_model_config(config)
            
            return config
            
        except yaml.YAMLError as e:
            raise TemplateParsingError(f"YAML格式错误: {e}")
            
    def _validate_model_config(self, config: Dict[str, Any]) -> None:
        """
        验证模型配置的有效性
        
        Args:
            config: 模型配置字典
            
        Raises:
            TemplateParsingError: 配置无效时抛出异常
        """
        # 检查必需的配置项
        required_fields = ['model']
        for field in required_fields:
            if field not in config:
                raise TemplateParsingError(f"缺少必需的配置项: {field}")
                
        # 验证模型名称
        model = config.get('model')
        if not isinstance(model, str) or not model.strip():
            raise TemplateParsingError("model 配置项必须是非空字符串")
            
        # 验证支持的模型（支持厂商,模型格式和简化格式）
        if self._is_provider_model_format(model):
            # 厂商,模型格式：如 "deepseek,deepseek-chat"
            provider, specific_model = self._parse_provider_model(model)
            if not self._validate_provider_model_combination(provider, specific_model):
                raise TemplateParsingError(
                    f"不支持的厂商和模型组合: {model}，请检查厂商和模型名称是否匹配"
                )
        else:
            # 简化格式：如 "deepseek" 或 "deepseek-chat"
            supported_models = [
                'deepseek', 'deepseek-chat', 'deepseek-reasoner',  # DeepSeek系列
                'kimi', 'moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'  # Kimi系列
            ]
            if model not in supported_models:
                raise TemplateParsingError(
                    f"不支持的模型: {model}，支持的模型: {', '.join(supported_models)} 或厂商,模型格式（如: deepseek,deepseek-chat）"
                )
            
        # 验证可选的数值配置项
        numeric_fields = {
            'temperature': (0.0, 2.0, float),
            'max_tokens': (1, 32000, int),
            'top_p': (0.0, 1.0, float),
            'frequency_penalty': (-2.0, 2.0, float),
            'presence_penalty': (-2.0, 2.0, float)
        }
        
        for field, (min_val, max_val, expected_type) in numeric_fields.items():
            if field in config:
                value = config[field]
                try:
                    # 尝试转换为预期类型
                    converted_value = expected_type(value)
                    
                    # 检查范围
                    if not (min_val <= converted_value <= max_val):
                        raise TemplateParsingError(
                            f"{field} 配置项超出有效范围 [{min_val}, {max_val}]: {value}"
                        )
                        
                    # 更新配置为转换后的值
                    config[field] = converted_value
                    
                except (ValueError, TypeError):
                    raise TemplateParsingError(
                        f"{field} 配置项必须是 {expected_type.__name__} 类型: {value}"
                    )
    
    def _is_provider_model_format(self, model: str) -> bool:
        """
        检查是否是厂商,模型格式
        
        Args:
            model: 模型字符串
            
        Returns:
            bool: 是否是厂商,模型格式
        """
        return ',' in model and len(model.split(',')) == 2
    
    def _parse_provider_model(self, model: str) -> Tuple[str, str]:
        """
        解析厂商,模型格式
        
        Args:
            model: 厂商,模型格式的字符串
            
        Returns:
            tuple[str, str]: (厂商, 具体模型)
        """
        parts = model.split(',', 1)
        provider = parts[0].strip()
        specific_model = parts[1].strip()
        return provider, specific_model
    
    def _validate_provider_model_combination(self, provider: str, specific_model: str) -> bool:
        """
        验证厂商和模型的组合是否有效
        
        Args:
            provider: 厂商名称
            specific_model: 具体模型名称
            
        Returns:
            bool: 组合是否有效
        """
        # 定义厂商和对应的模型映射
        provider_models = {
            'deepseek': ['deepseek-chat', 'deepseek-reasoner'],
            'kimi': ['kimi-k2-0711-preview']
        }
        
        # 检查厂商是否支持
        if provider not in provider_models:
            return False
            
        # 检查模型是否属于该厂商
        return specific_model in provider_models[provider]
                    
    def parse_template(self, template_name: str) -> TemplateContent:
        """
        解析指定的模板文件
        
        Args:
            template_name: 模板名称
            
        Returns:
            TemplateContent: 解析后的模板内容对象
            
        Raises:
            TemplateParsingError: 模板解析失败时抛出异常
        """
        # 加载模板内容
        content = self.load_template(template_name)
        
        # 解析模板内容
        template_content = self.parse_template_content(content)
        
        # 添加文件信息
        template_path = self.scanner.find_template_by_name(template_name)
        if template_path:
            template_content.file_info = self.reader.get_file_info(template_path)
            
        return template_content
        
    def parse_template_by_path(self, template_path: Union[str, Path]) -> TemplateContent:
        """
        根据路径解析模板文件
        
        Args:
            template_path: 模板文件路径
            
        Returns:
            TemplateContent: 解析后的模板内容对象
        """
        # 加载模板内容
        content = self.load_template_by_path(template_path)
        
        # 解析模板内容
        template_content = self.parse_template_content(content)
        
        # 添加文件信息
        template_content.file_info = self.reader.get_file_info(template_path)
        
        return template_content
        
    def get_parsed_templates(self) -> List[TemplateContent]:
        """
        解析所有可用的模板文件
        
        Returns:
            List[TemplateContent]: 解析后的模板内容列表
        """
        templates = []
        template_files = self.scanner.scan_template_files()
        
        for template_path in template_files:
            try:
                # 跳过README文件
                if template_path.name.lower() == 'readme.md':
                    continue
                    
                template_content = self.parse_template_by_path(template_path)
                templates.append(template_content)
                
            except TemplateParsingError as e:
                logger.warning(f"跳过模板文件 {template_path}: {e}")
            except Exception as e:
                logger.error(f"解析模板文件 {template_path} 时发生未知错误: {e}")
                
        return templates


class PlaceholderProcessor:
    """占位符处理器"""
    
    def __init__(self):
        """初始化占位符处理器"""
        self.pattern = PLACEHOLDER_PATTERN
        
    def find_placeholders(self, text: str) -> List[str]:
        """
        在文本中查找所有占位符
        
        Args:
            text: 要搜索的文本
            
        Returns:
            List[str]: 占位符变量名列表
        """
        matches = self.pattern.findall(text)
        return [match.strip() for match in matches]
        
    def get_placeholder_positions(self, text: str) -> List[Dict[str, Any]]:
        """
        获取占位符在文本中的位置信息
        
        Args:
            text: 要搜索的文本
            
        Returns:
            List[Dict]: 占位符位置信息列表
        """
        positions = []
        for match in self.pattern.finditer(text):
            positions.append({
                'variable': match.group(1).strip(),
                'full_match': match.group(0),
                'start': match.start(),
                'end': match.end()
            })
        return positions
        
    def validate_placeholder_format(self, text: str) -> List[str]:
        """
        验证占位符格式的有效性
        
        Args:
            text: 要验证的文本
            
        Returns:
            List[str]: 格式错误列表，如果为空则表示格式正确
        """
        errors = []
        
        # 检查是否有不匹配的大括号
        open_braces = text.count('{')
        close_braces = text.count('}')
        
        if open_braces != close_braces:
            errors.append(f"大括号不匹配：{{ 数量={open_braces}, }} 数量={close_braces}")
            
        # 检查是否有不正确的占位符格式
        import re
        
        # 查找孤立的单个大括号（不属于占位符的部分）
        # 先移除所有正确的占位符，然后查找剩余的孤立大括号
        text_without_placeholders = self.pattern.sub('', text)
        
        if '{' in text_without_placeholders or '}' in text_without_placeholders:
            errors.append("发现孤立的大括号（不属于 {{变量名}} 格式）")
        
        # 检查空占位符
        if '{{}' in text:
            errors.append("发现空占位符 {{}}")
        
        # 检查不完整的占位符格式
        incomplete_patterns = [
            r'\{\{[^}]*$',  # {{ 后没有闭合
            r'^[^{]*\}\}',  # }} 前没有开始
        ]
        
        for pattern in incomplete_patterns:
            if re.search(pattern, text, re.MULTILINE):
                errors.append("发现不完整的占位符格式")
                
        return errors
        
    def replace_placeholders(self, text: str, replacements: Dict[str, str]) -> str:
        """
        替换文本中的占位符
        
        Args:
            text: 原始文本
            replacements: 替换字典
            
        Returns:
            str: 替换后的文本
        """
        result = text
        
        for variable, replacement in replacements.items():
            full_placeholder = f"{{{{{variable}}}}}"
            result = result.replace(full_placeholder, replacement)
            
        return result
        
    def replace_all_with_same_value(self, text: str, replacement: str) -> str:
        """
        将所有占位符替换为相同的值
        
        Args:
            text: 原始文本
            replacement: 替换值
            
        Returns:
            str: 替换后的文本
        """
        # 使用正则表达式替换所有占位符
        return self.pattern.sub(replacement, text)
        
    def get_placeholder_statistics(self, text: str) -> Dict[str, Any]:
        """
        获取占位符统计信息
        
        Args:
            text: 要分析的文本
            
        Returns:
            Dict: 统计信息
        """
        placeholders = self.find_placeholders(text)
        positions = self.get_placeholder_positions(text)
        
        return {
            'total_count': len(placeholders),
            'unique_count': len(set(placeholders)),
            'placeholders': placeholders,
            'unique_placeholders': list(set(placeholders)),
            'positions': positions,
            'has_duplicates': len(placeholders) != len(set(placeholders))
        }


class AdvancedTemplateParser(TemplateParser):
    """高级模板解析器 - 包含占位符处理功能"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化高级模板解析器
        
        Args:
            template_directory: 模板目录路径
        """
        super().__init__(template_directory)
        self.placeholder_processor = PlaceholderProcessor()
        
    def parse_template_with_validation(self, template_name: str, 
                                     strict_single_placeholder: bool = True) -> TemplateContent:
        """
        解析模板并进行占位符验证
        
        Args:
            template_name: 模板名称
            strict_single_placeholder: 是否严格要求只有一个占位符
            
        Returns:
            TemplateContent: 解析后的模板内容对象
            
        Raises:
            TemplateParsingError: 解析或验证失败时抛出异常
        """
        # 先进行基本解析
        template_content = self.parse_template(template_name)
        
        # 验证占位符格式
        format_errors = self.placeholder_processor.validate_placeholder_format(
            template_content.prompt_content
        )
        if format_errors:
            raise TemplateParsingError(f"占位符格式错误: {'; '.join(format_errors)}")
            
        # 获取占位符统计信息
        stats = self.placeholder_processor.get_placeholder_statistics(
            template_content.prompt_content
        )
        
        # 验证占位符数量要求
        if strict_single_placeholder:
            if stats['total_count'] == 0:
                raise TemplateParsingError(f"模板 {template_name} 缺少必需的占位符")
            elif stats['total_count'] > 1:
                raise TemplateParsingError(
                    f"模板 {template_name} 包含多个占位符 ({stats['total_count']} 个)，"
                    f"但要求只能有一个占位符"
                )
            elif stats['has_duplicates']:
                raise TemplateParsingError(
                    f"模板 {template_name} 包含重复的占位符变量名"
                )
                
        return template_content
        
    def process_template(self, template_name: str, input_text: str, 
                        strict_validation: bool = True) -> str:
        """
        处理模板：解析并替换占位符
        
        Args:
            template_name: 模板名称
            input_text: 要插入的文本
            strict_validation: 是否进行严格验证
            
        Returns:
            str: 处理后的完整提示词
            
        Raises:
            TemplateParsingError: 处理失败时抛出异常
        """
        # 解析模板
        template_content = self.parse_template_with_validation(
            template_name, strict_single_placeholder=strict_validation
        )
        
        # 替换占位符
        if strict_validation:
            # 严格模式：使用主要占位符替换
            try:
                processed_content = template_content.replace_primary_placeholder(input_text)
            except ValueError as e:
                raise TemplateParsingError(f"替换占位符失败: {e}")
        else:
            # 宽松模式：替换所有占位符为相同值
            processed_content = self.placeholder_processor.replace_all_with_same_value(
                template_content.prompt_content, input_text
            )
            
        return processed_content
        
    def get_template_info_with_placeholders(self, template_name: str) -> Dict[str, Any]:
        """
        获取模板信息包括占位符详情
        
        Args:
            template_name: 模板名称
            
        Returns:
            Dict: 模板详细信息
        """
        try:
            template_content = self.parse_template(template_name)
            placeholder_stats = self.placeholder_processor.get_placeholder_statistics(
                template_content.prompt_content
            )
            
            return {
                'template_name': template_name,
                'model_name': template_content.get_model_name(),
                'temperature': template_content.get_temperature(),
                'max_tokens': template_content.get_max_tokens(),
                'model_config': template_content.model_config,
                'prompt_length': len(template_content.prompt_content),
                'placeholder_stats': placeholder_stats,
                'is_valid_single_placeholder': placeholder_stats['total_count'] == 1,
                'file_info': template_content.file_info
            }
        except Exception as e:
            return {
                'template_name': template_name,
                'error': str(e),
                'is_valid': False
            }


class TemplateValidator:
    """模板验证器 - 专门用于验证模板的各种规则"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化模板验证器
        
        Args:
            template_directory: 模板目录路径
        """
        self.template_directory = Path(template_directory)
        self.parser = AdvancedTemplateParser(template_directory)
        self.placeholder_processor = PlaceholderProcessor()
        
    def validate_single_template(self, template_name: str, 
                                strict_single_placeholder: bool = True) -> Dict[str, Any]:
        """
        验证单个模板文件
        
        Args:
            template_name: 模板名称
            strict_single_placeholder: 是否严格要求单占位符
            
        Returns:
            Dict: 验证结果
        """
        result = {
            'template_name': template_name,
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }
        
        try:
            # 1. 基本文件存在性检查
            if not self.parser.template_exists(template_name):
                result['is_valid'] = False
                result['errors'].append(f"模板文件不存在: {template_name}")
                return result
                
            # 2. 解析模板
            try:
                template_content = self.parser.parse_template(template_name)
                result['details']['model_config'] = template_content.model_config
                result['details']['prompt_length'] = len(template_content.prompt_content)
            except TemplateParsingError as e:
                result['is_valid'] = False
                result['errors'].append(f"模板解析失败: {e}")
                return result
                
            # 3. 占位符验证
            placeholder_errors = self._validate_placeholders(
                template_content, strict_single_placeholder
            )
            if placeholder_errors:
                result['is_valid'] = False
                result['errors'].extend(placeholder_errors)
                
            # 4. 占位符格式验证
            format_errors = self.placeholder_processor.validate_placeholder_format(
                template_content.prompt_content
            )
            if format_errors:
                result['is_valid'] = False
                result['errors'].extend([f"占位符格式错误: {err}" for err in format_errors])
                
            # 5. 模型配置验证
            config_warnings = self._validate_model_config(template_content.model_config)
            if config_warnings:
                result['warnings'].extend(config_warnings)
                
            # 6. 内容质量检查
            content_warnings = self._validate_content_quality(template_content)
            if content_warnings:
                result['warnings'].extend(content_warnings)
                
            # 7. 添加占位符统计信息
            placeholder_stats = self.placeholder_processor.get_placeholder_statistics(
                template_content.prompt_content
            )
            result['details']['placeholder_stats'] = placeholder_stats
            
        except Exception as e:
            result['is_valid'] = False
            result['errors'].append(f"验证过程中发生未知错误: {e}")
            
        return result
        
    def _validate_placeholders(self, template_content: TemplateContent, 
                              strict_single_placeholder: bool) -> List[str]:
        """
        验证占位符相关规则
        
        Args:
            template_content: 模板内容对象
            strict_single_placeholder: 是否严格要求单占位符
            
        Returns:
            List[str]: 错误信息列表
        """
        errors = []
        
        placeholder_count = template_content.get_placeholder_count()
        placeholders = template_content.find_placeholders()
        
        if strict_single_placeholder:
            # 严格单占位符模式
            if placeholder_count == 0:
                errors.append("模板缺少必需的占位符")
            elif placeholder_count > 1:
                errors.append(
                    f"模板包含 {placeholder_count} 个占位符，但要求只能有一个。"
                    f"发现的占位符: {placeholders}"
                )
            
            # 检查重复占位符
            unique_placeholders = list(set(placeholders))
            if len(placeholders) != len(unique_placeholders):
                duplicate_count = len(placeholders) - len(unique_placeholders)
                errors.append(f"发现 {duplicate_count} 个重复的占位符")
                
        else:
            # 宽松模式的基本检查
            if placeholder_count == 0:
                errors.append("模板建议至少包含一个占位符")
                
        # 检查占位符变量名的有效性
        for placeholder in placeholders:
            if not self._is_valid_placeholder_name(placeholder):
                errors.append(f"无效的占位符变量名: '{placeholder}'")
                
        return errors
        
    def _is_valid_placeholder_name(self, name: str) -> bool:
        """
        验证占位符变量名是否有效
        
        Args:
            name: 占位符变量名
            
        Returns:
            bool: 是否有效
        """
        # 基本规则：不能为空，不能包含特殊字符，建议使用字母数字下划线
        if not name or not name.strip():
            return False
            
        name = name.strip()
        
        # 检查是否只包含字母、数字、下划线
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            return False
            
        # 检查长度限制
        if len(name) > 50:  # 合理的长度限制
            return False
            
        return True
        
    def _validate_model_config(self, model_config: Dict[str, Any]) -> List[str]:
        """
        验证模型配置并提供建议
        
        Args:
            model_config: 模型配置字典
            
        Returns:
            List[str]: 警告信息列表
        """
        warnings = []
        
        # 检查温度设置的合理性
        temperature = model_config.get('temperature')
        if temperature is not None:
            if temperature <= 0.1:
                warnings.append("温度设置过低（≤0.1），可能导致输出过于确定性")
            elif temperature >= 1.5:
                warnings.append("温度设置过高（≥1.5），可能导致输出过于随机")
                
        # 检查max_tokens设置
        max_tokens = model_config.get('max_tokens')
        if max_tokens is not None:
            if max_tokens < 100:
                warnings.append("max_tokens设置过低（<100），可能导致输出被截断")
            elif max_tokens > 8000:
                warnings.append("max_tokens设置过高（>8000），可能影响响应速度")
                
        # 建议设置的配置项
        recommended_configs = ['temperature', 'max_tokens']
        missing_configs = [cfg for cfg in recommended_configs if cfg not in model_config]
        if missing_configs:
            warnings.append(f"建议设置以下配置项以获得更好的控制: {', '.join(missing_configs)}")
            
        return warnings
        
    def _validate_content_quality(self, template_content: TemplateContent) -> List[str]:
        """
        验证提示词内容质量
        
        Args:
            template_content: 模板内容对象
            
        Returns:
            List[str]: 警告信息列表
        """
        warnings = []
        content = template_content.prompt_content
        
        # 长度检查
        if len(content) < 20:
            warnings.append("提示词内容过短（<20字符），可能缺少必要的指导信息")
        elif len(content) > 2000:
            warnings.append("提示词内容过长（>2000字符），可能影响处理效率")
            
        # 基本质量检查
        if not any(char.isalpha() for char in content):
            warnings.append("提示词内容缺少文字描述")
            
        # 检查是否包含基本的指导性语言
        instruction_keywords = ['请', '请求', '需要', '要求', '指示', '说明', 'please', 'generate', 'create']
        if not any(keyword in content.lower() for keyword in instruction_keywords):
            warnings.append("提示词内容建议包含明确的指导性语言")
            
        return warnings
        
    def validate_all_templates(self, strict_single_placeholder: bool = True) -> Dict[str, Any]:
        """
        验证所有模板文件
        
        Args:
            strict_single_placeholder: 是否严格要求单占位符
            
        Returns:
            Dict: 完整的验证报告
        """
        report = {
            'total_templates': 0,
            'valid_templates': 0,
            'invalid_templates': 0,
            'templates_with_warnings': 0,
            'validation_results': [],
            'summary': {
                'common_errors': {},
                'common_warnings': {}
            }
        }
        
        # 获取所有可用模板
        try:
            available_templates = self.parser.get_available_templates()
            # 排除README文件
            template_files = [t for t in available_templates if t.lower() != 'readme.md']
        except Exception as e:
            report['error'] = f"无法获取模板列表: {e}"
            return report
            
        report['total_templates'] = len(template_files)
        
        # 验证每个模板
        for template_name in template_files:
            result = self.validate_single_template(template_name, strict_single_placeholder)
            report['validation_results'].append(result)
            
            if result['is_valid']:
                report['valid_templates'] += 1
            else:
                report['invalid_templates'] += 1
                
            if result['warnings']:
                report['templates_with_warnings'] += 1
                
            # 统计常见错误和警告
            for error in result['errors']:
                key = error.split(':')[0] if ':' in error else error
                report['summary']['common_errors'][key] = report['summary']['common_errors'].get(key, 0) + 1
                
            for warning in result['warnings']:
                key = warning.split('：')[0] if '：' in warning else warning.split(':')[0] if ':' in warning else warning
                report['summary']['common_warnings'][key] = report['summary']['common_warnings'].get(key, 0) + 1
                
        return report
        
    def get_validation_summary(self, report: Dict[str, Any]) -> str:
        """
        生成验证报告的文字摘要
        
        Args:
            report: 验证报告
            
        Returns:
            str: 文字摘要
        """
        if 'error' in report:
            return f"❌ 验证失败: {report['error']}"
            
        total = report['total_templates']
        valid = report['valid_templates']
        invalid = report['invalid_templates']
        with_warnings = report['templates_with_warnings']
        
        lines = [
            f"📊 模板验证报告摘要",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📁 总模板数: {total}",
            f"✅ 有效模板: {valid}",
            f"❌ 无效模板: {invalid}",
            f"⚠️  有警告的模板: {with_warnings}",
        ]
        
        if invalid > 0:
            lines.append("\n🔍 常见错误:")
            for error, count in sorted(report['summary']['common_errors'].items(), 
                                     key=lambda x: x[1], reverse=True)[:3]:
                lines.append(f"  • {error}: {count} 次")
                
        if with_warnings > 0:
            lines.append("\n💡 常见警告:")
            for warning, count in sorted(report['summary']['common_warnings'].items(), 
                                       key=lambda x: x[1], reverse=True)[:3]:
                lines.append(f"  • {warning}: {count} 次")
                
        lines.append(f"\n📈 总体健康度: {(valid/total)*100:.1f}%")
        
        return "\n".join(lines)


class TemplateLoader:
    """模板加载器 - 自动扫描和加载.md文件"""
    
    def __init__(self, template_directory: Union[str, Path] = "prompt"):
        """
        初始化模板加载器
        
        Args:
            template_directory: 模板目录路径
        """
        self.template_directory = Path(template_directory)
        self.parser = AdvancedTemplateParser(template_directory)
        self.scanner = TemplateScanner(template_directory)
        
        # 缓存系统
        self._template_cache = {}  # 模板内容缓存
        self._file_mtimes = {}     # 文件修改时间缓存
        self._scan_cache = None    # 扫描结果缓存
        self._scan_timestamp = 0   # 扫描时间戳
        
        # 配置参数
        self.cache_ttl = 300      # 缓存存活时间（秒）
        self.auto_reload = True   # 是否启用自动重载
        self.recursive_scan = False  # 是否递归扫描子目录
        
        # 统计信息
        self.stats = {
            'total_scans': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'files_loaded': 0,
            'files_reloaded': 0,
            'last_scan_time': None,
            'last_load_time': None
        }
        
    def configure(self, cache_ttl: int = None, auto_reload: bool = None, 
                  recursive_scan: bool = None):
        """
        配置加载器参数
        
        Args:
            cache_ttl: 缓存存活时间（秒）
            auto_reload: 是否启用自动重载
            recursive_scan: 是否递归扫描子目录
        """
        if cache_ttl is not None:
            self.cache_ttl = cache_ttl
        if auto_reload is not None:
            self.auto_reload = auto_reload  
        if recursive_scan is not None:
            self.recursive_scan = recursive_scan
            
        logger.info(f"模板加载器配置更新: cache_ttl={self.cache_ttl}, "
                   f"auto_reload={self.auto_reload}, recursive_scan={self.recursive_scan}")
        
    def scan_templates(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        扫描模板文件
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            List[Dict]: 模板文件信息列表
        """
        import time
        
        current_time = time.time()
        
        # 检查缓存是否有效
        if (not force_refresh and 
            self._scan_cache is not None and 
            (current_time - self._scan_timestamp) < self.cache_ttl):
            
            self.stats['cache_hits'] += 1
            logger.debug("使用缓存的扫描结果")
            return self._scan_cache
            
        # 执行新的扫描
        self.stats['total_scans'] += 1
        self.stats['cache_misses'] += 1
        self.stats['last_scan_time'] = current_time
        
        logger.info(f"开始扫描模板目录: {self.template_directory}")
        
        try:
            # 使用现有的扫描功能
            template_files = self.scanner.scan_template_files(recursive=self.recursive_scan)
            
            # 获取详细信息
            template_info_list = []
            
            for template_path in template_files:
                # 跳过README文件
                if template_path.name.lower() == 'readme.md':
                    continue
                    
                try:
                    file_info = self.scanner.reader.get_file_info(template_path)
                    
                    # 添加额外的信息
                    file_info.update({
                        'path': template_path,
                        'relative_path': template_path.relative_to(self.template_directory),
                        'template_name': template_path.name,
                        'stem': template_path.stem,
                        'is_cached': str(template_path) in self._template_cache,
                        'needs_reload': self._needs_reload(template_path, file_info.get('modified', 0))
                    })
                    
                    template_info_list.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"获取模板文件信息失败 {template_path}: {e}")
                    
            # 更新缓存
            self._scan_cache = template_info_list
            self._scan_timestamp = current_time
            
            logger.info(f"扫描完成，发现 {len(template_info_list)} 个模板文件")
            
            return template_info_list
            
        except Exception as e:
            logger.error(f"扫描模板目录失败: {e}")
            # 返回空列表而不是抛出异常
            return []
            
    def _needs_reload(self, template_path: Path, current_mtime: float) -> bool:
        """
        检查模板是否需要重新加载
        
        Args:
            template_path: 模板文件路径
            current_mtime: 当前文件修改时间
            
        Returns:
            bool: 是否需要重新加载
        """
        if not self.auto_reload:
            return False
            
        path_str = str(template_path)
        
        # 如果文件不在缓存中，需要加载
        if path_str not in self._template_cache:
            return True
            
        # 如果没有记录的修改时间，需要重新加载
        if path_str not in self._file_mtimes:
            return True
            
        # 如果文件修改时间发生变化，需要重新加载
        cached_mtime = self._file_mtimes.get(path_str, 0)
        return current_mtime > cached_mtime
        
    def load_template(self, template_name: str, use_cache: bool = True) -> Optional[TemplateContent]:
        """
        加载指定的模板
        
        Args:
            template_name: 模板名称
            use_cache: 是否使用缓存
            
        Returns:
            Optional[TemplateContent]: 加载的模板内容，失败时返回None
        """
        import time
        
        try:
            # 查找模板文件
            template_path = self.scanner.find_template_by_name(template_name)
            
            if template_path is None:
                logger.warning(f"未找到模板文件: {template_name}")
                return None
                
            path_str = str(template_path)
            
            # 获取文件信息
            file_info = self.scanner.reader.get_file_info(template_path)
            current_mtime = file_info.get('modified', 0)
            
            # 检查缓存
            if (use_cache and 
                path_str in self._template_cache and
                not self._needs_reload(template_path, current_mtime)):
                
                self.stats['cache_hits'] += 1
                logger.debug(f"使用缓存的模板: {template_name}")
                return self._template_cache[path_str]
                
            # 加载模板
            self.stats['cache_misses'] += 1
            self.stats['last_load_time'] = time.time()
            
            if path_str in self._template_cache:
                self.stats['files_reloaded'] += 1
                logger.info(f"重新加载模板: {template_name}")
            else:
                self.stats['files_loaded'] += 1
                logger.info(f"加载新模板: {template_name}")
                
            template_content = self.parser.parse_template_by_path(template_path)
            
            # 更新缓存
            self._template_cache[path_str] = template_content
            self._file_mtimes[path_str] = current_mtime
            
            return template_content
            
        except Exception as e:
            logger.error(f"加载模板失败 {template_name}: {e}")
            return None
            
    def load_all_templates(self, use_cache: bool = True, 
                          force_refresh: bool = False) -> Dict[str, TemplateContent]:
        """
        加载所有模板
        
        Args:
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新
            
        Returns:
            Dict[str, TemplateContent]: 加载的所有模板内容
        """
        templates = {}
        
        # 先扫描获取所有模板文件
        template_list = self.scan_templates(force_refresh=force_refresh)
        
        logger.info(f"开始批量加载 {len(template_list)} 个模板")
        
        success_count = 0
        error_count = 0
        
        for template_info in template_list:
            template_name = template_info['name']
            
            try:
                template_content = self.load_template(template_name, use_cache=use_cache)
                
                if template_content is not None:
                    templates[template_name] = template_content
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"批量加载模板失败 {template_name}: {e}")
                error_count += 1
                
        logger.info(f"批量加载完成: 成功 {success_count} 个, 失败 {error_count} 个")
        
        return templates
        
    def reload_template(self, template_name: str) -> Optional[TemplateContent]:
        """
        强制重新加载指定模板
        
        Args:
            template_name: 模板名称
            
        Returns:
            Optional[TemplateContent]: 重新加载的模板内容
        """
        # 从缓存中移除
        template_path = self.scanner.find_template_by_name(template_name)
        if template_path:
            path_str = str(template_path)
            self._template_cache.pop(path_str, None)
            self._file_mtimes.pop(path_str, None)
            
        # 重新加载
        return self.load_template(template_name, use_cache=False)
        
    def reload_all_templates(self) -> Dict[str, TemplateContent]:
        """
        强制重新加载所有模板
        
        Returns:
            Dict[str, TemplateContent]: 重新加载的所有模板内容
        """
        # 清空缓存
        self.clear_cache()
        
        # 重新加载
        return self.load_all_templates(use_cache=False, force_refresh=True)
        
    def clear_cache(self):
        """清空所有缓存"""
        self._template_cache.clear()
        self._file_mtimes.clear()
        self._scan_cache = None
        self._scan_timestamp = 0
        
        logger.info("模板缓存已清空")
        
    def get_template_list(self, include_details: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """
        获取模板列表
        
        Args:
            include_details: 是否包含详细信息
            
        Returns:
            List: 模板列表
        """
        template_info_list = self.scan_templates()
        
        if include_details:
            return template_info_list
        else:
            return [info['name'] for info in template_info_list]
            
    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态信息
        
        Returns:
            Dict: 缓存状态信息
        """
        import time
        
        return {
            'cached_templates': len(self._template_cache),
            'cache_hit_rate': (
                self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses'])
                if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0
            ),
            'scan_cache_age': time.time() - self._scan_timestamp if self._scan_timestamp > 0 else 0,
            'stats': self.stats.copy(),
            'config': {
                'cache_ttl': self.cache_ttl,
                'auto_reload': self.auto_reload,
                'recursive_scan': self.recursive_scan
            }
        }
        
    def get_template_status(self, template_name: str) -> Dict[str, Any]:
        """
        获取指定模板的状态信息
        
        Args:
            template_name: 模板名称
            
        Returns:
            Dict: 模板状态信息
        """
        template_path = self.scanner.find_template_by_name(template_name)
        
        if template_path is None:
            return {'exists': False}
            
        path_str = str(template_path)
        file_info = self.scanner.reader.get_file_info(template_path)
        
        return {
            'exists': True,
            'path': template_path,
            'file_info': file_info,
            'is_cached': path_str in self._template_cache,
            'cache_mtime': self._file_mtimes.get(path_str),
            'needs_reload': self._needs_reload(template_path, file_info.get('modified', 0)),
            'template_name': template_name
        }


class TemplateWatcher:
    """模板文件监控器 - 监控文件变化并触发重新加载"""
    
    def __init__(self, template_loader: TemplateLoader):
        """
        初始化模板监控器
        
        Args:
            template_loader: 模板加载器实例
        """
        self.loader = template_loader
        self.template_directory = template_loader.template_directory
        
        # watchdog相关
        self.observer = None
        self.event_handler = None
        self.is_watching = False
        
        # 回调函数列表
        self.change_callbacks = []
        
        # 配置参数
        self.debounce_delay = 1.0  # 防抖延迟（秒）
        self.watch_recursive = True  # 是否递归监控
        
        # 事件统计
        self.event_stats = {
            'files_created': 0,
            'files_modified': 0,
            'files_deleted': 0,
            'files_moved': 0,
            'total_events': 0,
            'last_event_time': None
        }
        
    def add_change_callback(self, callback):
        """
        添加文件变化回调函数
        
        Args:
            callback: 回调函数，接收(event_type, template_name, file_path)参数
        """
        if callback not in self.change_callbacks:
            self.change_callbacks.append(callback)
            
    def remove_change_callback(self, callback):
        """
        移除文件变化回调函数
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self.change_callbacks:
            self.change_callbacks.remove(callback)
            
    def start_watching(self) -> bool:
        """
        开始监控文件变化
        
        Returns:
            bool: 是否启动成功
        """
        if self.is_watching:
            logger.warning("文件监控已经在运行")
            return True
            
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class TemplateEventHandler(FileSystemEventHandler):
                def __init__(self, watcher):
                    self.watcher = watcher
                    
                def on_modified(self, event):
                    if not event.is_directory:
                        self.watcher._handle_file_event('modified', event.src_path)
                        
                def on_created(self, event):
                    if not event.is_directory:
                        self.watcher._handle_file_event('created', event.src_path)
                        
                def on_deleted(self, event):
                    if not event.is_directory:
                        self.watcher._handle_file_event('deleted', event.src_path)
                        
                def on_moved(self, event):
                    if not event.is_directory:
                        self.watcher._handle_file_event('moved', event.dest_path, event.src_path)
            
            # 创建监控器
            self.observer = Observer()
            self.event_handler = TemplateEventHandler(self)
            
            # 开始监控
            self.observer.schedule(
                self.event_handler, 
                str(self.template_directory), 
                recursive=self.watch_recursive
            )
            
            self.observer.start()
            self.is_watching = True
            
            logger.info(f"开始监控模板目录: {self.template_directory}")
            return True
            
        except ImportError:
            logger.error("watchdog模块未安装，无法启动文件监控")
            return False
        except Exception as e:
            logger.error(f"启动文件监控失败: {e}")
            return False
            
    def stop_watching(self):
        """停止监控文件变化"""
        if not self.is_watching:
            return
            
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                
            self.observer = None
            self.event_handler = None
            self.is_watching = False
            
            logger.info("已停止文件监控")
            
        except Exception as e:
            logger.error(f"停止文件监控失败: {e}")
            
    def _handle_file_event(self, event_type: str, file_path: str, old_path: str = None):
        """
        处理文件事件
        
        Args:
            event_type: 事件类型
            file_path: 文件路径
            old_path: 旧路径（用于移动事件）
        """
        import time
        from pathlib import Path
        
        try:
            file_path = Path(file_path)
            
            # 只处理.md文件
            if file_path.suffix.lower() != '.md':
                return
                
            # 跳过README文件
            if file_path.name.lower() == 'readme.md':
                return
                
            # 更新统计
            self.event_stats['total_events'] += 1
            self.event_stats['last_event_time'] = time.time()
            
            if event_type == 'created':
                self.event_stats['files_created'] += 1
            elif event_type == 'modified':
                self.event_stats['files_modified'] += 1
            elif event_type == 'deleted':
                self.event_stats['files_deleted'] += 1
            elif event_type == 'moved':
                self.event_stats['files_moved'] += 1
                
            template_name = file_path.name
            
            logger.info(f"检测到模板文件{event_type}: {template_name}")
            
            # 处理不同类型的事件
            if event_type in ['modified', 'created']:
                # 重新加载模板
                self.loader.reload_template(template_name)
            elif event_type == 'deleted':
                # 从缓存中移除
                path_str = str(file_path)
                self.loader._template_cache.pop(path_str, None)
                self.loader._file_mtimes.pop(path_str, None)
            elif event_type == 'moved':
                # 处理文件移动
                if old_path:
                    old_name = Path(old_path).name
                    # 从缓存中移除旧路径
                    self.loader._template_cache.pop(str(old_path), None)
                    self.loader._file_mtimes.pop(str(old_path), None)
                    
                # 加载新路径的模板
                self.loader.reload_template(template_name)
                
            # 调用回调函数
            for callback in self.change_callbacks:
                try:
                    callback(event_type, template_name, file_path)
                except Exception as e:
                    logger.error(f"执行文件变化回调失败: {e}")
                    
        except Exception as e:
            logger.error(f"处理文件事件失败 {event_type} {file_path}: {e}")
            
    def get_watch_status(self) -> Dict[str, Any]:
        """
        获取监控状态
        
        Returns:
            Dict: 监控状态信息
        """
        return {
            'is_watching': self.is_watching,
            'watch_directory': str(self.template_directory),
            'watch_recursive': self.watch_recursive,
            'callback_count': len(self.change_callbacks),
            'debounce_delay': self.debounce_delay,
            'event_stats': self.event_stats.copy()
        } 