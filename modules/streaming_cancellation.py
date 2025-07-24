"""
流式输出取消系统

提供ESC键取消流式输出的功能，支持跨平台取消机制。
"""

import threading
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CancellationToken:
    """取消令牌，用于控制流式输出的取消"""
    
    _cancelled: bool = False
    _lock: threading.Lock = None
    
    def __post_init__(self):
        if self._lock is None:
            self._lock = threading.Lock()
    
    def cancel(self) -> bool:
        """请求取消"""
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                logger.debug("取消令牌已激活")
                return True
            return False
    
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        with self._lock:
            return self._cancelled
    
    def reset(self) -> None:
        """重置取消状态"""
        with self._lock:
            self._cancelled = False


class StreamingCancellationManager:
    """流式输出取消管理器"""
    
    def __init__(self):
        """初始化取消管理器"""
        self._active_streams: Dict[str, CancellationToken] = {}
        self._global_token: Optional[CancellationToken] = None
        self._lock = threading.Lock()
        self._esc_listener: Optional[Callable] = None
        self._is_listening = False
        
    def create_cancellation_token(self, stream_id: str) -> CancellationToken:
        """
        为特定流创建取消令牌
        
        Args:
            stream_id: 流ID
            
        Returns:
            CancellationToken: 取消令牌
        """
        with self._lock:
            token = CancellationToken()
            self._active_streams[stream_id] = token
            logger.debug(f"为流 {stream_id} 创建取消令牌")
            return token
    
    def get_cancellation_token(self, stream_id: str) -> Optional[CancellationToken]:
        """
        获取指定流的取消令牌
        
        Args:
            stream_id: 流ID
            
        Returns:
            Optional[CancellationToken]: 取消令牌，如果不存在则返回None
        """
        with self._lock:
            return self._active_streams.get(stream_id)
    
    def cancel_stream(self, stream_id: str) -> bool:
        """
        取消指定流
        
        Args:
            stream_id: 流ID
            
        Returns:
            bool: 是否成功取消
        """
        with self._lock:
            token = self._active_streams.get(stream_id)
            if token:
                cancelled = token.cancel()
                if cancelled:
                    logger.info(f"已取消流: {stream_id}")
                return cancelled
            return False
    
    def cancel_all_streams(self) -> int:
        """
        取消所有活动流
        
        Returns:
            int: 取消的流数量
        """
        with self._lock:
            cancelled_count = 0
            for stream_id, token in list(self._active_streams.items()):
                if token.cancel():
                    cancelled_count += 1
                    logger.info(f"已取消流: {stream_id}")
            
            # 同时取消全局令牌
            if self._global_token and self._global_token.cancel():
                cancelled_count += 1
                logger.info("已取消全局流")
            
            return cancelled_count
    
    def remove_stream(self, stream_id: str) -> bool:
        """
        移除指定流的取消令牌
        
        Args:
            stream_id: 流ID
            
        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]
                logger.debug(f"已移除流 {stream_id} 的取消令牌")
                return True
            return False
    
    def create_global_cancellation(self) -> CancellationToken:
        """创建全局取消令牌"""
        with self._lock:
            self._global_token = CancellationToken()
            logger.debug("创建全局取消令牌")
            return self._global_token
    
    def get_global_cancellation(self) -> Optional[CancellationToken]:
        """获取全局取消令牌"""
        return self._global_token
    
    def start_esc_listener(self, on_esc_pressed: Callable[[], None]) -> bool:
        """
        启动ESC键监听器
        
        Args:
            on_esc_pressed: ESC键按下时的回调函数
            
        Returns:
            bool: 是否成功启动
        """
        if self._is_listening:
            logger.warning("ESC监听器已在运行")
            return False
        
        self._esc_listener = on_esc_pressed
        self._is_listening = True
        logger.info("ESC键监听器已启动")
        return True
    
    def stop_esc_listener(self) -> bool:
        """停止ESC键监听器"""
        if not self._is_listening:
            logger.warning("ESC监听器未运行")
            return False
        
        self._esc_listener = None
        self._is_listening = False
        logger.info("ESC键监听器已停止")
        return True
    
    def handle_esc_key(self) -> None:
        """处理ESC键按下事件"""
        logger.info("检测到ESC键按下，开始取消流式输出")
        
        # 调用注册的回调
        if self._esc_listener:
            try:
                self._esc_listener()
            except Exception as e:
                logger.error(f"ESC回调执行失败: {e}")
        
        # 取消所有活动流
        cancelled_count = self.cancel_all_streams()
        logger.info(f"已取消 {cancelled_count} 个流")
    
    def get_active_streams_count(self) -> int:
        """获取活动流数量"""
        with self._lock:
            return len(self._active_streams)
    
    def get_status(self) -> Dict[str, Any]:
        """获取取消管理器状态"""
        with self._lock:
            return {
                'active_streams': list(self._active_streams.keys()),
                'active_streams_count': len(self._active_streams),
                'global_token_active': self._global_token is not None,
                'esc_listener_active': self._is_listening,
                'esc_listener_registered': self._esc_listener is not None
            }
    
    def cleanup(self) -> None:
        """清理资源"""
        self.stop_esc_listener()
        self.cancel_all_streams()
        
        with self._lock:
            self._active_streams.clear()
            self._global_token = None
            self._esc_listener = None
        
        logger.info("流式取消管理器已清理")


class CancellationAwareStreamProcessor:
    """支持取消的流式处理器"""
    
    def __init__(self, cancellation_manager: StreamingCancellationManager):
        """
        初始化支持取消的流式处理器
        
        Args:
            cancellation_manager: 取消管理器实例
        """
        self.cancellation_manager = cancellation_manager
        self._current_stream_id: Optional[str] = None
        
    def process_with_cancellation(self, 
                                stream_id: str,
                                chunks_iter, 
                                chunk_handler: Callable[[str], None],
                                cancellation_token: CancellationToken) -> Dict[str, Any]:
        """
        处理流式数据，支持取消
        
        Args:
            stream_id: 流ID
            chunks_iter: 数据块迭代器
            chunk_handler: 数据块处理函数
            cancellation_token: 取消令牌
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        self._current_stream_id = stream_id
        
        result = {
            'success': False,
            'content': '',
            'cancelled': False,
            'error': None,
            'total_chunks': 0,
            'processing_time': 0.0
        }
        
        start_time = time.time()
        
        try:
            for chunk in chunks_iter:
                # 检查是否已取消
                if cancellation_token.is_cancelled():
                    logger.info(f"流 {stream_id} 已被用户取消")
                    result['cancelled'] = True
                    break
                
                # 处理数据块
                if chunk.content:
                    result['content'] += chunk.content
                    result['total_chunks'] += 1
                    
                    try:
                        chunk_handler(chunk.content)
                    except Exception as e:
                        logger.error(f"处理数据块时出错: {e}")
                        result['error'] = str(e)
                        break
                
                # 检查是否完成
                if chunk.is_final:
                    result['success'] = True
                    break
                    
                # 检查错误
                if chunk.is_error:
                    result['error'] = chunk.error_message or '未知错误'
                    break
            
            result['processing_time'] = time.time() - start_time
            
        except Exception as e:
            logger.error(f"流式处理异常: {e}")
            result['error'] = str(e)
        
        finally:
            # 清理
            self.cancellation_manager.remove_stream(stream_id)
            self._current_stream_id = None
        
        return result
    
    def get_current_stream_id(self) -> Optional[str]:
        """获取当前处理的流ID"""
        return self._current_stream_id


# 全局取消管理器实例
cancellation_manager = StreamingCancellationManager()


def setup_esc_cancellation(on_esc_pressed: Callable[[], None]) -> None:
    """
    设置ESC键取消功能
    
    Args:
        on_esc_pressed: ESC键按下时的回调函数
    """
    cancellation_manager.start_esc_listener(on_esc_pressed)


def cleanup_esc_cancellation() -> None:
    """清理ESC键取消功能"""
    cancellation_manager.cleanup()


def get_cancellation_status() -> Dict[str, Any]:
    """获取取消系统状态"""
    return cancellation_manager.get_status()