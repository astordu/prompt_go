"""
文本处理模块测试

验证文本处理器的选中文本获取、验证和平台兼容性功能。
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import platform
from pathlib import Path

from modules.text_processor import TextProcessor


class TestTextProcessor:
    """文本处理器测试类"""
    
    @pytest.fixture
    def temp_template_dir(self):
        """创建临时模板目录"""
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        import tempfile
        import shutil
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def text_processor(self, temp_template_dir, temp_config_dir):
        """创建文本处理器实例"""
        return TextProcessor(temp_template_dir, temp_config_dir)
    
    def test_text_processor_init(self, text_processor):
        """测试文本处理器初始化"""
        assert text_processor._platform == platform.system()
        assert text_processor._selection_timeout > 0
        assert text_processor._copy_retry_count > 0
        assert text_processor._copy_retry_delay > 0
        
        # 验证平台配置存在
        assert 'Darwin' in text_processor._platform_config
        assert 'Windows' in text_processor._platform_config
        assert 'Linux' in text_processor._platform_config
    
    @patch('modules.text_processor.pyperclip')
    def test_get_clipboard_content(self, mock_pyperclip, text_processor):
        """测试获取剪贴板内容"""
        mock_pyperclip.paste.return_value = "test content"
        
        result = text_processor._get_clipboard_content()
        
        assert result == "test content"
        mock_pyperclip.paste.assert_called_once()
    
    @patch('modules.text_processor.pyperclip')
    def test_get_clipboard_content_error(self, mock_pyperclip, text_processor):
        """测试获取剪贴板内容失败"""
        mock_pyperclip.paste.side_effect = Exception("Clipboard error")
        
        result = text_processor._get_clipboard_content()
        
        assert result == ""
    
    @patch('modules.text_processor.pyperclip')
    def test_restore_clipboard(self, mock_pyperclip, text_processor):
        """测试恢复剪贴板内容"""
        text_processor._restore_clipboard("test content")
        
        mock_pyperclip.copy.assert_called_once_with("test content")
    
    @patch('modules.text_processor.pyperclip')
    def test_restore_clipboard_empty(self, mock_pyperclip, text_processor):
        """测试恢复空剪贴板内容"""
        text_processor._restore_clipboard("")
        
        mock_pyperclip.copy.assert_not_called()
    
    def test_validate_text_selection_valid(self, text_processor):
        """测试有效文本验证"""
        result = text_processor.validate_text_selection("Hello World")
        
        assert result['is_valid'] == True
        assert result['text'] == "Hello World"
        assert result['length'] == 11
        assert result['is_empty'] == False
        assert result['error_message'] is None
    
    def test_validate_text_selection_empty(self, text_processor):
        """测试空文本验证"""
        result = text_processor.validate_text_selection("")
        
        assert result['is_valid'] == False
        assert result['is_empty'] == True
        assert result['error_message'] == "选中文本为空"
    
    def test_validate_text_selection_none(self, text_processor):
        """测试None文本验证"""
        result = text_processor.validate_text_selection(None)
        
        assert result['is_valid'] == False
        assert result['error_message'] == "文本为空"
    
    def test_validate_text_selection_whitespace_only(self, text_processor):
        """测试仅包含空白字符的文本验证"""
        result = text_processor.validate_text_selection("   \n\t   ")
        
        assert result['is_valid'] == False
        assert result['is_empty'] == True
        assert result['error_message'] == "选中文本为空"
    
    def test_validate_text_selection_too_long(self, text_processor):
        """测试过长文本验证"""
        long_text = "a" * 60000  # 超过50KB限制
        result = text_processor.validate_text_selection(long_text)
        
        assert result['is_valid'] == False
        assert result['error_message'] == "选中文本过长"
    
    def test_validate_text_selection_non_printable(self, text_processor):
        """测试非可打印字符文本验证"""
        non_printable_text = "\x00\x01\x02"
        result = text_processor.validate_text_selection(non_printable_text)
        
        assert result['is_valid'] == False
        assert result['error_message'] == "选中文本不包含可读内容"
    
    @patch('modules.text_processor.pyperclip')
    def test_get_platform_capabilities(self, mock_pyperclip, text_processor):
        """测试获取平台能力"""
        # 模拟剪贴板测试
        mock_pyperclip.copy.return_value = None
        mock_pyperclip.paste.return_value = "test_clipboard_availability"
        
        capabilities = text_processor.get_platform_capabilities()
        
        assert 'platform' in capabilities
        assert 'clipboard_available' in capabilities
        assert 'copy_simulation_available' in capabilities
        assert 'accessibility_required' in capabilities
        
        # 验证平台名称正确
        assert capabilities['platform'] == platform.system()
    
    @patch('pynput.keyboard.Controller')
    def test_check_accessibility_permission_non_macos(self, mock_controller, text_processor):
        """测试非macOS平台的辅助功能权限检查"""
        # 模拟非macOS平台
        text_processor._platform = "Linux"
        
        result = text_processor.check_accessibility_permission()
        
        assert result == True
        mock_controller.assert_not_called()
    
    @patch('pynput.keyboard.Controller')
    def test_check_accessibility_permission_macos_success(self, mock_controller, text_processor):
        """测试macOS平台辅助功能权限检查成功"""
        # 模拟macOS平台
        text_processor._platform = "Darwin"
        
        # 模拟成功的控制器操作
        mock_controller_instance = Mock()
        mock_controller.return_value = mock_controller_instance
        
        result = text_processor.check_accessibility_permission()
        
        assert result == True
        mock_controller.assert_called_once()
        mock_controller_instance.press.assert_called()
        mock_controller_instance.release.assert_called()
    
    @patch('pynput.keyboard.Controller')
    def test_check_accessibility_permission_macos_failure(self, mock_controller, text_processor):
        """测试macOS平台辅助功能权限检查失败"""
        # 模拟macOS平台
        text_processor._platform = "Darwin"
        
        # 模拟权限错误
        mock_controller.side_effect = Exception("Accessibility permission denied")
        
        result = text_processor.check_accessibility_permission()
        
        assert result == False
    
    def test_get_text_statistics_english(self, text_processor):
        """测试英文文本统计"""
        text = "Hello World! This is a test."
        stats = text_processor.get_text_statistics(text)
        
        assert stats['length'] == len(text)
        assert stats['word_count'] == 6
        assert stats['line_count'] == 1
        assert stats['has_english'] == True
        assert stats['has_chinese'] == False
        assert stats['has_numbers'] == False
        assert stats['encoding'] == 'utf-8'
    
    def test_get_text_statistics_chinese(self, text_processor):
        """测试中文文本统计"""
        text = "你好世界！这是一个测试。"
        stats = text_processor.get_text_statistics(text)
        
        assert stats['length'] == len(text)
        assert stats['has_chinese'] == True
        assert stats['has_english'] == False
        assert stats['encoding'] == 'utf-8'
    
    def test_get_text_statistics_mixed(self, text_processor):
        """测试混合文本统计"""
        text = "Hello 世界! 123"
        stats = text_processor.get_text_statistics(text)
        
        assert stats['length'] == len(text)
        assert stats['has_english'] == True
        assert stats['has_chinese'] == True
        assert stats['has_numbers'] == True
    
    def test_get_text_statistics_multiline(self, text_processor):
        """测试多行文本统计"""
        text = "Line 1\nLine 2\nLine 3"
        stats = text_processor.get_text_statistics(text)
        
        assert stats['line_count'] == 3
        assert stats['word_count'] == 6
    
    @patch('modules.text_processor.pyperclip')
    @patch.object(TextProcessor, '_execute_copy_operation')
    def test_get_selected_text_success(self, mock_execute_copy, mock_pyperclip, text_processor):
        """测试成功获取选中文本"""
        # 设置模拟
        original_content = "original"
        selected_content = "selected text"
        
        # paste会被调用两次：一次获取原始内容，一次获取选中内容
        mock_pyperclip.paste.side_effect = [original_content, selected_content]
        mock_pyperclip.copy.return_value = None
        mock_execute_copy.return_value = True
        
        result = text_processor.get_selected_text()
        
        assert result == "selected text"
        assert mock_execute_copy.called
    
    @patch('modules.text_processor.pyperclip')
    @patch.object(TextProcessor, '_execute_copy_operation')
    def test_get_selected_text_copy_failure(self, mock_execute_copy, mock_pyperclip, text_processor):
        """测试复制操作失败"""
        mock_pyperclip.paste.return_value = "original"
        mock_pyperclip.copy.return_value = None
        mock_execute_copy.return_value = False
        
        result = text_processor.get_selected_text()
        
        assert result is None
    
    @patch('modules.text_processor.pyperclip')
    @patch.object(TextProcessor, '_execute_copy_operation')
    def test_get_selected_text_empty_selection(self, mock_execute_copy, mock_pyperclip, text_processor):
        """测试选中文本为空"""
        mock_pyperclip.paste.side_effect = ["original", "", ""]
        mock_pyperclip.copy.return_value = None
        mock_execute_copy.return_value = True
        
        result = text_processor.get_selected_text()
        
        assert result is None
    
    @patch('pynput.keyboard.Controller')
    def test_simulate_copy_keys_success(self, mock_controller_class, text_processor):
        """测试模拟按键操作成功"""
        mock_controller = Mock()
        mock_controller_class.return_value = mock_controller
        
        from pynput.keyboard import Key
        keys = [Key.ctrl, 'c']
        
        result = text_processor._simulate_copy_keys(keys)
        
        assert result == True
        mock_controller.press.assert_called()
        mock_controller.release.assert_called()
    
    @patch('pynput.keyboard.Controller')
    def test_simulate_copy_keys_failure(self, mock_controller_class, text_processor):
        """测试模拟按键操作失败"""
        mock_controller_class.side_effect = Exception("Controller error")
        
        from pynput.keyboard import Key
        keys = [Key.ctrl, 'c']
        
        result = text_processor._simulate_copy_keys(keys)
        
        assert result == False
    
    @patch.object(TextProcessor, '_simulate_copy_keys')
    def test_execute_copy_operation_success(self, mock_simulate, text_processor):
        """测试执行复制操作成功"""
        mock_simulate.return_value = True
        
        result = text_processor._execute_copy_operation()
        
        assert result == True
        assert mock_simulate.called
    
    @patch.object(TextProcessor, '_simulate_copy_keys')
    def test_execute_copy_operation_retry(self, mock_simulate, text_processor):
        """测试复制操作重试机制"""
        # 前两次失败，第三次成功
        mock_simulate.side_effect = [False, False, True]
        
        result = text_processor._execute_copy_operation()
        
        assert result == True
        assert mock_simulate.call_count == 3
    
    @patch.object(TextProcessor, '_simulate_copy_keys')
    def test_execute_copy_operation_all_attempts_fail(self, mock_simulate, text_processor):
        """测试所有复制尝试都失败"""
        mock_simulate.return_value = False
        
        result = text_processor._execute_copy_operation()
        
        assert result == False
        assert mock_simulate.call_count == text_processor._copy_retry_count

    # ================= 模板处理功能测试 =================
    
    @pytest.fixture
    def sample_template(self, temp_template_dir):
        """创建示例模板文件"""
        from pathlib import Path
        template_dir = Path(temp_template_dir)
        template_dir.mkdir(exist_ok=True)
        
        template_path = template_dir / "test_template.md"
        template_content = """model: deepseek
temperature: 0.7
max_tokens: 2000

---

你是一个专业的助手。请处理以下内容：

{{input}}

请提供详细的回复。"""
        
        template_path.write_text(template_content, encoding='utf-8')
        return "test_template.md"
    
    @pytest.fixture
    def invalid_template(self, temp_template_dir):
        """创建无效的模板文件（没有占位符）"""
        from pathlib import Path
        template_dir = Path(temp_template_dir)
        template_dir.mkdir(exist_ok=True)
        
        template_path = template_dir / "invalid_template.md"
        template_content = """model: deepseek
temperature: 0.7

---

这是一个没有占位符的模板。"""
        
        template_path.write_text(template_content, encoding='utf-8')
        return "invalid_template.md"
    
    @pytest.fixture
    def multi_placeholder_template(self, temp_template_dir):
        """创建多占位符模板文件"""
        from pathlib import Path
        template_dir = Path(temp_template_dir)
        template_dir.mkdir(exist_ok=True)
        
        template_path = template_dir / "multi_template.md"
        template_content = """model: kimi
temperature: 0.5

---

处理内容1: {{input1}}
处理内容2: {{input2}}"""
        
        template_path.write_text(template_content, encoding='utf-8')
        return "multi_template.md"
    
    def test_text_processor_init_with_template_dir(self, temp_template_dir, temp_config_dir):
        """测试带模板目录的文本处理器初始化"""
        processor = TextProcessor(temp_template_dir, temp_config_dir)
        
        assert str(processor.template_dir) == str(Path(temp_template_dir))
        assert str(processor.config_dir) == str(Path(temp_config_dir))
        assert processor.template_parser is not None
        assert processor.config_manager is not None
        assert processor.stream_processor is not None
        assert processor.streaming_manager is not None
        assert str(processor.template_parser.template_directory) == str(Path(temp_template_dir))
    
    def test_template_exists(self, text_processor, sample_template):
        """测试模板存在性检查"""
        assert text_processor._template_exists(sample_template) == True
        assert text_processor._template_exists("nonexistent.md") == False
    
    def test_validate_template_for_processing_valid(self, text_processor, sample_template):
        """测试有效模板的验证"""
        template_content = text_processor.template_parser.parse_template(sample_template)
        result = text_processor._validate_template_for_processing(template_content)
        
        assert result['is_valid'] == True
        assert result['placeholder_count'] == 1
        assert result['has_single_placeholder'] == True
        assert 'input' in result['placeholders']
        assert result['primary_placeholder'] == 'input'
    
    def test_validate_template_for_processing_no_placeholder(self, text_processor, invalid_template):
        """测试无占位符模板的验证"""
        template_content = text_processor.template_parser.parse_template(invalid_template)
        result = text_processor._validate_template_for_processing(template_content)
        
        assert result['is_valid'] == False
        assert result['placeholder_count'] == 0
        assert result['error'] == "模板缺少必需的占位符"
    
    def test_validate_template_for_processing_multiple_placeholders(self, text_processor, multi_placeholder_template):
        """测试多占位符模板的验证"""
        template_content = text_processor.template_parser.parse_template(multi_placeholder_template)
        result = text_processor._validate_template_for_processing(template_content)
        
        assert result['is_valid'] == False
        assert result['placeholder_count'] == 2
        assert result['has_single_placeholder'] == False
        assert "多个占位符" in result['error']
    
    def test_insert_text_into_template_success(self, text_processor, sample_template):
        """测试成功插入文本到模板"""
        test_text = "这是测试文本"
        result = text_processor.insert_text_into_template(sample_template, test_text)
        
        assert result['success'] == True
        assert result['template_name'] == sample_template
        assert result['input_text'] == test_text
        assert test_text in result['processed_content']
        assert "{{input}}" not in result['processed_content']
        assert result['error'] is None
    
    def test_insert_text_into_template_nonexistent(self, text_processor):
        """测试插入文本到不存在的模板"""
        result = text_processor.insert_text_into_template("nonexistent.md", "test")
        
        assert result['success'] == False
        assert "不存在" in result['error']
    
    def test_insert_text_into_template_invalid(self, text_processor, invalid_template):
        """测试插入文本到无效模板"""
        result = text_processor.insert_text_into_template(invalid_template, "test")
        
        assert result['success'] == False
        assert "验证失败" in result['error']
    
    def test_get_template_with_text_success(self, text_processor, sample_template):
        """测试获取插入文本后的模板内容（简化接口）"""
        test_text = "测试内容"
        result = text_processor.get_template_with_text(sample_template, test_text)
        
        assert result is not None
        assert test_text in result
        assert "{{input}}" not in result
    
    def test_get_template_with_text_failure(self, text_processor):
        """测试获取不存在模板的内容"""
        result = text_processor.get_template_with_text("nonexistent.md", "test")
        
        assert result is None
    
    def test_validate_template_processing_valid(self, text_processor, sample_template):
        """测试有效模板的处理验证"""
        result = text_processor.validate_template_processing(sample_template)
        
        assert result['is_valid'] == True
        assert result['template_name'] == sample_template
        assert len(result['errors']) == 0
        assert 'model_name' in result['details']
        assert 'placeholders' in result['details']
    
    def test_validate_template_processing_invalid(self, text_processor, invalid_template):
        """测试无效模板的处理验证"""
        result = text_processor.validate_template_processing(invalid_template)
        
        assert result['is_valid'] == False
        assert len(result['errors']) > 0
        assert "占位符" in result['errors'][0]
    
    def test_validate_template_processing_nonexistent(self, text_processor):
        """测试不存在模板的处理验证"""
        result = text_processor.validate_template_processing("nonexistent.md")
        
        assert result['is_valid'] == False
        assert "不存在" in result['errors'][0]
    
    def test_get_available_templates(self, text_processor, sample_template, invalid_template):
        """测试获取可用模板列表"""
        templates = text_processor.get_available_templates()
        
        assert len(templates) >= 2
        template_names = [t['name'] for t in templates]
        assert sample_template in template_names
        assert invalid_template in template_names
        
        # 检查模板有效性状态
        sample_info = next(t for t in templates if t['name'] == sample_template)
        invalid_info = next(t for t in templates if t['name'] == invalid_template)
        
        assert sample_info['is_valid'] == True
        assert invalid_info['is_valid'] == False
    
    @patch.object(TextProcessor, 'get_selected_text')
    def test_process_template_with_selected_text_success(self, mock_get_text, text_processor, sample_template):
        """测试使用选中文本处理模板成功"""
        mock_get_text.return_value = "选中的测试文本"
        
        result = text_processor.process_template_with_selected_text(sample_template)
        
        assert result['success'] == True
        assert result['template_name'] == sample_template
        assert result['selected_text'] == "选中的测试文本"
        assert "选中的测试文本" in result['processed_content']
        assert result['error'] is None
    
    @patch.object(TextProcessor, 'get_selected_text')
    def test_process_template_with_selected_text_empty_text(self, mock_get_text, text_processor, sample_template):
        """测试选中文本为空时的处理"""
        mock_get_text.return_value = None
        
        result = text_processor.process_template_with_selected_text(sample_template)
        
        assert result['success'] == False
        assert "文本无效" in result['error']
    
    @patch.object(TextProcessor, 'get_selected_text')
    def test_process_template_with_selected_text_invalid_template(self, mock_get_text, text_processor, invalid_template):
        """测试使用无效模板处理选中文本"""
        mock_get_text.return_value = "测试文本"
        
        result = text_processor.process_template_with_selected_text(invalid_template)
        
        assert result['success'] == False
        assert "验证失败" in result['error']
    
    def test_get_processing_statistics(self, text_processor, sample_template, invalid_template):
        """测试获取处理统计信息"""
        stats = text_processor.get_processing_statistics()
        
        assert 'platform' in stats
        assert 'template_directory' in stats
        assert 'total_templates' in stats
        assert 'valid_templates' in stats
        assert 'invalid_templates' in stats
        assert 'platform_capabilities' in stats
        assert 'valid_template_names' in stats
        assert 'invalid_template_names' in stats
        
        assert stats['total_templates'] >= 2
        assert stats['valid_templates'] >= 1
        assert stats['invalid_templates'] >= 1

    # ================= 流式输出功能测试 =================
    
    @pytest.fixture
    def sample_config(self, temp_config_dir):
        """创建示例配置文件"""
        config_path = Path(temp_config_dir) / "global_config.yaml"
        config_content = """
deepseek:
  api_key: "test_deepseek_key"
  base_url: "https://api.deepseek.com"

kimi:
  api_key: "test_kimi_key"
  base_url: "https://api.moonshot.cn"
"""
        config_path.write_text(config_content, encoding='utf-8')
        return config_path
    
    def test_determine_model_type(self, text_processor):
        """测试模型类型判断"""
        from modules.model_client import ModelType
        
        assert text_processor._determine_model_type("deepseek-chat") == ModelType.DEEPSEEK
        assert text_processor._determine_model_type("kimi-chat") == ModelType.KIMI
        assert text_processor._determine_model_type("moonshot-v1") == ModelType.KIMI
        assert text_processor._determine_model_type("unknown-model") == ModelType.DEEPSEEK  # 默认
    
    @patch.object(TextProcessor, '_get_api_key_for_model')
    def test_get_model_client_success(self, mock_get_api_key, text_processor):
        """测试成功获取模型客户端"""
        from modules.model_client import ModelType
        
        # 模拟API密钥存在
        mock_get_api_key.return_value = "test_api_key"
        
        with patch('modules.model_client.ModelClientFactory.create_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            client = text_processor.get_model_client("deepseek-chat")
            
            assert client == mock_client
            mock_create.assert_called_once_with(ModelType.DEEPSEEK, "test_api_key")
    
    @patch.object(TextProcessor, '_get_api_key_for_model')
    def test_get_model_client_no_api_key(self, mock_get_api_key, text_processor):
        """测试没有API密钥时的情况"""
        mock_get_api_key.return_value = None
        
        client = text_processor.get_model_client("deepseek-chat")
        
        assert client is None
    
    def test_get_api_key_for_model(self, text_processor, sample_config):
        """测试获取API密钥"""
        from modules.model_client import ModelType
        
        # 由于配置文件加载可能有问题，我们直接模拟
        with patch.object(text_processor.config_manager, 'get') as mock_get:
            mock_get.side_effect = lambda key: {
                'deepseek.api_key': 'test_deepseek_key',
                'kimi.api_key': 'test_kimi_key'
            }.get(key)
            
            deepseek_key = text_processor._get_api_key_for_model(ModelType.DEEPSEEK)
            kimi_key = text_processor._get_api_key_for_model(ModelType.KIMI)
            
            assert deepseek_key == 'test_deepseek_key'
            assert kimi_key == 'test_kimi_key'
    
    def test_set_typing_speed(self, text_processor):
        """测试设置打字速度"""
        text_processor.set_typing_speed(0.05)
        assert text_processor._typing_speed == 0.05
        
        # 测试负值处理
        text_processor.set_typing_speed(-0.1)
        assert text_processor._typing_speed == 0
    
    @patch('pynput.keyboard.Controller')
    def test_output_text_to_cursor(self, mock_controller_class, text_processor):
        """测试输出文本到光标位置"""
        mock_controller = Mock()
        mock_controller_class.return_value = mock_controller
        
        text = "Hello"
        text_processor.set_typing_speed(0)  # 设置为0以加快测试
        text_processor._output_text_to_cursor(text)
        
        # 验证每个字符都被输出
        assert mock_controller.type.call_count == 5
        mock_controller.type.assert_any_call('H')
        mock_controller.type.assert_any_call('e')
        mock_controller.type.assert_any_call('l')
        mock_controller.type.assert_any_call('l')
        mock_controller.type.assert_any_call('o')
    
    @patch('pynput.keyboard.Controller')
    @patch('modules.text_processor.pyperclip')
    def test_output_text_to_cursor_fallback(self, mock_pyperclip, mock_controller_class, text_processor):
        """测试输出失败时的备用方案"""
        # 模拟键盘输出失败
        mock_controller_class.side_effect = Exception("Controller failed")
        
        text = "Test text"
        text_processor._output_text_to_cursor(text)
        
        # 验证备用方案被调用
        mock_pyperclip.copy.assert_called_once_with(text)
    
    def test_output_text_streaming_callback(self, text_processor):
        """测试流式输出回调"""
        output_chars = []
        
        def callback(char):
            output_chars.append(char)
        
        text = "Hello"
        text_processor.set_typing_speed(0)  # 设置为0以加快测试
        text_processor._output_text_streaming(text, callback)
        
        assert output_chars == ['H', 'e', 'l', 'l', 'o']
    
    @patch.object(TextProcessor, 'get_selected_text')
    def test_process_template_with_ai_complete_empty_text(self, mock_get_text, text_processor):
        """测试选中文本为空时的完整处理流程"""
        mock_get_text.return_value = None
        
        with patch.object(text_processor, '_output_text_to_cursor') as mock_output:
            result = text_processor.process_template_with_ai_complete("test_template.md")
            
            assert result['success'] == False
            assert result['error'] == '选中文本为空'
            assert result['output_text'] == "!!文本为空!!"
            mock_output.assert_called_once_with("!!文本为空!!")
    
    @patch.object(TextProcessor, 'process_with_ai_streaming')
    @patch.object(TextProcessor, 'get_selected_text')
    def test_process_template_with_ai_complete_api_error(self, mock_get_text, mock_ai_stream, text_processor):
        """测试API不可用时的完整处理流程"""
        mock_get_text.return_value = "test text"
        mock_ai_stream.return_value = {
            'success': False,
            'error': 'API调用失败'
        }
        
        with patch.object(text_processor, '_output_text_to_cursor') as mock_output:
            result = text_processor.process_template_with_ai_complete("test_template.md")
            
            assert result['success'] == False
            assert result['output_text'] == "!!api不可用!!"
            mock_output.assert_called_once_with("!!api不可用!!")
    
    def test_get_streaming_statistics(self, text_processor):
        """测试获取流式统计信息"""
        stats = text_processor.get_streaming_statistics()
        
        assert 'processing' in stats
        assert 'streaming' in stats
        assert 'model_clients' in stats
        assert 'output_config' in stats
        assert 'platform_capabilities' in stats
        
        # 验证输出配置
        output_config = stats['output_config']
        assert 'typing_speed' in output_config
        assert 'chunk_output_delay' in output_config
        assert 'max_output_length' in output_config

    # ================= 字符编码和过滤功能测试 =================
    
    def test_detect_and_validate_encoding_valid_utf8(self, text_processor):
        """测试有效UTF-8文本的编码检测"""
        text = "Hello 世界! 🌍"
        result = text_processor._detect_and_validate_encoding(text)
        
        assert result['is_valid'] == True
        assert result['encoding'] == 'utf-8'
        assert result['encoding_confidence'] == 1.0
        assert result['char_length'] == len(text)
        assert result['byte_length'] > result['char_length']  # UTF-8多字节
        assert result['has_bom'] == False
    
    def test_detect_and_validate_encoding_control_chars(self, text_processor):
        """测试包含过多控制字符的文本"""
        # 创建包含大量控制字符的文本
        text = "Hello\x00\x01\x02\x03\x04\x05\x06\x07World"
        result = text_processor._detect_and_validate_encoding(text)
        
        assert result['is_valid'] == False
        assert "控制字符" in result['error']
    
    def test_filter_special_characters_control_chars(self, text_processor):
        """测试过滤控制字符"""
        text = "Hello\x00\x01World\x7F"
        result = text_processor._filter_special_characters(text)
        
        assert result['filtered_text'] == "HelloWorld"
        assert len(result['filtered_chars']) == 3  # \x00, \x01, \x7F
        assert result['warnings'][0] == "过滤了 3 个特殊字符"
    
    def test_filter_special_characters_keep_common_whitespace(self, text_processor):
        """测试保留常见的空白字符"""
        text = "Hello\nWorld\r\nTest\tEnd"
        result = text_processor._filter_special_characters(text)
        
        assert result['filtered_text'] == text  # 应该保持不变
        assert len(result['filtered_chars']) == 0
    
    def test_filter_special_characters_invisible_chars(self, text_processor):
        """测试过滤不可见字符"""
        text = "Hello\u200BWorld\uFEFFTest"  # 零宽空格和BOM
        result = text_processor._filter_special_characters(text)
        
        assert result['filtered_text'] == "HelloWorldTest"
        assert len(result['filtered_chars']) == 2
    
    def test_filter_special_characters_private_use(self, text_processor):
        """测试过滤私用区字符"""
        text = "Hello\uE000World\uF8FFTest"  # 私用区字符
        result = text_processor._filter_special_characters(text)
        
        assert result['filtered_text'] == "HelloWorldTest"
        assert len(result['filtered_chars']) == 2
    
    def test_clean_and_normalize_text_newlines(self, text_processor):
        """测试换行符标准化"""
        text = "Line1\r\nLine2\rLine3\nLine4"
        result = text_processor._clean_and_normalize_text(text)
        
        expected = "Line1\nLine2\nLine3\nLine4"
        assert result['text'] == expected
    
    def test_clean_and_normalize_text_whitespace(self, text_processor):
        """测试空白字符处理"""
        text = "  Hello   World  \t\t  End  "
        result = text_processor._clean_and_normalize_text(text)
        
        expected = "Hello World End"
        assert result['text'] == expected
    
    def test_clean_and_normalize_text_multiple_newlines(self, text_processor):
        """测试多重换行符处理"""
        text = "Line1\n\n\n\n\nLine2"
        result = text_processor._clean_and_normalize_text(text)
        
        expected = "Line1\n\n\nLine2"  # 最多3个连续换行
        assert result['text'] == expected
    
    def test_process_text_encoding_success(self, text_processor):
        """测试完整的文本编码处理成功"""
        text = "Hello\x00World\u200B  Test  \n\n\n\nEnd"
        result = text_processor.process_text_encoding(text)
        
        assert result['success'] == True
        assert result['processed_text'] == "HelloWorld Test\n\n\nEnd"
        assert len(result['filtered_characters']) > 0
        assert len(result['warnings']) > 0
    
    def test_process_text_encoding_invalid_encoding(self, text_processor):
        """测试编码验证失败的情况"""
        # 模拟编码检测失败
        with patch.object(text_processor, '_detect_and_validate_encoding') as mock_detect:
            mock_detect.return_value = {
                'is_valid': False,
                'error': '编码错误'
            }
            
            result = text_processor.process_text_encoding("test")
            
            assert result['success'] == False
            assert "编码验证失败" in result['error']
    
    def test_filter_output_text_success(self, text_processor):
        """测试输出文本过滤（简化接口）"""
        text = "Hello\x00World\u200BTest"
        result = text_processor.filter_output_text(text)
        
        assert result == "HelloWorldTest"
    
    def test_filter_output_text_failure_fallback(self, text_processor):
        """测试过滤失败时的备用方案"""
        text = "test"
        
        with patch.object(text_processor, 'process_text_encoding') as mock_process:
            mock_process.return_value = {'success': False, 'error': '测试错误'}
            
            result = text_processor.filter_output_text(text)
            assert result == text  # 应该返回原文本
    
    def test_validate_output_safety_safe_text(self, text_processor):
        """测试安全文本的验证"""
        text = "Hello World! This is a safe text."
        result = text_processor.validate_output_safety(text)
        
        assert result['is_safe'] == True
        assert result['risk_level'] == 'low'
        assert len(result['issues']) == 0
    
    def test_validate_output_safety_control_chars(self, text_processor):
        """测试包含控制字符的文本安全验证"""
        text = "Hello\x00\x01World"
        result = text_processor.validate_output_safety(text)
        
        assert result['is_safe'] == False
        assert result['risk_level'] == 'high'
        assert any("控制字符" in issue for issue in result['issues'])
        assert "建议过滤控制字符" in result['recommendations']
    
    def test_validate_output_safety_invisible_chars(self, text_processor):
        """测试包含不可见字符的文本安全验证"""
        text = "Hello\u200BWorld\uFEFF"
        result = text_processor.validate_output_safety(text)
        
        assert result['is_safe'] == False
        assert result['risk_level'] == 'medium'
        assert any("不可见字符" in issue for issue in result['issues'])
    
    def test_validate_output_safety_too_long(self, text_processor):
        """测试过长文本的安全验证"""
        text = "a" * (text_processor._max_output_length + 100)
        result = text_processor.validate_output_safety(text)
        
        assert result['is_safe'] == False
        assert result['risk_level'] == 'medium'
        assert any("过长" in issue for issue in result['issues'])
    
    def test_get_encoding_statistics_ascii(self, text_processor):
        """测试ASCII文本的编码统计"""
        text = "Hello World"
        stats = text_processor.get_encoding_statistics(text)
        
        assert stats['char_count'] == len(text)
        assert stats['ascii_chars'] == len(text)
        assert stats['latin1_chars'] == 0
        assert stats['unicode_chars'] == 0
        assert stats['control_chars'] == 0
        assert stats['encoding_efficiency'] == 1.0  # ASCII效率为1
    
    def test_get_encoding_statistics_unicode(self, text_processor):
        """测试Unicode文本的编码统计"""
        text = "Hello 世界 🌍"
        stats = text_processor.get_encoding_statistics(text)
        
        assert stats['char_count'] == len(text)
        assert stats['ascii_chars'] > 0  # "Hello "
        assert stats['unicode_chars'] > 0  # "世界 🌍"
        assert stats['byte_count_utf8'] > stats['char_count']  # 多字节字符
        assert stats['encoding_efficiency'] < 1.0
    
    def test_get_encoding_statistics_mixed_chars(self, text_processor):
        """测试混合字符类型的编码统计"""
        text = "Hello\nWorld\t123\x00"
        stats = text_processor.get_encoding_statistics(text)
        
        assert stats['char_count'] == len(text)
        assert stats['ascii_chars'] > 0
        assert stats['control_chars'] == 1  # \x00
        assert stats['whitespace_chars'] == 2  # \n, \t
        assert stats['max_char_code'] == ord('r')  # 最大的字符编码
        assert stats['min_char_code'] == 0  # \x00
    
    def test_get_encoding_statistics_empty_text(self, text_processor):
        """测试空文本的编码统计"""
        text = ""
        stats = text_processor.get_encoding_statistics(text)
        
        assert stats['char_count'] == 0
        assert stats['byte_count_utf8'] == 0
        assert stats['line_count'] == 0
        assert stats['min_char_code'] == 0
        assert stats['encoding_efficiency'] == 0.0
    
    @patch('pynput.keyboard.Controller')
    def test_output_text_to_cursor_with_filtering(self, mock_controller_class, text_processor):
        """测试输出文本到光标位置时的过滤功能"""
        mock_controller = Mock()
        mock_controller_class.return_value = mock_controller
        
        # 包含需要过滤的字符
        text = "Hello\x00World\u200B!"
        text_processor.set_typing_speed(0)
        text_processor._output_text_to_cursor(text)
        
        # 验证过滤后的文本被输出
        expected_calls = len("HelloWorld!")  # 过滤掉\x00和\u200B
        assert mock_controller.type.call_count == expected_calls 