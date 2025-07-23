"""
模型客户端集成测试模块

测试ModelClient相关类的基本功能和集成
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from modules.model_client import (
        ModelType, ResponseStatus, ModelRequest, ModelResponse,
        StreamChunk, StreamBuffer, StreamProcessor, StreamingManager,
        ModelClientError, APIConnectionError, APITimeoutError,
        ModelClientFactory, DeepseekClient, KimiClient
    )
except ImportError as e:
    pytest.skip(f"无法导入模型客户端模块: {e}", allow_module_level=True)


class TestModelTypes:
    """模型类型和状态测试"""
    
    def test_model_type_enum(self):
        """测试模型类型枚举"""
        assert ModelType.DEEPSEEK.value == "deepseek"
        assert ModelType.KIMI.value == "kimi"
    
    def test_response_status_enum(self):
        """测试响应状态枚举"""
        assert ResponseStatus.SUCCESS.value == "success"
        assert ResponseStatus.ERROR.value == "error"
        assert ResponseStatus.STREAMING.value == "streaming"


class TestModelRequest:
    """ModelRequest类测试"""
    
    def test_model_request_init(self):
        """测试ModelRequest初始化"""
        request = ModelRequest(prompt="test message", model="test-model")
        
        assert request.prompt == "test message"
        assert request.model == "test-model"
        assert request.temperature == 0.5  # 默认值
        assert request.max_tokens == 2000  # 默认值
        assert request.stream == False  # 默认值
    
    def test_model_request_validation(self):
        """测试ModelRequest验证"""
        # 有效请求
        request = ModelRequest(prompt="test", model="test-model")
        errors = request.validate()
        assert len(errors) == 0
        
        # 无效请求 - 空prompt
        request = ModelRequest(prompt="", model="test-model")
        errors = request.validate()
        assert len(errors) > 0
        assert any("prompt不能为空" in error for error in errors)
    
    def test_model_request_dict_conversion(self):
        """测试字典转换"""
        request = ModelRequest(prompt="test", model="test-model", temperature=0.8)
        request_dict = request.to_dict()
        
        assert request_dict['prompt'] == "test"
        assert request_dict['model'] == "test-model"
        assert request_dict['temperature'] == 0.8


class TestModelResponse:
    """ModelResponse类测试"""
    
    def test_model_response_init(self):
        """测试ModelResponse初始化"""
        response = ModelResponse(
            content="test response",
            status=ResponseStatus.SUCCESS,
            model="test-model"
        )
        
        assert response.content == "test response"
        assert response.status == ResponseStatus.SUCCESS
        assert response.model == "test-model"
    
    def test_model_response_success_check(self):
        """测试成功状态检查"""
        success_response = ModelResponse(
            content="test",
            status=ResponseStatus.SUCCESS,
            model="test-model"
        )
        
        error_response = ModelResponse(
            content="",
            status=ResponseStatus.ERROR,
            model="test-model"
        )
        
        assert success_response.is_success() == True
        assert error_response.is_success() == False
    
    def test_model_response_dict_conversion(self):
        """测试字典转换"""
        response = ModelResponse(
            content="test response",
            status=ResponseStatus.SUCCESS,
            model="test-model",
            total_tokens=100
        )
        
        response_dict = response.to_dict()
        assert response_dict['content'] == "test response"
        assert response_dict['status'] == ResponseStatus.SUCCESS  # 枚举对象
        assert response_dict['total_tokens'] == 100


class TestStreamChunk:
    """StreamChunk类测试"""
    
    def test_stream_chunk_init(self):
        """测试StreamChunk初始化"""
        chunk = StreamChunk(content="test content", chunk_id=1)
        
        assert chunk.content == "test content"
        assert chunk.chunk_id == 1
        assert chunk.is_final == False
        assert chunk.is_error == False
        assert chunk.timestamp is not None
    
    def test_stream_chunk_dict_conversion(self):
        """测试字典转换"""
        chunk = StreamChunk(
            content="test",
            chunk_id=1,
            is_final=True,
            total_tokens=50
        )
        
        chunk_dict = chunk.to_dict()
        assert chunk_dict['content'] == "test"
        assert chunk_dict['chunk_id'] == 1
        assert chunk_dict['is_final'] == True
        assert chunk_dict['total_tokens'] == 50


class TestStreamBuffer:
    """StreamBuffer类测试"""
    
    @pytest.fixture
    def stream_buffer(self):
        """创建StreamBuffer实例"""
        return StreamBuffer(max_size=5)
    
    def test_stream_buffer_init(self, stream_buffer):
        """测试StreamBuffer初始化"""
        assert stream_buffer.max_size == 5
        assert len(stream_buffer.chunks) == 0
        assert stream_buffer.accumulated_content == ""
        assert stream_buffer.is_complete == False
        assert stream_buffer.error_occurred == False
    
    def test_add_chunk(self, stream_buffer):
        """测试添加数据块"""
        chunk1 = StreamChunk(content="Hello", chunk_id=0)
        chunk2 = StreamChunk(content=" World", chunk_id=1)
        
        assert stream_buffer.add_chunk(chunk1) == True
        assert stream_buffer.add_chunk(chunk2) == True
        
        assert stream_buffer.get_content() == "Hello World"
        assert len(stream_buffer.chunks) == 2
    
    def test_final_chunk(self, stream_buffer):
        """测试最终数据块"""
        chunk1 = StreamChunk(content="Hello", chunk_id=0)
        final_chunk = StreamChunk(
            content=" World",
            chunk_id=1,
            is_final=True,
            total_tokens=100
        )
        
        stream_buffer.add_chunk(chunk1)
        stream_buffer.add_chunk(final_chunk)
        
        assert stream_buffer.is_complete == True
        assert stream_buffer.total_tokens == 100
    
    def test_error_chunk(self, stream_buffer):
        """测试错误数据块"""
        error_chunk = StreamChunk(
            content="",
            chunk_id=0,
            is_error=True,
            is_final=True
        )
        
        stream_buffer.add_chunk(error_chunk)
        
        assert stream_buffer.error_occurred == True
        assert stream_buffer.is_complete == True
    
    def test_to_response(self, stream_buffer):
        """测试转换为ModelResponse"""
        chunk = StreamChunk(content="Test response", chunk_id=0, is_final=True)
        stream_buffer.add_chunk(chunk)
        
        response = stream_buffer.to_response("test-model", "request-123")
        
        assert response.content == "Test response"
        assert response.status == ResponseStatus.SUCCESS
        assert response.model == "test-model"
        assert response.request_id == "request-123"


class TestStreamProcessor:
    """StreamProcessor类测试"""
    
    @pytest.fixture
    def stream_processor(self):
        """创建StreamProcessor实例"""
        return StreamProcessor()
    
    def test_stream_processor_init(self, stream_processor):
        """测试StreamProcessor初始化"""
        assert 'chunk_received' in stream_processor.event_handlers
        assert 'content_updated' in stream_processor.event_handlers
        assert 'stream_completed' in stream_processor.event_handlers
        assert 'stream_error' in stream_processor.event_handlers
    
    def test_add_remove_event_handler(self, stream_processor):
        """测试事件处理器管理"""
        def test_handler(chunk):
            pass
        
        # 添加处理器
        stream_processor.add_event_handler('chunk_received', test_handler)
        assert test_handler in stream_processor.event_handlers['chunk_received']
        
        # 移除处理器
        stream_processor.remove_event_handler('chunk_received', test_handler)
        assert test_handler not in stream_processor.event_handlers['chunk_received']
    
    def test_process_stream(self, stream_processor):
        """测试流式数据处理"""
        chunks = [
            StreamChunk(content="Hello", chunk_id=0),
            StreamChunk(content=" World", chunk_id=1, is_final=True)
        ]
        
        # 记录事件
        events = []
        
        def chunk_handler(chunk):
            events.append(('chunk_received', chunk))
        
        def content_handler(content, accumulated):
            events.append(('content_updated', content, accumulated))
        
        def completed_handler(buffer):
            events.append(('stream_completed', buffer))
        
        stream_processor.add_event_handler('chunk_received', chunk_handler)
        stream_processor.add_event_handler('content_updated', content_handler)
        stream_processor.add_event_handler('stream_completed', completed_handler)
        
        buffer = stream_processor.process_stream(iter(chunks))
        
        assert buffer.get_content() == "Hello World"
        assert buffer.is_complete == True
        assert len(events) >= 3  # 至少触发了3个事件


class TestStreamingManager:
    """StreamingManager类测试"""
    
    @pytest.fixture
    def streaming_manager(self):
        """创建StreamingManager实例"""
        return StreamingManager()
    
    def test_streaming_manager_init(self, streaming_manager):
        """测试StreamingManager初始化"""
        assert len(streaming_manager.active_streams) == 0
        assert streaming_manager.stats['total_streams'] == 0
        assert streaming_manager.processor is not None
    
    def test_create_stream(self, streaming_manager):
        """测试创建流"""
        buffer = streaming_manager.create_stream("test-request-1")
        
        assert "test-request-1" in streaming_manager.active_streams
        assert streaming_manager.stats['total_streams'] == 1
        assert isinstance(buffer, StreamBuffer)
    
    def test_get_stream(self, streaming_manager):
        """测试获取流"""
        buffer = streaming_manager.create_stream("test-request-1")
        retrieved_buffer = streaming_manager.get_stream("test-request-1")
        
        assert buffer == retrieved_buffer
        assert streaming_manager.get_stream("nonexistent") is None
    
    def test_close_stream(self, streaming_manager):
        """测试关闭流"""
        streaming_manager.create_stream("test-request-1")
        streaming_manager.close_stream("test-request-1")
        
        assert "test-request-1" not in streaming_manager.active_streams


class TestModelClientFactory:
    """ModelClientFactory类测试"""
    
    def test_create_deepseek_client(self):
        """测试创建Deepseek客户端"""
        client = ModelClientFactory.create_client(ModelType.DEEPSEEK, "test-api-key")
        
        assert isinstance(client, DeepseekClient)
        assert client.api_key == "test-api-key"
    
    def test_create_kimi_client(self):
        """测试创建Kimi客户端"""
        client = ModelClientFactory.create_client(ModelType.KIMI, "test-api-key")
        
        assert isinstance(client, KimiClient)
        assert client.api_key == "test-api-key"
    
    def test_invalid_model_type(self):
        """测试无效模型类型"""
        with pytest.raises(ValueError):
            ModelClientFactory.create_client("invalid_type", "test-api-key")


class TestDeepseekClient:
    """DeepseekClient类基本测试"""
    
    @pytest.fixture
    def deepseek_client(self):
        """创建DeepseekClient实例"""
        return DeepseekClient("test-api-key")
    
    def test_deepseek_client_init(self, deepseek_client):
        """测试DeepseekClient初始化"""
        assert deepseek_client.api_key == "test-api-key"
        assert deepseek_client.get_model_type() == ModelType.DEEPSEEK
    
    def test_get_supported_models(self, deepseek_client):
        """测试获取支持的模型"""
        models = deepseek_client.get_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_validate_model(self, deepseek_client):
        """测试模型验证"""
        # 假设deepseek-chat是支持的
        supported_models = deepseek_client.get_supported_models()
        if supported_models:
            assert deepseek_client.validate_model(supported_models[0]) == True
        
        assert deepseek_client.validate_model("invalid-model") == False


class TestKimiClient:
    """KimiClient类基本测试"""
    
    @pytest.fixture
    def kimi_client(self):
        """创建KimiClient实例"""
        return KimiClient("test-api-key")
    
    def test_kimi_client_init(self, kimi_client):
        """测试KimiClient初始化"""
        assert kimi_client.api_key == "test-api-key"
        assert kimi_client.get_model_type() == ModelType.KIMI
    
    def test_get_supported_models(self, kimi_client):
        """测试获取支持的模型"""
        models = kimi_client.get_supported_models()
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_validate_model(self, kimi_client):
        """测试模型验证"""
        supported_models = kimi_client.get_supported_models()
        if supported_models:
            assert kimi_client.validate_model(supported_models[0]) == True
        
        assert kimi_client.validate_model("invalid-model") == False


class TestModelClientErrors:
    """模型客户端错误测试"""
    
    def test_model_client_error_init(self):
        """测试ModelClientError初始化"""
        error = ModelClientError("Test error message")
        assert str(error) == "Test error message"
        assert error.error_code is None
    
    def test_api_connection_error(self):
        """测试API连接错误"""
        error = APIConnectionError("Connection failed")
        assert isinstance(error, ModelClientError)
        assert str(error) == "Connection failed"
    
    def test_api_timeout_error(self):
        """测试API超时错误"""
        error = APITimeoutError("Request timeout")
        assert isinstance(error, ModelClientError)
        assert str(error) == "Request timeout"


class TestIntegration:
    """集成测试"""
    
    def test_end_to_end_data_flow(self):
        """测试端到端数据流"""
        # 创建请求
        request = ModelRequest(prompt="Hello", model="test-model")
        assert request.validate() == []
        
        # 创建响应
        response = ModelResponse(
            content="Hello back",
            status=ResponseStatus.SUCCESS,
            model="test-model"
        )
        assert response.is_success()
        
        # 创建流式数据
        chunk1 = StreamChunk(content="Hello", chunk_id=0)
        chunk2 = StreamChunk(content=" back", chunk_id=1, is_final=True)
        
        # 处理流式数据
        buffer = StreamBuffer()
        buffer.add_chunk(chunk1)
        buffer.add_chunk(chunk2)
        
        assert buffer.get_content() == "Hello back"
        assert buffer.is_complete == True
        
        # 转换为响应
        final_response = buffer.to_response("test-model")
        assert final_response.content == "Hello back"
        assert final_response.is_success()
    
    def test_streaming_workflow(self):
        """测试流式处理工作流"""
        chunks = [
            StreamChunk(content="Hello", chunk_id=0),
            StreamChunk(content=" ", chunk_id=1),
            StreamChunk(content="World", chunk_id=2, is_final=True)
        ]
        
        processor = StreamProcessor()
        buffer = processor.process_stream(iter(chunks))
        
        assert buffer.get_content() == "Hello World"
        assert buffer.is_complete == True
        assert len(buffer.chunks) == 3 