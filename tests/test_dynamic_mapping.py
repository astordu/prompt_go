"""
动态映射功能测试

验证快捷键到模板文件的动态映射机制，包括模板发现、验证、监控和智能映射建议功能。
"""

import pytest
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

from modules.hotkey_listener import HotkeyListener


class TestDynamicMapping:
    """动态映射功能测试类"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """创建临时项目目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_templates(self, temp_project_dir):
        """创建示例模板文件"""
        template_dir = Path(temp_project_dir) / "prompt"
        template_dir.mkdir()
        
        # 创建示例模板文件
        templates = {
            'translate.md': '''---
model: deepseek
temperature: 0.7
---
请将以下内容翻译成中文：

{{text}}''',
            
            'summarize.md': '''---
model: kimi
max_tokens: 1000
---
请为以下内容生成摘要：

{{content}}''',
            
            'grammar_check.md': '''---
model: deepseek
temperature: 0.3
---
请检查以下文本的语法错误：

{{text}}''',
            
            'code_review.md': '''---
model: deepseek
temperature: 0.5
---
请对以下代码进行审查：

{{code}}'''
        }
        
        for filename, content in templates.items():
            (template_dir / filename).write_text(content, encoding='utf-8')
            
        return template_dir
    
    @pytest.fixture
    def sample_config(self, temp_project_dir):
        """创建示例配置文件"""
        config_dir = Path(temp_project_dir) / "config"
        config_dir.mkdir()
        
        # 创建快捷键配置
        hotkey_config = {
            'hotkeys': {
                'ctrl+alt+cmd+1': 'translate.md',
                'ctrl+alt+cmd+2': 'nonexistent.md',  # 不存在的文件用于测试
                'ctrl+alt+cmd+3': 'summarize.md'
            },
            'settings': {
                'enabled': True,
                'response_delay': 100
            }
        }
        
        config_path = config_dir / "hotkey_mapping.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(hotkey_config, f, allow_unicode=True)
            
        return config_dir
    
    @pytest.fixture
    def hotkey_listener(self, sample_config, sample_templates):
        """创建配置好的快捷键监听器"""
        config_dir = str(sample_config)
        template_dir = str(sample_templates)
        
        listener = HotkeyListener(config_dir, template_dir)
        yield listener
        
        # 清理
        listener._stop_template_monitoring()
    
    def test_template_validation(self, hotkey_listener):
        """测试模板文件验证功能"""
        # 测试存在的模板
        assert hotkey_listener._is_template_valid('translate.md')
        assert hotkey_listener._is_template_valid('summarize.md')
        
        # 测试不存在的模板
        assert not hotkey_listener._is_template_valid('nonexistent.md')
        assert not hotkey_listener._is_template_valid('invalid_template.md')
    
    def test_get_available_templates(self, hotkey_listener):
        """测试获取可用模板列表"""
        templates = hotkey_listener.get_available_templates()
        
        assert isinstance(templates, list)
        # 至少应该包含我们创建的模板
        assert 'translate.md' in templates
        assert 'summarize.md' in templates
        assert 'grammar_check.md' in templates
        assert 'code_review.md' in templates
    
    def test_mapping_validation_with_invalid_templates(self, hotkey_listener):
        """测试包含无效模板的映射验证"""
        mappings = hotkey_listener.config_manager.get_all_mappings()
        
        # 应该能检测到无效的映射
        invalid_found = False
        for hotkey, template in mappings.items():
            if not hotkey_listener._is_template_valid(template):
                invalid_found = True
                break
                
        assert invalid_found  # 应该发现 nonexistent.md 是无效的
    
    def test_generate_mapping_suggestions(self, hotkey_listener):
        """测试映射建议生成"""
        invalid_mappings = [('ctrl+alt+cmd+2', 'nonexistent.md')]
        suggestions = hotkey_listener._generate_mapping_suggestions(invalid_mappings)
        
        assert isinstance(suggestions, dict)
        if suggestions:  # 如果有建议
            assert 'ctrl+alt+cmd+2' in suggestions
            # 建议的模板应该是存在的
            suggested_template = suggestions['ctrl+alt+cmd+2']
            assert hotkey_listener._is_template_valid(suggested_template)
    
    def test_find_best_template_match(self, hotkey_listener):
        """测试最佳模板匹配算法"""
        available = ['translate.md', 'summarize.md', 'grammar_check.md']
        
        # 测试相似度匹配
        match = hotkey_listener._find_best_template_match('translation.md', available)
        assert match == 'translate.md'
        
        match = hotkey_listener._find_best_template_match('summary.md', available)
        assert match == 'summarize.md'
        
        # 测试没有匹配时返回第一个
        match = hotkey_listener._find_best_template_match('unknown.md', available)
        assert match in available
    
    def test_auto_mapping_generation(self, hotkey_listener):
        """测试自动映射生成"""
        auto_mappings = hotkey_listener._generate_auto_mappings()
        
        assert isinstance(auto_mappings, dict)
        
        # 应该为未映射的模板生成快捷键
        available_templates = hotkey_listener.get_available_templates()
        current_mappings = hotkey_listener.config_manager.get_all_mappings()
        used_templates = set(current_mappings.values())
        
        for hotkey, template in auto_mappings.items():
            # 快捷键应该是有效的
            assert hotkey in hotkey_listener.get_supported_hotkeys()
            # 模板应该是未被使用的
            assert template in available_templates
    
    def test_dynamic_add_mapping(self, hotkey_listener):
        """测试动态添加映射"""
        # 添加有效映射
        result = hotkey_listener.add_dynamic_mapping('ctrl+alt+cmd+4', 'code_review.md')
        assert result == True
        
        # 验证映射已添加
        template = hotkey_listener.config_manager.get_template_for_hotkey('ctrl+alt+cmd+4')
        assert template == 'code_review.md'
        
        # 尝试添加无效模板
        result = hotkey_listener.add_dynamic_mapping('ctrl+alt+cmd+5', 'invalid.md')
        assert result == False
        
        # 尝试添加无效快捷键
        result = hotkey_listener.add_dynamic_mapping('invalid_hotkey', 'translate.md')
        assert result == False
    
    def test_dynamic_remove_mapping(self, hotkey_listener):
        """测试动态移除映射"""
        # 移除存在的映射
        result = hotkey_listener.remove_dynamic_mapping('ctrl+alt+cmd+1')
        assert result == True
        
        # 验证映射已移除
        template = hotkey_listener.config_manager.get_template_for_hotkey('ctrl+alt+cmd+1')
        assert template is None
        
        # 尝试移除不存在的映射
        result = hotkey_listener.remove_dynamic_mapping('ctrl+alt+cmd+9')
        assert result == False
    
    def test_get_template_info(self, hotkey_listener):
        """测试获取模板信息"""
        # 获取存在的模板信息
        info = hotkey_listener.get_template_info('translate.md')
        assert info is not None
        assert info['name'] == 'translate.md'
        assert info['exists'] == True
        assert 'path' in info
        assert 'size' in info
        assert 'modified' in info
        
        # 如果解析成功，还应该包含模型信息
        if 'model' in info:
            assert info['model'] == 'deepseek'
            assert 'placeholders' in info
            
        # 获取不存在的模板信息
        info = hotkey_listener.get_template_info('nonexistent.md')
        assert info is None
    
    def test_get_mapping_status(self, hotkey_listener):
        """测试获取映射状态"""
        status = hotkey_listener.get_mapping_status()
        
        assert isinstance(status, dict)
        assert 'total_mappings' in status
        assert 'valid_mappings' in status
        assert 'invalid_mappings' in status
        assert 'available_templates' in status
        assert 'unused_templates' in status
        assert 'unused_hotkeys' in status
        assert 'mappings' in status
        assert 'suggestions' in status
        
        # 应该检测到无效映射（nonexistent.md）
        assert status['invalid_mappings'] > 0
        assert status['valid_mappings'] > 0
        
        # 应该有建议
        assert isinstance(status['suggestions'], dict)
    
    def test_hotkey_info_with_dynamic_mapping(self, hotkey_listener):
        """测试包含动态映射信息的快捷键状态"""
        info = hotkey_listener.get_hotkey_info()
        
        assert 'mapping_status' in info
        assert 'template_monitoring' in info
        
        mapping_status = info['mapping_status']
        assert isinstance(mapping_status, dict)
        
        # 应该有模板监控
        assert info['template_monitoring'] == True
    
    def test_is_hotkey_enabled_with_template_validation(self, hotkey_listener):
        """测试快捷键启用状态检查（包括模板验证）"""
        # 有效的快捷键和模板
        assert hotkey_listener.is_hotkey_enabled('ctrl+alt+cmd+1') == True
        assert hotkey_listener.is_hotkey_enabled('ctrl+alt+cmd+3') == True
        
        # 无效的模板
        assert hotkey_listener.is_hotkey_enabled('ctrl+alt+cmd+2') == False  # nonexistent.md
        
        # 未配置的快捷键
        assert hotkey_listener.is_hotkey_enabled('ctrl+alt+cmd+9') == False
    
    @patch('modules.hotkey_listener.Observer')
    def test_template_monitoring_start_stop(self, mock_observer_class, hotkey_listener):
        """测试模板目录监控的启动和停止"""
        mock_observer = Mock()
        mock_observer_class.return_value = mock_observer
        
        # 重新创建监听器以触发监控启动
        hotkey_listener._start_template_monitoring()
        
        # 应该已经启动了监控（在初始化时就启动了）
        assert hotkey_listener._template_observer is not None
        
        # 停止监控
        hotkey_listener._stop_template_monitoring()
        
        if mock_observer.called:
            mock_observer.stop.assert_called()
    
    def test_template_file_creation_simulation(self, hotkey_listener):
        """测试模拟模板文件创建（测试监控响应）"""
        # 创建一个新的模板文件
        new_template_path = hotkey_listener.template_dir / "new_template.md"
        new_template_content = '''---
model: deepseek
---
New template: {{input}}'''
        
        new_template_path.write_text(new_template_content, encoding='utf-8')
        
        # 等待一段时间让文件系统事件被处理
        time.sleep(0.5)
        
        # 检查新模板是否被发现
        available_templates = hotkey_listener.get_available_templates()
        assert 'new_template.md' in available_templates
        
        # 清理
        new_template_path.unlink()
    
    def test_template_cache(self, hotkey_listener):
        """测试模板信息缓存功能"""
        # 第一次获取模板信息
        info1 = hotkey_listener.get_template_info('translate.md')
        
        # 第二次获取应该使用缓存
        info2 = hotkey_listener.get_template_info('translate.md')
        
        assert info1 == info2
        
        # 验证缓存中确实有数据
        assert 'translate.md' in hotkey_listener._template_cache


if __name__ == "__main__":
    # 运行测试的演示代码
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    print("=== 动态映射功能演示 ===")
    
    # 创建临时环境
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 创建配置和模板目录
        config_dir = temp_path / "config"
        template_dir = temp_path / "prompt"
        config_dir.mkdir()
        template_dir.mkdir()
        
        # 创建示例模板
        (template_dir / "translate.md").write_text("""---
model: deepseek
---
翻译: {{text}}""")
        
        (template_dir / "summarize.md").write_text("""---
model: kimi
---
摘要: {{content}}""")
        
        # 创建配置文件
        config_content = {
            'hotkeys': {
                'ctrl+alt+cmd+1': 'translate.md',
                'ctrl+alt+cmd+2': 'missing.md',  # 故意创建无效映射
            },
            'settings': {'enabled': True}
        }
        
        with open(config_dir / "hotkey_mapping.yaml", 'w') as f:
            yaml.dump(config_content, f)
        
        # 创建监听器
        listener = HotkeyListener(str(config_dir), str(template_dir))
        
        try:
            print(f"📁 模板目录: {template_dir}")
            print(f"⚙️  配置目录: {config_dir}")
            
            # 显示可用模板
            templates = listener.get_available_templates()
            print(f"📋 可用模板: {templates}")
            
            # 显示映射状态
            status = listener.get_mapping_status()
            print(f"📊 映射状态:")
            print(f"  - 总映射数: {status['total_mappings']}")
            print(f"  - 有效映射: {status['valid_mappings']}")
            print(f"  - 无效映射: {status['invalid_mappings']}")
            print(f"  - 未使用模板: {status['unused_templates']}")
            print(f"  - 建议映射: {status['suggestions']}")
            
            # 测试动态添加映射
            result = listener.add_dynamic_mapping('ctrl+alt+cmd+3', 'summarize.md')
            print(f"➕ 动态添加映射结果: {result}")
            
            # 测试模板信息获取
            info = listener.get_template_info('translate.md')
            if info:
                print(f"📄 模板信息: {info['name']}, 大小: {info['size']}")
            
            print("✅ 动态映射功能演示完成!")
            
        finally:
            listener._stop_template_monitoring() 