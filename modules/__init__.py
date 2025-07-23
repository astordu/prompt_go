"""
本地提示词管理软件 - 模块包

提供配置管理、项目初始化等核心功能
"""

from .config_manager import (
    ConfigManager, 
    GlobalConfigManager, 
    HotkeyConfigManager
)
from .project_initializer import (
    ProjectInitializer,
    initialize_on_startup
)
from .template_parser import (
    TemplateReader,
    TemplateScanner,
    BasicTemplateParser,
    TemplateParser,
    TemplateContent,
    TemplateParsingError,
    PlaceholderProcessor,
    AdvancedTemplateParser,
    TemplateValidator,
    TemplateLoader,
    TemplateWatcher,
    PLACEHOLDER_PATTERN
)

from .model_client import (
    ModelType,
    ResponseStatus,
    ModelRequest,
    ModelResponse,
    StreamChunk,
    ModelClient,
    ModelClientError,
    APIConnectionError,
    APITimeoutError,
    APIRateLimitError,
    APIAuthenticationError,
    APIValidationError,
    DeepseekClient,
    KimiClient,
    ModelClientFactory,
    ClientManager,
    StreamBuffer,
    StreamProcessor,
    StreamingManager,
    RetryPolicy,
    CircuitBreaker,
    RetryHandler,
    RetryMixin,
    EnhancedDeepseekClient,
    EnhancedKimiClient,
    ConnectionPool,
    TimeoutManager,
    EnhancedModelClient
)

from .text_processor import (
    TextProcessor
)

from .performance_optimizer import (
    PerformanceOptimizer,
    FastHotkeyProcessor,
    PerformanceTimer,
    PerformanceCache,
    PerformanceMonitor,
    get_global_optimizer,
    ensure_fast_response,
    performance_monitor
)

__all__ = [
    'ConfigManager',
    'GlobalConfigManager', 
    'HotkeyConfigManager',
    'ProjectInitializer',
    'initialize_on_startup',
    'TemplateReader',
    'TemplateScanner',
    'BasicTemplateParser',
    'TemplateParser',
    'TemplateContent',
    'TemplateParsingError',
    'PlaceholderProcessor',
    'AdvancedTemplateParser',
    'TemplateValidator',
    'TemplateLoader',
    'TemplateWatcher',
    'PLACEHOLDER_PATTERN',
    # Model client classes
    'ModelType',
    'ResponseStatus',
    'ModelRequest',
    'ModelResponse',
    'StreamChunk',
    'ModelClient',
    'ModelClientError',
    'APIConnectionError',
    'APITimeoutError',
    'APIRateLimitError',
    'APIAuthenticationError',
    'APIValidationError',
    'DeepseekClient',
    'KimiClient',
    'ModelClientFactory',
    'ClientManager',
    'StreamBuffer',
    'StreamProcessor',
    'StreamingManager',
    # Retry and error handling
    'RetryPolicy',
    'CircuitBreaker',
    'RetryHandler',
    'RetryMixin',
    'EnhancedDeepseekClient',
    'EnhancedKimiClient',
    # Connection and timeout management
    'ConnectionPool',
    'TimeoutManager',
    'EnhancedModelClient',
    # Text processing
    'TextProcessor',
    # Performance optimization
    'PerformanceOptimizer',
    'FastHotkeyProcessor',
    'PerformanceTimer',
    'PerformanceCache',
    'PerformanceMonitor',
    'get_global_optimizer',
    'ensure_fast_response',
    'performance_monitor'
] 