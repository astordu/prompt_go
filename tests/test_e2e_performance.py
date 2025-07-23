"""
端到端功能测试和性能测试模块

测试整个系统的集成功能和性能指标
"""

import pytest
import time
import tempfile
import shutil
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from main import PromptManager
    from modules import (
        GlobalConfigManager, HotkeyConfigManager, TextProcessor,
        ProjectInitializer, initialize_on_startup
    )
    from modules.hotkey_listener import HotkeyListener
except ImportError as e:
    pytest.skip(f"无法导入必要的模块: {e}", allow_module_level=True)


class TestEndToEndFunctionality:
    """端到端功能测试"""
    
    @pytest.fixture
    def test_environment(self):
        """设置测试环境"""
        config_dir = tempfile.mkdtemp()
        prompt_dir = tempfile.mkdtemp()
        
        # 创建测试配置文件
        config_path = Path(config_dir) / "global_config.yaml"
        config_content = """
api:
  deepseek:
    base_url: https://api.deepseek.com
    key: 'sk-test-key-for-testing'
    model: deepseek-chat

logging:
  level: DEBUG
  file: test_prompt_manager.log
  max_size: 1048576
  backup_count: 2
"""
        config_path.write_text(config_content, encoding='utf-8')
        
        # 创建测试模板
        template_path = Path(prompt_dir) / "test_template.md"
        template_content = """---
model: deepseek-chat
temperature: 0.7
max_tokens: 1000
---

请分析以下文本：

{{text}}

请提供详细的分析。
"""
        template_path.write_text(template_content, encoding='utf-8')
        
        yield config_dir, prompt_dir
        
        # 清理
        shutil.rmtree(config_dir)
        shutil.rmtree(prompt_dir)
    
    def test_full_system_initialization(self, test_environment):
        """测试完整系统初始化"""
        config_dir, prompt_dir = test_environment
        
        start_time = time.time()
        
        # 创建和初始化PromptManager
        manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
        
        initialization_time = time.time() - start_time
        
        # 验证初始化时间 < 2秒
        assert initialization_time < 2.0, f"初始化时间过长: {initialization_time:.2f}秒"
        
        # 验证基本组件
        assert manager.config_dir == Path(config_dir)
        assert manager.prompt_dir == Path(prompt_dir)
        assert hasattr(manager, '_setup_logging')
        
    @patch('modules.project_initializer.ProjectInitializer')
    @patch('modules.config_manager.GlobalConfigManager')
    @patch('modules.config_manager.HotkeyConfigManager')
    @patch('modules.text_processor.TextProcessor')
    @patch('modules.hotkey_listener.HotkeyListener')
    def test_component_integration(self, mock_hotkey_listener, mock_text_processor,
                                  mock_hotkey_config, mock_global_config,
                                  mock_project_init, test_environment):
        """测试组件集成"""
        config_dir, prompt_dir = test_environment
        
        # 模拟组件
        mock_project_init.return_value = Mock()
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
        
        # 模拟初始化成功
        with patch('main.initialize_on_startup') as mock_init:
            mock_init.return_value = {'success': True, 'message': '初始化成功'}
            
            manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
            
            # 测试初始化
            start_time = time.time()
            result = manager.initialize()
            init_time = time.time() - start_time
            
            assert result == True
            assert init_time < 1.0, f"组件初始化时间过长: {init_time:.2f}秒"
            
            # 验证组件调用
            mock_global_config_instance.load_config.assert_called_once()
            mock_hotkey_config_instance.load_config.assert_called_once()
            mock_text_processor_instance.get_platform_capabilities.assert_called_once()
    
    def test_configuration_management_performance(self, test_environment):
        """测试配置管理性能"""
        config_dir, prompt_dir = test_environment
        
        config_manager = GlobalConfigManager(config_dir)
        
        # 测试配置加载性能
        start_time = time.time()
        config_manager.load_config()
        load_time = time.time() - start_time
        
        assert load_time < 0.5, f"配置加载时间过长: {load_time:.2f}秒"
        
        # 测试多次访问性能
        start_time = time.time()
        for _ in range(100):
            config_manager.get('api.deepseek.key')
        access_time = time.time() - start_time
        
        assert access_time < 0.1, f"100次配置访问时间过长: {access_time:.2f}秒"
    
    def test_template_processing_performance(self, test_environment):
        """测试模板处理性能"""
        config_dir, prompt_dir = test_environment
        
        text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
        
        # 测试模板验证性能
        start_time = time.time()
        validation = text_processor.validate_template_processing("test_template.md")
        validation_time = time.time() - start_time
        
        assert validation_time < 0.5, f"模板验证时间过长: {validation_time:.2f}秒"
        
        # 测试文本插入性能
        start_time = time.time()
        result = text_processor.insert_text_into_template("test_template.md", "这是测试文本")
        insertion_time = time.time() - start_time
        
        assert insertion_time < 0.3, f"文本插入时间过长: {insertion_time:.2f}秒"
        assert result['success'] == True
    
    def test_memory_usage(self, test_environment):
        """测试内存使用情况"""
        config_dir, prompt_dir = test_environment
        
        try:
            import psutil
            import os
            
            # 获取当前进程
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 创建多个PromptManager实例
            managers = []
            for i in range(10):
                manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
                managers.append(manager)
            
            # 检查内存使用
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # 内存增长应该合理（< 50MB）
            assert memory_increase < 50, f"内存使用过多: {memory_increase:.1f}MB"
            
            # 清理
            del managers
            
        except ImportError:
            pytest.skip("psutil不可用，跳过内存测试")
    
    def test_concurrent_operations(self, test_environment):
        """测试并发操作"""
        config_dir, prompt_dir = test_environment
        
        def worker_function(worker_id, results):
            """工作线程函数"""
            try:
                start_time = time.time()
                
                # 创建配置管理器
                config_manager = GlobalConfigManager(config_dir)
                config_manager.load_config()
                
                # 创建文本处理器
                text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
                
                # 执行模板处理
                result = text_processor.validate_template_processing("test_template.md")
                
                execution_time = time.time() - start_time
                results[worker_id] = {
                    'success': result['is_valid'],
                    'time': execution_time
                }
                
            except Exception as e:
                results[worker_id] = {
                    'success': False,
                    'error': str(e),
                    'time': None
                }
        
        # 启动多个并发线程
        num_threads = 5
        threads = []
        results = {}
        
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=worker_function, args=(i, results))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # 验证结果
        assert len(results) == num_threads
        assert total_time < 5.0, f"并发操作总时间过长: {total_time:.2f}秒"
        
        # 验证所有操作都成功
        successful_operations = sum(1 for r in results.values() if r['success'])
        assert successful_operations == num_threads, f"只有{successful_operations}/{num_threads}个操作成功"
        
        # 验证平均响应时间
        valid_times = [r['time'] for r in results.values() if r['time'] is not None]
        if valid_times:
            avg_time = sum(valid_times) / len(valid_times)
            assert avg_time < 2.0, f"平均操作时间过长: {avg_time:.2f}秒"


class TestPerformanceBenchmarks:
    """性能基准测试"""
    
    @pytest.fixture
    def benchmark_environment(self):
        """设置基准测试环境"""
        config_dir = tempfile.mkdtemp()
        prompt_dir = tempfile.mkdtemp()
        
        # 创建多个测试模板
        templates = [
            ("simple.md", "分析：{{text}}"),
            ("complex.md", """---
model: deepseek-chat
temperature: 0.7
---

请对以下内容进行详细分析：

{{text}}

请从以下几个方面分析：
1. 内容要点
2. 逻辑结构
3. 改进建议
"""),
            ("translate.md", "请将以下文本翻译成英文：{{text}}")
        ]
        
        for filename, content in templates:
            template_path = Path(prompt_dir) / filename
            template_path.write_text(content, encoding='utf-8')
        
        yield config_dir, prompt_dir
        
        shutil.rmtree(config_dir)
        shutil.rmtree(prompt_dir)
    
    def test_template_loading_performance(self, benchmark_environment):
        """测试模板加载性能"""
        config_dir, prompt_dir = benchmark_environment
        
        text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
        
        # 测试获取可用模板的性能
        start_time = time.time()
        templates = text_processor.get_available_templates()
        load_time = time.time() - start_time
        
        assert len(templates) >= 3  # 至少有3个模板
        assert load_time < 1.0, f"模板加载时间过长: {load_time:.2f}秒"
        
        # 测试重复加载性能（应该有缓存）
        start_time = time.time()
        for _ in range(10):
            text_processor.get_available_templates()
        repeated_load_time = time.time() - start_time
        
        assert repeated_load_time < 0.5, f"重复模板加载时间过长: {repeated_load_time:.2f}秒"
    
    def test_text_processing_performance(self, benchmark_environment):
        """测试文本处理性能"""
        config_dir, prompt_dir = benchmark_environment
        
        text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
        
        # 测试不同大小的文本处理性能
        test_texts = [
            "短文本",
            "中等长度的文本" * 10,
            "长文本内容" * 100
        ]
        
        for i, text in enumerate(test_texts):
            start_time = time.time()
            result = text_processor.insert_text_into_template("simple.md", text)
            process_time = time.time() - start_time
            
            assert result['success'] == True
            assert process_time < 0.5, f"文本{i+1}处理时间过长: {process_time:.2f}秒"
    
    def test_hotkey_response_time(self, benchmark_environment):
        """测试快捷键响应时间模拟"""
        config_dir, prompt_dir = benchmark_environment
        
        # 模拟快捷键触发到文本处理的完整流程
        def simulate_hotkey_trigger(template_name: str, text: str) -> float:
            """模拟快捷键触发流程"""
            start_time = time.time()
            
            # 1. 创建文本处理器（模拟快捷键监听器的处理）
            text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
            
            # 2. 验证模板
            validation = text_processor.validate_template_processing(template_name)
            
            # 3. 插入文本
            if validation['is_valid']:
                result = text_processor.insert_text_into_template(template_name, text)
            
            return time.time() - start_time
        
        # 测试不同模板的响应时间
        test_cases = [
            ("simple.md", "测试文本"),
            ("complex.md", "复杂测试文本"),
            ("translate.md", "需要翻译的文本")
        ]
        
        response_times = []
        for template, text in test_cases:
            response_time = simulate_hotkey_trigger(template, text)
            response_times.append(response_time)
            
            # 快捷键响应时间应该 < 500ms（PRD要求）
            assert response_time < 0.5, f"快捷键响应时间过长: {response_time:.3f}秒"
        
        # 计算平均响应时间
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 0.3, f"平均响应时间过长: {avg_response_time:.3f}秒"
    
    def test_system_resource_usage(self, benchmark_environment):
        """测试系统资源使用情况"""
        config_dir, prompt_dir = benchmark_environment
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # 记录初始资源使用
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            initial_cpu_times = process.cpu_times()
            
            # 执行大量操作
            text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
            
            operations_start = time.time()
            for i in range(100):
                text_processor.validate_template_processing("simple.md")
                text_processor.insert_text_into_template("simple.md", f"测试文本 {i}")
            operations_time = time.time() - operations_start
            
            # 记录操作后的资源使用
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            final_cpu_times = process.cpu_times()
            
            memory_increase = final_memory - initial_memory
            cpu_usage = (final_cpu_times.user - initial_cpu_times.user) + (final_cpu_times.system - initial_cpu_times.system)
            
            # 验证资源使用合理
            assert memory_increase < 10, f"内存增长过多: {memory_increase:.1f}MB"
            assert operations_time < 5.0, f"100次操作时间过长: {operations_time:.2f}秒"
            
            # CPU使用率应该合理
            cpu_percentage = (cpu_usage / operations_time) * 100 if operations_time > 0 else 0
            assert cpu_percentage < 50, f"CPU使用率过高: {cpu_percentage:.1f}%"
            
        except ImportError:
            pytest.skip("psutil不可用，跳过资源使用测试")


class TestStressTests:
    """压力测试"""
    
    @pytest.fixture
    def stress_environment(self):
        """设置压力测试环境"""
        config_dir = tempfile.mkdtemp()
        prompt_dir = tempfile.mkdtemp()
        
        # 创建大量模板文件
        for i in range(20):
            template_path = Path(prompt_dir) / f"template_{i:02d}.md"
            template_content = f"""---
model: deepseek-chat
temperature: 0.{i % 10}
---

这是模板{i}，请处理：{{{{text}}}}
"""
            template_path.write_text(template_content, encoding='utf-8')
        
        yield config_dir, prompt_dir
        
        shutil.rmtree(config_dir)
        shutil.rmtree(prompt_dir)
    
    def test_large_template_set_performance(self, stress_environment):
        """测试大模板集性能"""
        config_dir, prompt_dir = stress_environment
        
        text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
        
        # 测试加载大量模板的性能
        start_time = time.time()
        templates = text_processor.get_available_templates()
        load_time = time.time() - start_time
        
        assert len(templates) == 20
        assert load_time < 2.0, f"大模板集加载时间过长: {load_time:.2f}秒"
        
        # 测试批量处理性能
        start_time = time.time()
        for i in range(10):
            template_name = f"template_{i:02d}.md"
            result = text_processor.insert_text_into_template(template_name, f"测试文本 {i}")
            assert result['success'] == True
        
        batch_time = time.time() - start_time
        assert batch_time < 3.0, f"批量处理时间过长: {batch_time:.2f}秒"
    
    def test_high_frequency_operations(self, stress_environment):
        """测试高频操作"""
        config_dir, prompt_dir = stress_environment
        
        text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
        
        # 模拟用户快速连续操作
        operations = []
        start_time = time.time()
        
        for i in range(50):
            op_start = time.time()
            
            template_name = f"template_{i % 20:02d}.md"
            result = text_processor.insert_text_into_template(template_name, f"快速操作 {i}")
            
            op_time = time.time() - op_start
            operations.append(op_time)
            
            assert result['success'] == True
        
        total_time = time.time() - start_time
        
        # 验证总体性能
        assert total_time < 10.0, f"50次高频操作总时间过长: {total_time:.2f}秒"
        
        # 验证单次操作时间稳定性
        avg_time = sum(operations) / len(operations)
        max_time = max(operations)
        
        assert avg_time < 0.2, f"平均操作时间过长: {avg_time:.3f}秒"
        assert max_time < 1.0, f"最长单次操作时间过长: {max_time:.3f}秒"


@pytest.mark.slow
class TestLongRunningOperations:
    """长时间运行测试"""
    
    def test_memory_leak_detection(self):
        """内存泄漏检测"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            config_dir = tempfile.mkdtemp()
            prompt_dir = tempfile.mkdtemp()
            
            try:
                # 记录初始内存
                initial_memory = process.memory_info().rss / 1024 / 1024
                
                # 执行长时间重复操作
                for cycle in range(10):
                    # 创建和销毁PromptManager实例
                    manager = PromptManager(config_dir=config_dir, prompt_dir=prompt_dir)
                    
                    # 创建文本处理器
                    text_processor = TextProcessor(template_dir=prompt_dir, config_dir=config_dir)
                    
                    # 执行一些操作
                    stats = text_processor.get_processing_statistics()
                    
                    # 显式删除
                    del text_processor
                    del manager
                    
                    # 检查内存使用
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - initial_memory
                    
                    # 内存增长应该保持在合理范围内
                    assert memory_increase < 20, f"周期{cycle}内存增长过多: {memory_increase:.1f}MB"
                
            finally:
                shutil.rmtree(config_dir)
                shutil.rmtree(prompt_dir)
                
        except ImportError:
            pytest.skip("psutil不可用，跳过内存泄漏测试")


if __name__ == "__main__":
    # 运行性能测试
    pytest.main([__file__, "-v", "--tb=short"]) 