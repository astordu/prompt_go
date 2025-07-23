"""
AI模型客户端模块

提供统一的AI模型调用接口，支持多种模型（Deepseek、Kimi）的集成和管理
"""

import asyncio
import logging
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Union, AsyncIterator, Iterator, Callable
from enum import Enum
import aiohttp
import requests

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """支持的模型类型"""
    DEEPSEEK = "deepseek"
    KIMI = "kimi"


class ResponseStatus(Enum):
    """响应状态"""
    SUCCESS = "success"
    ERROR = "error"
    STREAMING = "streaming"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


@dataclass
class ModelRequest:
    """模型请求数据结构"""
    
    # 基本参数
    prompt: str
    model: str = "deepseek-chat"
    
    # 生成参数
    temperature: float = 0.5
    max_tokens: int = 2000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # 控制参数
    stream: bool = False
    timeout: int = 30
    
    # 元数据
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """验证请求参数的有效性"""
        errors = []
        
        if not self.prompt or not self.prompt.strip():
            errors.append("prompt不能为空")
            
        if not isinstance(self.temperature, (int, float)) or not (0.0 <= self.temperature <= 2.0):
            errors.append("temperature必须在0.0-2.0之间")
            
        if not isinstance(self.max_tokens, int) or not (1 <= self.max_tokens <= 32000):
            errors.append("max_tokens必须在1-32000之间")
            
        if not isinstance(self.top_p, (int, float)) or not (0.0 <= self.top_p <= 1.0):
            errors.append("top_p必须在0.0-1.0之间")
            
        if not isinstance(self.timeout, int) or not (1 <= self.timeout <= 300):
            errors.append("timeout必须在1-300秒之间")
            
        return errors


@dataclass
class ModelResponse:
    """模型响应数据结构"""
    
    # 基本信息
    content: str
    status: ResponseStatus
    model: str
    
    # 元数据
    request_id: Optional[str] = None
    created_at: Optional[float] = None
    
    # 使用统计
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    
    # 错误信息
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # 性能信息
    response_time: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
    
    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == ResponseStatus.SUCCESS
    
    def is_error(self) -> bool:
        """检查是否有错误"""
        return self.status == ResponseStatus.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


@dataclass 
class StreamChunk:
    """流式响应数据块"""
    
    # 基本内容
    content: str
    chunk_id: int
    
    # 状态信息
    is_final: bool = False
    is_error: bool = False
    
    # 元数据
    request_id: Optional[str] = None
    timestamp: Optional[float] = None
    error_message: Optional[str] = None
    
    # 累积信息（仅在最后一个chunk中有效）
    total_tokens: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


class ModelClientError(Exception):
    """模型客户端基础异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 original_error: Optional[Exception] = None):
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
        super().__init__(self.message)


class APIConnectionError(ModelClientError):
    """API连接错误"""
    pass


class APITimeoutError(ModelClientError):
    """API超时错误"""
    pass


class APIRateLimitError(ModelClientError):
    """API速率限制错误"""
    pass


class APIAuthenticationError(ModelClientError):
    """API认证错误"""
    pass


class APIValidationError(ModelClientError):
    """API参数验证错误"""
    pass


class ModelClient(ABC):
    """模型客户端抽象基类"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, 
                 timeout: int = 30, max_retries: int = 3):
        """
        初始化模型客户端
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            timeout: 默认超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'average_response_time': 0.0,
            'last_request_time': None
        }
        
        # 会话管理
        self._session = None
        self._async_session = None
    
    @abstractmethod
    def get_model_type(self) -> ModelType:
        """获取模型类型"""
        pass
    
    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        pass
    
    @abstractmethod
    def validate_model(self, model: str) -> bool:
        """验证模型名称是否支持"""
        pass
    
    @abstractmethod
    def prepare_request(self, request: ModelRequest) -> Dict[str, Any]:
        """准备API请求数据"""
        pass
    
    @abstractmethod
    def parse_response(self, response_data: Dict[str, Any], 
                      request: ModelRequest) -> ModelResponse:
        """解析API响应数据"""
        pass
    
    @abstractmethod
    def parse_stream_chunk(self, chunk_data: str, chunk_id: int,
                          request: ModelRequest) -> Optional[StreamChunk]:
        """解析流式响应数据块"""
        pass
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'PromptGo/1.0'
        }
    
    def _update_stats(self, response: ModelResponse, response_time: float):
        """更新统计信息"""
        self.stats['total_requests'] += 1
        self.stats['last_request_time'] = time.time()
        
        if response.is_success():
            self.stats['successful_requests'] += 1
            if response.total_tokens:
                self.stats['total_tokens'] += response.total_tokens
        else:
            self.stats['failed_requests'] += 1
            
        # 计算平均响应时间
        total_time = self.stats['average_response_time'] * (self.stats['total_requests'] - 1)
        self.stats['average_response_time'] = (total_time + response_time) / self.stats['total_requests']
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'average_response_time': 0.0,
            'last_request_time': None
        }
    
    # 同步方法
    def chat(self, request: ModelRequest) -> ModelResponse:
        """发送聊天请求（同步）"""
        return self._make_request(request)
    
    def chat_stream(self, request: ModelRequest) -> Iterator[StreamChunk]:
        """发送流式聊天请求（同步）"""
        request.stream = True
        return self._make_stream_request(request)
    
    # 异步方法
    async def chat_async(self, request: ModelRequest) -> ModelResponse:
        """发送聊天请求（异步）"""
        return await self._make_request_async(request)
    
    async def chat_stream_async(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        """发送流式聊天请求（异步）"""
        request.stream = True
        async for chunk in self._make_stream_request_async(request):
            yield chunk
    
    def _make_request(self, request: ModelRequest) -> ModelResponse:
        """发送同步请求"""
        start_time = time.time()
        
        try:
            # 验证请求
            errors = request.validate()
            if errors:
                raise APIValidationError(f"请求参数验证失败: {'; '.join(errors)}")
                
            if not self.validate_model(request.model):
                raise APIValidationError(f"不支持的模型: {request.model}")
            
            # 准备请求数据
            request_data = self.prepare_request(request)
            
            # 发送请求
            response = self._send_http_request(request_data, request.timeout)
            
            # 解析响应
            model_response = self.parse_response(response, request)
            model_response.response_time = time.time() - start_time
            
            # 更新统计
            self._update_stats(model_response, model_response.response_time)
            
            return model_response
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # 创建错误响应
            error_response = ModelResponse(
                content="",
                status=ResponseStatus.ERROR,
                model=request.model,
                request_id=request.request_id,
                error_message=str(e),
                error_code=getattr(e, 'error_code', None),
                response_time=response_time
            )
            
            self._update_stats(error_response, response_time)
            
            if isinstance(e, ModelClientError):
                raise
            else:
                raise ModelClientError(f"请求处理失败: {e}", original_error=e)
    
    def _make_stream_request(self, request: ModelRequest) -> Iterator[StreamChunk]:
        """发送同步流式请求"""
        start_time = time.time()
        chunk_id = 0
        
        try:
            # 验证请求
            errors = request.validate()
            if errors:
                raise APIValidationError(f"请求参数验证失败: {'; '.join(errors)}")
                
            if not self.validate_model(request.model):
                raise APIValidationError(f"不支持的模型: {request.model}")
            
            # 准备请求数据
            request_data = self.prepare_request(request)
            
            # 发送流式请求
            for chunk_data in self._send_stream_request(request_data, request.timeout):
                chunk = self.parse_stream_chunk(chunk_data, chunk_id, request)
                if chunk:
                    yield chunk
                    chunk_id += 1
                    
        except Exception as e:
            # 发送错误块
            error_chunk = StreamChunk(
                content="",
                chunk_id=chunk_id,
                is_final=True,
                is_error=True,
                request_id=request.request_id,
                error_message=f"流式请求处理失败: {e}"
            )
            yield error_chunk
            
            if isinstance(e, ModelClientError):
                raise
            else:
                raise ModelClientError(f"流式请求处理失败: {e}", original_error=e)
    
    async def _make_request_async(self, request: ModelRequest) -> ModelResponse:
        """发送异步请求"""
        start_time = time.time()
        
        try:
            # 验证请求
            errors = request.validate()
            if errors:
                raise APIValidationError(f"请求参数验证失败: {'; '.join(errors)}")
                
            if not self.validate_model(request.model):
                raise APIValidationError(f"不支持的模型: {request.model}")
            
            # 准备请求数据
            request_data = self.prepare_request(request)
            
            # 发送异步请求
            response = await self._send_http_request_async(request_data, request.timeout)
            
            # 解析响应
            model_response = self.parse_response(response, request)
            model_response.response_time = time.time() - start_time
            
            # 更新统计
            self._update_stats(model_response, model_response.response_time)
            
            return model_response
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # 创建错误响应
            error_response = ModelResponse(
                content="",
                status=ResponseStatus.ERROR,
                model=request.model,
                request_id=request.request_id,
                error_message=str(e),
                error_code=getattr(e, 'error_code', None),
                response_time=response_time
            )
            
            self._update_stats(error_response, response_time)
            
            if isinstance(e, ModelClientError):
                raise
            else:
                raise ModelClientError(f"异步请求处理失败: {e}", original_error=e)
    
    async def _make_stream_request_async(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        """发送异步流式请求"""
        start_time = time.time()
        chunk_id = 0
        
        try:
            # 验证请求
            errors = request.validate()
            if errors:
                raise APIValidationError(f"请求参数验证失败: {'; '.join(errors)}")
                
            if not self.validate_model(request.model):
                raise APIValidationError(f"不支持的模型: {request.model}")
            
            # 准备请求数据
            request_data = self.prepare_request(request)
            
            # 发送异步流式请求
            async for chunk_data in self._send_stream_request_async(request_data, request.timeout):
                chunk = self.parse_stream_chunk(chunk_data, chunk_id, request)
                if chunk:
                    yield chunk
                    chunk_id += 1
                    
        except Exception as e:
            # 发送错误块
            error_chunk = StreamChunk(
                content="",
                chunk_id=chunk_id,
                is_final=True,
                is_error=True,
                request_id=request.request_id,
                error_message=f"异步流式请求处理失败: {e}"
            )
            yield error_chunk
            
            if isinstance(e, ModelClientError):
                raise
            else:
                raise ModelClientError(f"异步流式请求处理失败: {e}", original_error=e)
    
    def _send_http_request(self, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """发送HTTP请求（同步）"""
        if self._session is None:
            self._session = requests.Session()
            
        try:
            response = self._session.post(
                self.base_url,
                headers=self.get_headers(),
                json=data,
                timeout=timeout
            )
            
            if response.status_code == 401:
                raise APIAuthenticationError("API认证失败，请检查API密钥")
            elif response.status_code == 429:
                raise APIRateLimitError("API请求频率超限，请稍后重试")
            elif response.status_code >= 400:
                raise APIConnectionError(f"API请求失败，状态码: {response.status_code}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise APITimeoutError(f"API请求超时（{timeout}秒）")
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"API连接失败: {e}")
        except requests.exceptions.RequestException as e:
            raise ModelClientError(f"HTTP请求失败: {e}", original_error=e)
    
    def _send_stream_request(self, data: Dict[str, Any], timeout: int) -> Iterator[str]:
        """发送流式HTTP请求（同步）"""
        if self._session is None:
            self._session = requests.Session()
            
        try:
            with self._session.post(
                self.base_url,
                headers=self.get_headers(),
                json=data,
                timeout=timeout,
                stream=True
            ) as response:
                
                if response.status_code == 401:
                    raise APIAuthenticationError("API认证失败，请检查API密钥")
                elif response.status_code == 429:
                    raise APIRateLimitError("API请求频率超限，请稍后重试")
                elif response.status_code >= 400:
                    raise APIConnectionError(f"API请求失败，状态码: {response.status_code}")
                
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.strip():
                        yield line.strip()
                        
        except requests.exceptions.Timeout:
            raise APITimeoutError(f"API流式请求超时（{timeout}秒）")
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"API连接失败: {e}")
        except requests.exceptions.RequestException as e:
            raise ModelClientError(f"流式HTTP请求失败: {e}", original_error=e)
    
    async def _send_http_request_async(self, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """发送HTTP请求（异步）"""
        if self._async_session is None:
            self._async_session = aiohttp.ClientSession()
            
        try:
            async with self._async_session.post(
                self.base_url,
                headers=self.get_headers(),
                json=data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 401:
                    raise APIAuthenticationError("API认证失败，请检查API密钥")
                elif response.status == 429:
                    raise APIRateLimitError("API请求频率超限，请稍后重试")
                elif response.status >= 400:
                    raise APIConnectionError(f"API请求失败，状态码: {response.status}")
                
                return await response.json()
                
        except asyncio.TimeoutError:
            raise APITimeoutError(f"API异步请求超时（{timeout}秒）")
        except aiohttp.ClientConnectionError as e:
            raise APIConnectionError(f"API连接失败: {e}")
        except aiohttp.ClientError as e:
            raise ModelClientError(f"异步HTTP请求失败: {e}", original_error=e)
    
    async def _send_stream_request_async(self, data: Dict[str, Any], 
                                       timeout: int) -> AsyncIterator[str]:
        """发送流式HTTP请求（异步）"""
        if self._async_session is None:
            self._async_session = aiohttp.ClientSession()
            
        try:
            async with self._async_session.post(
                self.base_url,
                headers=self.get_headers(),
                json=data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 401:
                    raise APIAuthenticationError("API认证失败，请检查API密钥")
                elif response.status == 429:
                    raise APIRateLimitError("API请求频率超限，请稍后重试")
                elif response.status >= 400:
                    raise APIConnectionError(f"API请求失败，状态码: {response.status}")
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str:
                        yield line_str
                        
        except asyncio.TimeoutError:
            raise APITimeoutError(f"API异步流式请求超时（{timeout}秒）")
        except aiohttp.ClientConnectionError as e:
            raise APIConnectionError(f"API连接失败: {e}")
        except aiohttp.ClientError as e:
            raise ModelClientError(f"异步流式HTTP请求失败: {e}", original_error=e)
    
    def close(self):
        """关闭客户端会话"""
        if self._session:
            self._session.close()
            self._session = None
            
    async def aclose(self):
        """关闭异步客户端会话"""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()


class ModelClientFactory:
    """模型客户端工厂"""
    
    _clients = {}
    
    @classmethod
    def register_client(cls, model_type: ModelType, client_class):
        """注册客户端类"""
        cls._clients[model_type] = client_class
    
    @classmethod
    def create_client(cls, model_type: ModelType, api_key: str, 
                     **kwargs) -> ModelClient:
        """创建客户端实例"""
        if model_type not in cls._clients:
            raise ValueError(f"不支持的模型类型: {model_type}")
        
        client_class = cls._clients[model_type]
        return client_class(api_key=api_key, **kwargs)
    
    @classmethod
    def get_supported_types(cls) -> List[ModelType]:
        """获取支持的模型类型列表"""
        return list(cls._clients.keys())


class ClientManager:
    """客户端管理器"""
    
    def __init__(self):
        self._clients: Dict[str, ModelClient] = {}
        self._global_config = {}
    
    def add_client(self, name: str, client: ModelClient):
        """添加客户端"""
        self._clients[name] = client
        
    def get_client(self, name: str) -> Optional[ModelClient]:
        """获取客户端"""
        return self._clients.get(name)
    
    def remove_client(self, name: str) -> bool:
        """移除客户端"""
        if name in self._clients:
            client = self._clients[name]
            client.close()
            del self._clients[name]
            return True
        return False
    
    def list_clients(self) -> List[str]:
        """列出所有客户端"""
        return list(self._clients.keys())
    
    def close_all(self):
        """关闭所有客户端"""
        for client in self._clients.values():
            client.close()
        self._clients.clear()
    
    async def aclose_all(self):
        """异步关闭所有客户端"""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有客户端的统计信息"""
        return {name: client.get_stats() for name, client in self._clients.items()}


class DeepseekClient(ModelClient):
    """Deepseek API客户端"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, 
                 timeout: int = 30, max_retries: int = 3):
        """
        初始化Deepseek客户端
        
        Args:
            api_key: Deepseek API密钥
            base_url: API基础URL，默认使用官方API
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        if base_url is None:
            base_url = "https://api.deepseek.com"
            
        # 确保URL以/chat/completions结尾（DeepSeek API端点）
        if not base_url.endswith('/chat/completions'):
            if base_url.endswith('/'):
                base_url = base_url + 'chat/completions'
            else:
                base_url = base_url + '/chat/completions'
            
        super().__init__(api_key, base_url, timeout, max_retries)
        
        # Deepseek支持的模型列表
        self.supported_models = [
            "deepseek-chat",
            "deepseek-reasoner"
        ]
        
        # 模型参数限制
        self.model_limits = {
            "deepseek-chat": {
                "max_tokens": 32768,
                "context_length": 32768
            },
            "deepseek-reasoner": {
                "max_tokens": 32768,
                "context_length": 32768
            }
        }
    
    def get_model_type(self) -> ModelType:
        """获取模型类型"""
        return ModelType.DEEPSEEK
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return self.supported_models.copy()
    
    def _map_deepseek_model(self, model: str) -> str:
        """将通用模型名映射到DeepSeek特定模型名"""
        model_mapping = {
            "deepseek": "deepseek-chat",  # 默认映射到chat模型
            "deepseek-chat": "deepseek-chat",
            "deepseek-reasoner": "deepseek-reasoner"
        }
        return model_mapping.get(model, model)
    
    def validate_model(self, model: str) -> bool:
        """验证模型名称是否支持（支持模型映射）"""
        mapped_model = self._map_deepseek_model(model)
        return mapped_model in self.supported_models
    
    def prepare_request(self, request: ModelRequest) -> Dict[str, Any]:
        """准备Deepseek API请求数据"""
        
        # 映射模型名
        mapped_model = self._map_deepseek_model(request.model)
        
        # 构建消息格式
        messages = [
            {
                "role": "user",
                "content": request.prompt
            }
        ]
        
        # 基础请求数据
        request_data = {
            "model": mapped_model,
            "messages": messages,
            "stream": request.stream,
        }
        
        # 可选参数
        if request.temperature is not None:
            request_data["temperature"] = request.temperature
        if request.max_tokens is not None:
            request_data["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            request_data["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            request_data["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            request_data["presence_penalty"] = request.presence_penalty
        
        # 添加请求ID（如果有）
        if request.request_id:
            request_data["user"] = request.request_id
        
        return request_data
    
    def parse_response(self, response_data: Dict[str, Any], 
                      request: ModelRequest) -> ModelResponse:
        """解析Deepseek API响应数据"""
        
        try:
            # 检查响应格式
            if "error" in response_data:
                error_info = response_data["error"]
                return ModelResponse(
                    content="",
                    status=ResponseStatus.ERROR,
                    model=request.model,
                    request_id=request.request_id,
                    error_message=error_info.get("message", "未知错误"),
                    error_code=error_info.get("type", "unknown_error")
                )
            
            # 解析成功响应
            if "choices" not in response_data or not response_data["choices"]:
                return ModelResponse(
                    content="",
                    status=ResponseStatus.ERROR,
                    model=request.model,
                    request_id=request.request_id,
                    error_message="响应格式错误：缺少choices字段"
                )
            
            # 获取第一个选择的内容
            choice = response_data["choices"][0]
            content = ""
            
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"] or ""
            elif "text" in choice:
                content = choice["text"] or ""
            
            # 获取使用统计信息
            usage = response_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
            return ModelResponse(
                content=content,
                status=ResponseStatus.SUCCESS,
                model=request.model,
                request_id=request.request_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
        except Exception as e:
            logger.error(f"解析Deepseek响应失败: {e}")
            return ModelResponse(
                content="",
                status=ResponseStatus.ERROR,
                model=request.model,
                request_id=request.request_id,
                error_message=f"响应解析失败: {e}"
            )
    
    def parse_stream_chunk(self, chunk_data: str, chunk_id: int,
                          request: ModelRequest) -> Optional[StreamChunk]:
        """解析Deepseek流式响应数据块"""
        
        try:
            # Deepseek使用SSE格式：data: {json}
            if not chunk_data.startswith("data: "):
                return None
            
            json_str = chunk_data[6:].strip()  # 移除 "data: " 前缀
            
            # 检查是否是结束标记
            if json_str == "[DONE]":
                return StreamChunk(
                    content="",
                    chunk_id=chunk_id,
                    is_final=True,
                    request_id=request.request_id
                )
            
            # 解析JSON数据
            try:
                chunk_json = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"无法解析流式数据块: {json_str}")
                return None
            
            # 检查错误
            if "error" in chunk_json:
                error_info = chunk_json["error"]
                error_message = error_info.get("message", "API返回错误") if isinstance(error_info, dict) else str(error_info)
                return StreamChunk(
                    content="",
                    chunk_id=chunk_id,
                    is_final=True,
                    is_error=True,
                    request_id=request.request_id,
                    error_message=error_message
                )
            
            # 解析内容
            if "choices" not in chunk_json or not chunk_json["choices"]:
                return None
            
            choice = chunk_json["choices"][0]
            content = ""
            is_final = False
            total_tokens = None
            
            # 获取增量内容
            if "delta" in choice:
                delta = choice["delta"]
                if "content" in delta:
                    content = delta["content"] or ""
                    
            # 检查是否完成
            if choice.get("finish_reason") is not None:
                is_final = True
                # 尝试获取使用统计（通常在最后一个块中）
                usage = chunk_json.get("usage", {})
                total_tokens = usage.get("total_tokens")
            
            return StreamChunk(
                content=content,
                chunk_id=chunk_id,
                is_final=is_final,
                request_id=request.request_id,
                total_tokens=total_tokens if is_final else None
            )
            
        except Exception as e:
            logger.error(f"解析Deepseek流式数据块失败: {e}")
            return StreamChunk(
                content="",
                chunk_id=chunk_id,
                is_error=True,
                is_final=True,
                request_id=request.request_id
            )
    
    def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """获取模型信息"""
        if not self.validate_model(model):
            return None
            
        return {
            "name": model,
            "provider": "Deepseek",
            "type": self.get_model_type().value,
            "limits": self.model_limits.get(model, {}),
            "capabilities": {
                "chat": True,
                "stream": True,
                "function_calling": False,  # Deepseek暂不支持函数调用
                "vision": False  # Deepseek暂不支持视觉输入
            }
        }
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, 
                     model: str = "deepseek-chat") -> Dict[str, float]:
        """估算API调用成本（美元）"""
        
        # Deepseek价格表 (2024年价格，可能需要更新)
        pricing = {
            "deepseek-chat": {
                "input": 0.00014,   # 每1K tokens
                "output": 0.00028   # 每1K tokens
            },
            "deepseek-coder": {
                "input": 0.00014,
                "output": 0.00028
            },
            "deepseek-math": {
                "input": 0.00014,
                "output": 0.00028
            }
        }
        
        model_pricing = pricing.get(model, pricing["deepseek-chat"])
        
        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "currency": "USD"
        }
    
    def _update_stats(self, response: ModelResponse, response_time: float):
        """更新统计信息（重写以添加成本计算）"""
        super()._update_stats(response, response_time)
        
        # 添加成本统计
        if response.is_success() and response.prompt_tokens and response.completion_tokens:
            cost_info = self.estimate_cost(
                response.prompt_tokens, 
                response.completion_tokens,
                response.model
            )
            self.stats['total_cost'] += cost_info['total_cost']


# 注册Deepseek客户端到工厂
ModelClientFactory.register_client(ModelType.DEEPSEEK, DeepseekClient)


class KimiClient(ModelClient):
    """Kimi API客户端"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, 
                 timeout: int = 30, max_retries: int = 3):
        """
        初始化Kimi客户端
        
        Args:
            api_key: Kimi API密钥
            base_url: API基础URL，默认使用官方API
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        if base_url is None:
            base_url = "https://api.moonshot.cn/v1"
            
        # 确保URL以/chat/completions结尾（Kimi API端点）
        if not base_url.endswith('/chat/completions'):
            if base_url.endswith('/'):
                base_url = base_url + 'chat/completions'
            else:
                base_url = base_url + '/chat/completions'
            
        super().__init__(api_key, base_url, timeout, max_retries)
        
        # Kimi支持的模型列表
        self.supported_models = [
            "moonshot-v1-8k",
            "moonshot-v1-32k", 
            "moonshot-v1-128k"
        ]
        
        # 模型参数限制
        self.model_limits = {
            "moonshot-v1-8k": {
                "max_tokens": 8000,
                "context_length": 8000
            },
            "moonshot-v1-32k": {
                "max_tokens": 32000,
                "context_length": 32000
            },
            "moonshot-v1-128k": {
                "max_tokens": 128000,
                "context_length": 128000
            }
        }
    
    def get_model_type(self) -> ModelType:
        """获取模型类型"""
        return ModelType.KIMI
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表"""
        return self.supported_models.copy()
    
    def _map_kimi_model(self, model: str) -> str:
        """将通用模型名映射到Kimi特定模型名"""
        # 支持用户使用简化的模型名
        model_mapping = {
            "kimi": "moonshot-v1-8k",
            "kimi-8k": "moonshot-v1-8k",
            "kimi-32k": "moonshot-v1-32k",
            "kimi-128k": "moonshot-v1-128k"
        }
        
        return model_mapping.get(model, model)
    
    def validate_model(self, model: str) -> bool:
        """验证模型名称是否支持（支持模型映射）"""
        mapped_model = self._map_kimi_model(model)
        return mapped_model in self.supported_models
    
    def prepare_request(self, request: ModelRequest) -> Dict[str, Any]:
        """准备Kimi API请求数据"""
        
        # 映射模型名
        mapped_model = self._map_kimi_model(request.model)
        
        # 构建消息格式
        messages = [
            {
                "role": "user",
                "content": request.prompt
            }
        ]
        
        # 基础请求数据
        request_data = {
            "model": mapped_model,
            "messages": messages,
            "stream": request.stream,
        }
        
        # 可选参数
        if request.temperature is not None:
            request_data["temperature"] = request.temperature
        if request.max_tokens is not None:
            request_data["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            request_data["top_p"] = request.top_p
        if request.frequency_penalty is not None:
            request_data["frequency_penalty"] = request.frequency_penalty
        if request.presence_penalty is not None:
            request_data["presence_penalty"] = request.presence_penalty
        
        # Kimi特有参数
        if request.request_id:
            request_data["user"] = request.request_id
        
        return request_data
    
    def parse_response(self, response_data: Dict[str, Any], 
                      request: ModelRequest) -> ModelResponse:
        """解析Kimi API响应数据"""
        
        try:
            # 检查响应格式
            if "error" in response_data:
                error_info = response_data["error"]
                return ModelResponse(
                    content="",
                    status=ResponseStatus.ERROR,
                    model=request.model,
                    request_id=request.request_id,
                    error_message=error_info.get("message", "未知错误"),
                    error_code=error_info.get("type", "unknown_error")
                )
            
            # 解析成功响应
            if "choices" not in response_data or not response_data["choices"]:
                return ModelResponse(
                    content="",
                    status=ResponseStatus.ERROR,
                    model=request.model,
                    request_id=request.request_id,
                    error_message="响应格式错误：缺少choices字段"
                )
            
            # 获取第一个选择的内容
            choice = response_data["choices"][0]
            content = ""
            
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"] or ""
            elif "text" in choice:
                content = choice["text"] or ""
            
            # 获取使用统计信息
            usage = response_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            
            return ModelResponse(
                content=content,
                status=ResponseStatus.SUCCESS,
                model=request.model,
                request_id=request.request_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
        except Exception as e:
            logger.error(f"解析Kimi响应失败: {e}")
            return ModelResponse(
                content="",
                status=ResponseStatus.ERROR,
                model=request.model,
                request_id=request.request_id,
                error_message=f"响应解析失败: {e}"
            )
    
    def parse_stream_chunk(self, chunk_data: str, chunk_id: int,
                          request: ModelRequest) -> Optional[StreamChunk]:
        """解析Kimi流式响应数据块"""
        
        try:
            # Kimi同样使用SSE格式：data: {json}
            if not chunk_data.startswith("data: "):
                return None
            
            json_str = chunk_data[6:].strip()  # 移除 "data: " 前缀
            
            # 检查是否是结束标记
            if json_str == "[DONE]":
                return StreamChunk(
                    content="",
                    chunk_id=chunk_id,
                    is_final=True,
                    request_id=request.request_id
                )
            
            # 解析JSON数据
            try:
                chunk_json = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"无法解析Kimi流式数据块: {json_str}")
                return None
            
            # 检查错误
            if "error" in chunk_json:
                error_info = chunk_json["error"]
                error_message = error_info.get("message", "API返回错误") if isinstance(error_info, dict) else str(error_info)
                return StreamChunk(
                    content="",
                    chunk_id=chunk_id,
                    is_final=True,
                    is_error=True,
                    request_id=request.request_id,
                    error_message=error_message
                )
            
            # 解析内容
            if "choices" not in chunk_json or not chunk_json["choices"]:
                return None
            
            choice = chunk_json["choices"][0]
            content = ""
            is_final = False
            total_tokens = None
            
            # 获取增量内容
            if "delta" in choice:
                delta = choice["delta"]
                if "content" in delta:
                    content = delta["content"] or ""
                    
            # 检查是否完成
            if choice.get("finish_reason") is not None:
                is_final = True
                # 尝试获取使用统计（通常在最后一个块中）
                usage = chunk_json.get("usage", {})
                total_tokens = usage.get("total_tokens")
            
            return StreamChunk(
                content=content,
                chunk_id=chunk_id,
                is_final=is_final,
                request_id=request.request_id,
                total_tokens=total_tokens if is_final else None
            )
            
        except Exception as e:
            logger.error(f"解析Kimi流式数据块失败: {e}")
            return StreamChunk(
                content="",
                chunk_id=chunk_id,
                is_error=True,
                is_final=True,
                request_id=request.request_id
            )
    
    def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """获取模型信息"""
        if not self.validate_model(model):
            return None
            
        return {
            "name": model,
            "provider": "Kimi",
            "type": self.get_model_type().value,
            "limits": self.model_limits.get(model, {}),
            "capabilities": {
                "chat": True,
                "stream": True,
                "function_calling": True,  # Kimi支持函数调用
                "vision": False,  # Kimi暂不支持视觉输入
                "file_upload": True  # Kimi支持文件上传
            }
        }
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int, 
                     model: str = "moonshot-v1-8k") -> Dict[str, float]:
        """估算API调用成本（人民币）"""
        
        # Kimi价格表 (2024年价格，可能需要更新)
        pricing = {
            "moonshot-v1-8k": {
                "input": 0.012,   # 每1K tokens (人民币)
                "output": 0.012   # 每1K tokens (人民币)
            },
            "moonshot-v1-32k": {
                "input": 0.024,
                "output": 0.024
            },
            "moonshot-v1-128k": {
                "input": 0.060,
                "output": 0.060
            }
        }
        
        model_pricing = pricing.get(model, pricing["moonshot-v1-8k"])
        
        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "currency": "CNY"
        }
    

    
    def _update_stats(self, response: ModelResponse, response_time: float):
        """更新统计信息（重写以添加成本计算）"""
        super()._update_stats(response, response_time)
        
        # 添加成本统计
        if response.is_success() and response.prompt_tokens and response.completion_tokens:
            cost_info = self.estimate_cost(
                response.prompt_tokens, 
                response.completion_tokens,
                response.model
            )
            self.stats['total_cost'] += cost_info['total_cost']


# 注册Kimi客户端到工厂
ModelClientFactory.register_client(ModelType.KIMI, KimiClient)


class StreamBuffer:
    """流式响应数据缓冲区"""
    
    def __init__(self, max_size: int = 1000):
        """
        初始化流式缓冲区
        
        Args:
            max_size: 最大缓冲块数量
        """
        self.max_size = max_size
        self.chunks: List[StreamChunk] = []
        self.accumulated_content = ""
        self.is_complete = False
        self.error_occurred = False
        self.error_message = None
        self.total_tokens = None
        
    def add_chunk(self, chunk: StreamChunk) -> bool:
        """
        添加数据块到缓冲区
        
        Args:
            chunk: 流式数据块
            
        Returns:
            bool: 是否成功添加
        """
        if self.is_complete:
            return False
            
        self.chunks.append(chunk)
        
        # 累积内容
        if chunk.content:
            self.accumulated_content += chunk.content
        
        # 检查是否完成
        if chunk.is_final:
            self.is_complete = True
            if chunk.total_tokens:
                self.total_tokens = chunk.total_tokens
        
        # 检查错误
        if chunk.is_error:
            self.error_occurred = True
            self.is_complete = True
            # 尝试从chunk中获取错误信息
            if hasattr(chunk, 'error_message') and chunk.error_message:
                self.error_message = chunk.error_message
            elif chunk.content:
                self.error_message = chunk.content
            else:
                self.error_message = "流式响应中发生未知错误"
        
        # 清理旧数据以防止内存溢出
        if len(self.chunks) > self.max_size:
            self.chunks = self.chunks[-self.max_size:]
        
        return True
    
    def get_content(self) -> str:
        """获取累积的内容"""
        return self.accumulated_content
    
    def get_chunks(self) -> List[StreamChunk]:
        """获取所有数据块"""
        return self.chunks.copy()
    
    def get_latest_chunks(self, count: int) -> List[StreamChunk]:
        """获取最新的数据块"""
        return self.chunks[-count:] if count > 0 else []
    
    def clear(self):
        """清空缓冲区"""
        self.chunks.clear()
        self.accumulated_content = ""
        self.is_complete = False
        self.error_occurred = False
        self.error_message = None
        self.total_tokens = None
    
    def to_response(self, model: str, request_id: Optional[str] = None) -> ModelResponse:
        """将缓冲区内容转换为ModelResponse"""
        if self.error_occurred:
            return ModelResponse(
                content=self.accumulated_content,
                status=ResponseStatus.ERROR,
                model=model,
                request_id=request_id,
                error_message="流式响应过程中发生错误"
            )
        else:
            return ModelResponse(
                content=self.accumulated_content,
                status=ResponseStatus.SUCCESS,
                model=model,
                request_id=request_id,
                total_tokens=self.total_tokens
            )


class StreamProcessor:
    """流式数据处理器"""
    
    def __init__(self):
        """初始化流式处理器"""
        self.event_handlers = {
            'chunk_received': [],
            'content_updated': [],
            'stream_completed': [],
            'stream_error': []
        }
        
    def add_event_handler(self, event: str, handler: Callable):
        """
        添加事件处理器
        
        Args:
            event: 事件类型 ('chunk_received', 'content_updated', 'stream_completed', 'stream_error')
            handler: 处理函数
        """
        if event in self.event_handlers:
            self.event_handlers[event].append(handler)
    
    def remove_event_handler(self, event: str, handler: Callable):
        """移除事件处理器"""
        if event in self.event_handlers and handler in self.event_handlers[event]:
            self.event_handlers[event].remove(handler)
    
    def _trigger_event(self, event: str, *args, **kwargs):
        """触发事件"""
        for handler in self.event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"事件处理器执行失败 ({event}): {e}")
    
    def process_stream(self, chunks: Iterator[StreamChunk], 
                      buffer: Optional[StreamBuffer] = None) -> StreamBuffer:
        """
        处理流式数据
        
        Args:
            chunks: 流式数据块迭代器
            buffer: 可选的缓冲区，如果不提供则创建新的
            
        Returns:
            StreamBuffer: 处理后的缓冲区
        """
        if buffer is None:
            buffer = StreamBuffer()
        
        try:
            for chunk in chunks:
                # 添加到缓冲区
                buffer.add_chunk(chunk)
                
                # 触发事件
                self._trigger_event('chunk_received', chunk)
                
                if chunk.content:
                    self._trigger_event('content_updated', chunk.content, buffer.get_content())
                
                if chunk.is_error:
                    self._trigger_event('stream_error', chunk)
                    break
                    
                if chunk.is_final:
                    self._trigger_event('stream_completed', buffer)
                    break
            
            return buffer
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            # 创建错误块
            error_chunk = StreamChunk(
                content="",
                chunk_id=len(buffer.chunks),
                is_final=True,
                is_error=True,
                error_message=f"流式处理失败: {e}"
            )
            buffer.add_chunk(error_chunk)
            self._trigger_event('stream_error', error_chunk)
            return buffer
    
    async def process_stream_async(self, chunks: AsyncIterator[StreamChunk], 
                                  buffer: Optional[StreamBuffer] = None) -> StreamBuffer:
        """
        异步处理流式数据
        
        Args:
            chunks: 异步流式数据块迭代器
            buffer: 可选的缓冲区，如果不提供则创建新的
            
        Returns:
            StreamBuffer: 处理后的缓冲区
        """
        if buffer is None:
            buffer = StreamBuffer()
        
        try:
            async for chunk in chunks:
                # 添加到缓冲区
                buffer.add_chunk(chunk)
                
                # 触发事件
                self._trigger_event('chunk_received', chunk)
                
                if chunk.content:
                    self._trigger_event('content_updated', chunk.content, buffer.get_content())
                
                if chunk.is_error:
                    self._trigger_event('stream_error', chunk)
                    break
                    
                if chunk.is_final:
                    self._trigger_event('stream_completed', buffer)
                    break
            
            return buffer
            
        except Exception as e:
            logger.error(f"异步流式处理失败: {e}")
            # 创建错误块
            error_chunk = StreamChunk(
                content="",
                chunk_id=len(buffer.chunks),
                is_final=True,
                is_error=True,
                error_message=f"异步流式处理失败: {e}"
            )
            buffer.add_chunk(error_chunk)
            self._trigger_event('stream_error', error_chunk)
            return buffer


class StreamingManager:
    """流式响应管理器"""
    
    def __init__(self):
        """初始化流式管理器"""
        self.active_streams = {}  # request_id -> StreamBuffer
        self.processor = StreamProcessor()
        
        # 性能统计
        self.stats = {
            'total_streams': 0,
            'completed_streams': 0,
            'failed_streams': 0,
            'total_chunks': 0,
            'total_content_length': 0,
            'average_chunk_size': 0.0
        }
    
    def create_stream(self, request_id: str, max_buffer_size: int = 1000) -> StreamBuffer:
        """
        创建新的流式响应
        
        Args:
            request_id: 请求ID
            max_buffer_size: 最大缓冲区大小
            
        Returns:
            StreamBuffer: 新创建的缓冲区
        """
        buffer = StreamBuffer(max_buffer_size)
        self.active_streams[request_id] = buffer
        self.stats['total_streams'] += 1
        
        logger.debug(f"创建新的流式响应: {request_id}")
        return buffer
    
    def get_stream(self, request_id: str) -> Optional[StreamBuffer]:
        """获取指定的流式响应"""
        return self.active_streams.get(request_id)
    
    def close_stream(self, request_id: str):
        """关闭并清理流式响应"""
        if request_id in self.active_streams:
            buffer = self.active_streams[request_id]
            
            # 更新统计
            if buffer.is_complete:
                if buffer.error_occurred:
                    self.stats['failed_streams'] += 1
                else:
                    self.stats['completed_streams'] += 1
                    
            self.stats['total_chunks'] += len(buffer.chunks)
            self.stats['total_content_length'] += len(buffer.accumulated_content)
            
            # 计算平均块大小
            if self.stats['total_chunks'] > 0:
                self.stats['average_chunk_size'] = (
                    self.stats['total_content_length'] / self.stats['total_chunks']
                )
            
            del self.active_streams[request_id]
            logger.debug(f"关闭流式响应: {request_id}")
    
    def process_client_stream(self, client: ModelClient, request: ModelRequest,
                             callback: Optional[Callable[[StreamChunk], None]] = None) -> StreamBuffer:
        """
        处理客户端的流式请求
        
        Args:
            client: 模型客户端
            request: 请求对象
            callback: 可选的数据块回调函数
            
        Returns:
            StreamBuffer: 处理后的缓冲区
        """
        request_id = request.request_id or f"stream_{int(time.time() * 1000)}"
        buffer = self.create_stream(request_id)
        
        try:
            # 设置实时回调
            if callback:
                self.processor.add_event_handler('chunk_received', callback)
            
            # 处理流式数据
            chunks = client.chat_stream(request)
            result_buffer = self.processor.process_stream(chunks, buffer)
            
            return result_buffer
            
        except Exception as e:
            logger.error(f"客户端流式处理失败: {e}")
            # 创建错误响应
            error_chunk = StreamChunk(
                content="",
                chunk_id=0,
                is_final=True,
                is_error=True,
                request_id=request_id,
                error_message=f"客户端流式处理失败: {e}"
            )
            buffer.add_chunk(error_chunk)
            return buffer
            
        finally:
            # 清理回调
            if callback:
                self.processor.remove_event_handler('chunk_received', callback)
            self.close_stream(request_id)
    
    async def process_client_stream_async(self, client: ModelClient, request: ModelRequest,
                                        callback: Optional[Callable[[StreamChunk], None]] = None) -> StreamBuffer:
        """
        异步处理客户端的流式请求
        
        Args:
            client: 模型客户端
            request: 请求对象
            callback: 可选的数据块回调函数
            
        Returns:
            StreamBuffer: 处理后的缓冲区
        """
        request_id = request.request_id or f"async_stream_{int(time.time() * 1000)}"
        buffer = self.create_stream(request_id)
        
        try:
            # 设置实时回调
            if callback:
                self.processor.add_event_handler('chunk_received', callback)
            
            # 异步处理流式数据
            chunks = client.chat_stream_async(request)
            result_buffer = await self.processor.process_stream_async(chunks, buffer)
            
            return result_buffer
            
        except Exception as e:
            logger.error(f"异步客户端流式处理失败: {e}")
            # 创建错误响应
            error_chunk = StreamChunk(
                content="",
                chunk_id=0,
                is_final=True,
                is_error=True,
                request_id=request_id,
                error_message=f"异步客户端流式处理失败: {e}"
            )
            buffer.add_chunk(error_chunk)
            return buffer
            
        finally:
            # 清理回调
            if callback:
                self.processor.remove_event_handler('chunk_received', callback)
            self.close_stream(request_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取流式处理统计信息"""
        return {
            **self.stats,
            'active_streams': len(self.active_streams),
            'success_rate': (
                self.stats['completed_streams'] / self.stats['total_streams']
                if self.stats['total_streams'] > 0 else 0
            )
        }
    
    def cleanup_inactive_streams(self, max_age_seconds: int = 300):
        """清理长时间无活动的流式响应"""
        current_time = time.time()
        inactive_streams = []
        
        for request_id, buffer in self.active_streams.items():
            if buffer.chunks:
                last_chunk = buffer.chunks[-1]
                if hasattr(last_chunk, 'timestamp') and last_chunk.timestamp:
                    age = current_time - last_chunk.timestamp
                    if age > max_age_seconds:
                        inactive_streams.append(request_id)
        
        for request_id in inactive_streams:
            self.close_stream(request_id)
            logger.warning(f"清理无活动流式响应: {request_id}")
        
        return len(inactive_streams)


class RetryPolicy:
    """重试策略配置"""
    
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0,
                 jitter: bool = True):
        """
        初始化重试策略
        
        Args:
            max_attempts: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            backoff_factor: 退避因子
            jitter: 是否添加随机抖动
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        
        # 可重试的错误类型
        self.retryable_errors = {
            APITimeoutError,
            APIConnectionError,
            APIRateLimitError
        }
        
        # 不可重试的错误类型
        self.non_retryable_errors = {
            APIAuthenticationError,
            APIValidationError
        }
    
    def is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_type = type(error)
        
        # 明确不可重试的错误
        if error_type in self.non_retryable_errors:
            return False
            
        # 明确可重试的错误
        if error_type in self.retryable_errors:
            return True
            
        # 特殊处理HTTP状态码
        if isinstance(error, APIConnectionError):
            error_msg = str(error).lower()
            # 5xx错误通常可重试，4xx错误通常不可重试
            if 'status code: 5' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
                return True
            if 'status code: 4' in error_msg:
                # 429 (Rate Limit) 和 408 (Request Timeout) 可重试
                if '429' in error_msg or '408' in error_msg:
                    return True
                return False
        
        # 默认不重试未知错误
        return False
    
    def get_delay(self, attempt: int) -> float:
        """
        计算重试延迟时间
        
        Args:
            attempt: 当前重试次数（从1开始）
            
        Returns:
            float: 延迟时间（秒）
        """
        import random
        
        # 指数退避
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        
        # 限制最大延迟
        delay = min(delay, self.max_delay)
        
        # 添加随机抖动
        if self.jitter:
            jitter_range = delay * 0.1  # 10%的抖动
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class CircuitBreaker:
    """断路器模式实现"""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60,
                 success_threshold: int = 3):
        """
        初始化断路器
        
        Args:
            failure_threshold: 失败阈值，超过此值断路器打开
            timeout_seconds: 断路器打开后的超时时间
            success_threshold: 半开状态下连续成功次数阈值
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        
        # 状态：'closed', 'open', 'half-open'
        self.state = 'closed'
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        
    def is_request_allowed(self) -> bool:
        """检查是否允许请求通过"""
        current_time = time.time()
        
        if self.state == 'closed':
            return True
        elif self.state == 'open':
            # 检查是否超过超时时间，可以尝试半开
            if current_time - self.last_failure_time >= self.timeout_seconds:
                self.state = 'half-open'
                self.success_count = 0
                logger.info("断路器状态变更: open -> half-open")
                return True
            return False
        elif self.state == 'half-open':
            return True
        
        return False
    
    def record_success(self):
        """记录成功请求"""
        if self.state == 'half-open':
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = 'closed'
                self.failure_count = 0
                logger.info("断路器状态变更: half-open -> closed")
        else:
            self.failure_count = 0
    
    def record_failure(self):
        """记录失败请求"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == 'half-open':
            self.state = 'open'
            logger.info("断路器状态变更: half-open -> open")
        elif self.state == 'closed' and self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.info(f"断路器状态变更: closed -> open (失败次数: {self.failure_count})")
    
    def get_status(self) -> Dict[str, Any]:
        """获取断路器状态"""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'is_request_allowed': self.is_request_allowed()
        }


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, policy: Optional[RetryPolicy] = None, 
                 circuit_breaker: Optional[CircuitBreaker] = None):
        """
        初始化重试处理器
        
        Args:
            policy: 重试策略
            circuit_breaker: 断路器
        """
        self.policy = policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        
        # 统计信息
        self.stats = {
            'total_attempts': 0,
            'total_retries': 0,
            'successful_attempts': 0,
            'failed_attempts': 0,
            'circuit_breaker_blocks': 0
        }
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行带重试的函数调用
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            ModelClientError: 最终执行失败
        """
        last_error = None
        
        for attempt in range(1, self.policy.max_attempts + 1):
            self.stats['total_attempts'] += 1
            
            # 检查断路器状态
            if not self.circuit_breaker.is_request_allowed():
                self.stats['circuit_breaker_blocks'] += 1
                raise ModelClientError(
                    "断路器已打开，请求被阻止",
                    error_code="circuit_breaker_open"
                )
            
            try:
                # 执行函数
                result = func(*args, **kwargs)
                
                # 记录成功
                self.stats['successful_attempts'] += 1
                self.circuit_breaker.record_success()
                
                if attempt > 1:
                    logger.info(f"重试成功，总尝试次数: {attempt}")
                
                return result
                
            except Exception as error:
                last_error = error
                self.circuit_breaker.record_failure()
                
                # 检查是否可重试
                if attempt < self.policy.max_attempts and self.policy.is_retryable(error):
                    self.stats['total_retries'] += 1
                    delay = self.policy.get_delay(attempt)
                    
                    logger.warning(f"请求失败，{delay:.2f}秒后重试 (尝试 {attempt}/{self.policy.max_attempts}): {error}")
                    time.sleep(delay)
                    continue
                else:
                    # 不可重试或达到最大重试次数
                    self.stats['failed_attempts'] += 1
                    
                    if not self.policy.is_retryable(error):
                        logger.error(f"请求失败且不可重试: {error}")
                    else:
                        logger.error(f"请求失败，已达到最大重试次数 ({self.policy.max_attempts}): {error}")
                    
                    raise
        
        # 理论上不应该到达这里
        if last_error:
            raise last_error
        else:
            raise ModelClientError("未知错误，重试处理失败")
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        异步执行带重试的函数调用
        
        Args:
            func: 要执行的异步函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            ModelClientError: 最终执行失败
        """
        last_error = None
        
        for attempt in range(1, self.policy.max_attempts + 1):
            self.stats['total_attempts'] += 1
            
            # 检查断路器状态
            if not self.circuit_breaker.is_request_allowed():
                self.stats['circuit_breaker_blocks'] += 1
                raise ModelClientError(
                    "断路器已打开，请求被阻止",
                    error_code="circuit_breaker_open"
                )
            
            try:
                # 执行异步函数
                result = await func(*args, **kwargs)
                
                # 记录成功
                self.stats['successful_attempts'] += 1
                self.circuit_breaker.record_success()
                
                if attempt > 1:
                    logger.info(f"异步重试成功，总尝试次数: {attempt}")
                
                return result
                
            except Exception as error:
                last_error = error
                self.circuit_breaker.record_failure()
                
                # 检查是否可重试
                if attempt < self.policy.max_attempts and self.policy.is_retryable(error):
                    self.stats['total_retries'] += 1
                    delay = self.policy.get_delay(attempt)
                    
                    logger.warning(f"异步请求失败，{delay:.2f}秒后重试 (尝试 {attempt}/{self.policy.max_attempts}): {error}")
                    
                    import asyncio
                    await asyncio.sleep(delay)
                    continue
                else:
                    # 不可重试或达到最大重试次数
                    self.stats['failed_attempts'] += 1
                    
                    if not self.policy.is_retryable(error):
                        logger.error(f"异步请求失败且不可重试: {error}")
                    else:
                        logger.error(f"异步请求失败，已达到最大重试次数 ({self.policy.max_attempts}): {error}")
                    
                    raise
        
        # 理论上不应该到达这里
        if last_error:
            raise last_error
        else:
            raise ModelClientError("未知错误，异步重试处理失败")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        total_attempts = self.stats['total_attempts']
        
        return {
            **self.stats,
            'success_rate': (
                self.stats['successful_attempts'] / total_attempts
                if total_attempts > 0 else 0
            ),
            'retry_rate': (
                self.stats['total_retries'] / total_attempts
                if total_attempts > 0 else 0
            ),
            'circuit_breaker_status': self.circuit_breaker.get_status()
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_attempts': 0,
            'total_retries': 0,
            'successful_attempts': 0,
            'failed_attempts': 0,
            'circuit_breaker_blocks': 0
        }


# 为ModelClient添加重试功能的Mixin
class RetryMixin:
    """重试功能Mixin"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 创建重试处理器
        retry_policy = RetryPolicy(
            max_attempts=getattr(self, 'max_retries', 3),
            base_delay=1.0,
            max_delay=60.0
        )
        circuit_breaker = CircuitBreaker()
        self.retry_handler = RetryHandler(retry_policy, circuit_breaker)
    
    def _make_request_with_retry(self, request: ModelRequest) -> ModelResponse:
        """带重试的请求执行"""
        return self.retry_handler.execute(super()._make_request, request)
    
    async def _make_request_async_with_retry(self, request: ModelRequest) -> ModelResponse:
        """带重试的异步请求执行"""
        return await self.retry_handler.execute_async(super()._make_request_async, request)
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        return self.retry_handler.get_stats()
    
    def reset_retry_stats(self):
        """重置重试统计信息"""
        self.retry_handler.reset_stats()


# 增强的Deepseek客户端
class EnhancedDeepseekClient(RetryMixin, DeepseekClient):
    """增强版Deepseek客户端（带重试功能）"""
    
    def chat(self, request: ModelRequest) -> ModelResponse:
        """发送聊天请求（带重试）"""
        return self._make_request_with_retry(request)
    
    async def chat_async(self, request: ModelRequest) -> ModelResponse:
        """发送异步聊天请求（带重试）"""
        return await self._make_request_async_with_retry(request)


# 增强的Kimi客户端
class EnhancedKimiClient(RetryMixin, KimiClient):
    """增强版Kimi客户端（带重试功能）"""
    
    def chat(self, request: ModelRequest) -> ModelResponse:
        """发送聊天请求（带重试）"""
        return self._make_request_with_retry(request)
    
    async def chat_async(self, request: ModelRequest) -> ModelResponse:
        """发送异步聊天请求（带重试）"""
        return await self._make_request_async_with_retry(request)


class ConnectionPool:
    """HTTP连接池管理器"""
    
    def __init__(self, max_connections: int = 10, max_connections_per_host: int = 5,
                 connection_timeout: int = 30, read_timeout: int = 60,
                 keepalive_timeout: int = 30):
        """
        初始化连接池
        
        Args:
            max_connections: 最大连接数
            max_connections_per_host: 每个主机的最大连接数
            connection_timeout: 连接超时时间
            read_timeout: 读取超时时间  
            keepalive_timeout: 保持连接超时时间
        """
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.keepalive_timeout = keepalive_timeout
        
        # 连接会话
        self._session = None
        self._async_session = None
        
        # 连接统计
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'reused_connections': 0,
            'timeout_errors': 0,
            'connection_errors': 0,
            'last_cleanup_time': time.time()
        }
        
        # 健康检查
        self.health_check_interval = 300  # 5分钟
        self.last_health_check = 0
    
    def get_session(self) -> requests.Session:
        """获取同步HTTP会话"""
        if self._session is None:
            self._session = requests.Session()
            
            # 配置连接池
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # 创建HTTP适配器
            adapter = HTTPAdapter(
                pool_connections=self.max_connections,
                pool_maxsize=self.max_connections_per_host,
                max_retries=0  # 重试由RetryHandler处理
            )
            
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            
            # 配置超时
            self._session.timeout = (self.connection_timeout, self.read_timeout)
            
            self.stats['total_connections'] += 1
            
            logger.debug("创建新的HTTP会话")
        
        return self._session
    
    async def get_async_session(self) -> aiohttp.ClientSession:
        """获取异步HTTP会话"""
        if self._async_session is None:
            # 创建连接器配置
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=self.keepalive_timeout,
                enable_cleanup_closed=True
            )
            
            # 创建超时配置
            timeout = aiohttp.ClientTimeout(
                total=self.read_timeout,
                connect=self.connection_timeout
            )
            
            self._async_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
            
            self.stats['total_connections'] += 1
            
            logger.debug("创建新的异步HTTP会话")
        
        return self._async_session
    
    def close_session(self):
        """关闭同步会话"""
        if self._session:
            self._session.close()
            self._session = None
            self.stats['active_connections'] = max(0, self.stats['active_connections'] - 1)
            logger.debug("关闭HTTP会话")
    
    async def close_async_session(self):
        """关闭异步会话"""
        if self._async_session:
            await self._async_session.close()
            self._async_session = None
            self.stats['active_connections'] = max(0, self.stats['active_connections'] - 1)
            logger.debug("关闭异步HTTP会话")
    
    def health_check(self) -> bool:
        """连接健康检查"""
        current_time = time.time()
        
        if current_time - self.last_health_check < self.health_check_interval:
            return True
        
        try:
            # 检查同步会话
            if self._session:
                # 简单的健康检查 - 确保会话可用
                if hasattr(self._session, 'adapters') and self._session.adapters:
                    logger.debug("同步会话健康检查通过")
                else:
                    logger.warning("同步会话健康检查失败")
                    self.close_session()
            
            # 检查异步会话
            if self._async_session and (self._async_session.closed or self._async_session._connector.closed):
                logger.warning("异步会话已关闭，需要重新创建")
                self._async_session = None
            
            self.last_health_check = current_time
            return True
            
        except Exception as e:
            logger.error(f"连接健康检查失败: {e}")
            return False
    
    def cleanup_connections(self):
        """清理无效连接"""
        current_time = time.time()
        
        if current_time - self.stats['last_cleanup_time'] > 300:  # 5分钟清理一次
            logger.info("执行连接清理")
            
            # 执行健康检查
            self.health_check()
            
            self.stats['last_cleanup_time'] = current_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        return {
            **self.stats,
            'config': {
                'max_connections': self.max_connections,
                'max_connections_per_host': self.max_connections_per_host,
                'connection_timeout': self.connection_timeout,
                'read_timeout': self.read_timeout,
                'keepalive_timeout': self.keepalive_timeout
            },
            'session_status': {
                'sync_session_active': self._session is not None,
                'async_session_active': self._async_session is not None
            }
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_session()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_async_session()


class TimeoutManager:
    """超时管理器"""
    
    def __init__(self, default_timeout: int = 30, max_timeout: int = 300,
                 adaptive_timeout: bool = True):
        """
        初始化超时管理器
        
        Args:
            default_timeout: 默认超时时间
            max_timeout: 最大超时时间
            adaptive_timeout: 是否启用自适应超时
        """
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.adaptive_timeout = adaptive_timeout
        
        # 响应时间历史（用于自适应超时）
        self.response_times = []
        self.max_history = 100
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'timeout_requests': 0,
            'average_response_time': 0.0,
            'adaptive_timeout_value': default_timeout
        }
    
    def get_timeout(self, request_complexity: float = 1.0) -> int:
        """
        获取超时时间
        
        Args:
            request_complexity: 请求复杂度因子（1.0为标准）
            
        Returns:
            int: 超时时间（秒）
        """
        if self.adaptive_timeout and self.response_times:
            # 计算自适应超时（基于历史响应时间）
            avg_time = sum(self.response_times) / len(self.response_times)
            p95_time = sorted(self.response_times)[int(len(self.response_times) * 0.95)]
            
            # 自适应超时 = 95百分位响应时间 * 2.5 * 复杂度因子
            adaptive_timeout = int(p95_time * 2.5 * request_complexity)
            adaptive_timeout = max(self.default_timeout, 
                                 min(adaptive_timeout, self.max_timeout))
            
            self.stats['adaptive_timeout_value'] = adaptive_timeout
            return adaptive_timeout
        else:
            return int(self.default_timeout * request_complexity)
    
    def record_response_time(self, response_time: float, timed_out: bool = False):
        """
        记录响应时间
        
        Args:
            response_time: 响应时间
            timed_out: 是否超时
        """
        self.stats['total_requests'] += 1
        
        if timed_out:
            self.stats['timeout_requests'] += 1
        else:
            # 只记录成功请求的响应时间
            self.response_times.append(response_time)
            
            # 限制历史记录长度
            if len(self.response_times) > self.max_history:
                self.response_times = self.response_times[-self.max_history:]
            
            # 更新平均响应时间
            self.stats['average_response_time'] = sum(self.response_times) / len(self.response_times)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取超时管理统计信息"""
        return {
            **self.stats,
            'timeout_rate': (
                self.stats['timeout_requests'] / self.stats['total_requests']
                if self.stats['total_requests'] > 0 else 0
            ),
            'response_time_samples': len(self.response_times),
            'config': {
                'default_timeout': self.default_timeout,
                'max_timeout': self.max_timeout,
                'adaptive_timeout': self.adaptive_timeout
            }
        }


class EnhancedModelClient(ModelClient):
    """增强版模型客户端（带高级连接管理）"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None,
                 timeout: int = 30, max_retries: int = 3,
                 connection_pool_config: Optional[Dict[str, Any]] = None):
        """
        初始化增强版模型客户端
        
        Args:
            api_key: API密钥
            base_url: API基础URL
            timeout: 超时时间
            max_retries: 最大重试次数
            connection_pool_config: 连接池配置
        """
        super().__init__(api_key, base_url, timeout, max_retries)
        
        # 创建连接池
        pool_config = connection_pool_config or {}
        self.connection_pool = ConnectionPool(**pool_config)
        
        # 创建超时管理器
        self.timeout_manager = TimeoutManager(
            default_timeout=timeout,
            adaptive_timeout=True
        )
        
        # 重写会话获取方法
        self._connection_pool_enabled = True
    
    def _send_http_request(self, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """发送HTTP请求（使用连接池）"""
        if self._connection_pool_enabled:
            # 使用连接池
            session = self.connection_pool.get_session()
            
            # 自适应超时
            adaptive_timeout = self.timeout_manager.get_timeout()
            actual_timeout = min(timeout, adaptive_timeout)
            
            start_time = time.time()
            timed_out = False
            
            try:
                response = session.post(
                    self.base_url,
                    headers=self.get_headers(),
                    json=data,
                    timeout=actual_timeout
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 401:
                    raise APIAuthenticationError("API认证失败，请检查API密钥")
                elif response.status_code == 429:
                    raise APIRateLimitError("API请求频率超限，请稍后重试")
                elif response.status_code >= 400:
                    raise APIConnectionError(f"API请求失败，状态码: {response.status_code}")
                
                # 记录响应时间
                self.timeout_manager.record_response_time(response_time, timed_out)
                self.connection_pool.stats['reused_connections'] += 1
                
                return response.json()
                
            except requests.exceptions.Timeout:
                timed_out = True
                response_time = time.time() - start_time
                self.timeout_manager.record_response_time(response_time, timed_out)
                self.connection_pool.stats['timeout_errors'] += 1
                raise APITimeoutError(f"API请求超时（{actual_timeout}秒）")
            except requests.exceptions.ConnectionError as e:
                self.connection_pool.stats['connection_errors'] += 1
                raise APIConnectionError(f"API连接失败: {e}")
            except requests.exceptions.RequestException as e:
                raise ModelClientError(f"HTTP请求失败: {e}", original_error=e)
        else:
            # 使用原始方法
            return super()._send_http_request(data, timeout)
    
    async def _send_http_request_async(self, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """发送异步HTTP请求（使用连接池）"""
        if self._connection_pool_enabled:
            # 使用连接池
            session = await self.connection_pool.get_async_session()
            
            # 自适应超时
            adaptive_timeout = self.timeout_manager.get_timeout()
            actual_timeout = min(timeout, adaptive_timeout)
            
            start_time = time.time()
            timed_out = False
            
            try:
                async with session.post(
                    self.base_url,
                    headers=self.get_headers(),
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=actual_timeout)
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    if response.status == 401:
                        raise APIAuthenticationError("API认证失败，请检查API密钥")
                    elif response.status == 429:
                        raise APIRateLimitError("API请求频率超限，请稍后重试")
                    elif response.status >= 400:
                        raise APIConnectionError(f"API请求失败，状态码: {response.status}")
                    
                    # 记录响应时间
                    self.timeout_manager.record_response_time(response_time, timed_out)
                    self.connection_pool.stats['reused_connections'] += 1
                    
                    return await response.json()
                    
            except asyncio.TimeoutError:
                timed_out = True
                response_time = time.time() - start_time
                self.timeout_manager.record_response_time(response_time, timed_out)
                self.connection_pool.stats['timeout_errors'] += 1
                raise APITimeoutError(f"API异步请求超时（{actual_timeout}秒）")
            except aiohttp.ClientConnectionError as e:
                self.connection_pool.stats['connection_errors'] += 1
                raise APIConnectionError(f"API连接失败: {e}")
            except aiohttp.ClientError as e:
                raise ModelClientError(f"异步HTTP请求失败: {e}", original_error=e)
        else:
            # 使用原始方法
            return await super()._send_http_request_async(data, timeout)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            'connection_pool': self.connection_pool.get_stats(),
            'timeout_manager': self.timeout_manager.get_stats()
        }
    
    def cleanup_connections(self):
        """清理连接"""
        self.connection_pool.cleanup_connections()
    
    def close(self):
        """关闭客户端"""
        self.connection_pool.close_session()
        super().close()
    
    async def aclose(self):
        """异步关闭客户端"""
        await self.connection_pool.close_async_session()
        await super().aclose() 