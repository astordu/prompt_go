"""
性能优化模块

确保快捷键响应时间 < 500ms 的性能优化组件
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
from collections import defaultdict, deque
import statistics
from functools import wraps, lru_cache
import weakref

logger = logging.getLogger(__name__)


class PerformanceTimer:
    """性能计时器"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration = self.get_duration()
        
        if duration > 0.5:  # 超过500ms记录警告
            logger.warning(f"⚠️ 性能警告: {self.name} 耗时 {duration:.3f}秒 (超过500ms阈值)")
        elif duration > 0.1:  # 超过100ms记录信息
            logger.info(f"⏱️ 性能监控: {self.name} 耗时 {duration:.3f}秒")
        else:
            logger.debug(f"✅ 性能正常: {self.name} 耗时 {duration:.3f}秒")
    
    def get_duration(self) -> float:
        """获取执行时间（秒）"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


class PerformanceCache:
    """高性能缓存组件"""
    
    def __init__(self, max_size: int = 100, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._cache = {}
        self._access_times = {}
        self._access_counts = defaultdict(int)
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None
            
            # 检查TTL
            access_time = self._access_times.get(key, 0)
            if time.time() - access_time > self.ttl:
                self._remove(key)
                return None
            
            # 更新访问统计
            self._access_times[key] = time.time()
            self._access_counts[key] += 1
            
            return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        with self._lock:
            # 如果缓存已满，移除最少使用的项
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = value
            self._access_times[key] = time.time()
            self._access_counts[key] += 1
    
    def _remove(self, key: str) -> None:
        """移除缓存项"""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
        self._access_counts.pop(key, None)
    
    def _evict_lru(self) -> None:
        """移除最少使用的缓存项"""
        if not self._cache:
            return
        
        # 找到访问次数最少的key
        lru_key = min(self._access_counts.keys(), key=lambda k: self._access_counts[k])
        self._remove(lru_key)
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._access_counts.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': self._calculate_hit_rate(),
                'ttl': self.ttl
            }
    
    def _calculate_hit_rate(self) -> float:
        """计算缓存命中率"""
        total_access = sum(self._access_counts.values())
        if total_access == 0:
            return 0.0
        return len(self._cache) / total_access


class TemplatePreloader:
    """模板预加载器"""
    
    def __init__(self, template_dir: Path, cache: PerformanceCache):
        self.template_dir = Path(template_dir)
        self.cache = cache
        self._preloaded = False
        self._preload_lock = threading.Lock()
    
    def preload_templates(self) -> None:
        """预加载常用模板"""
        if self._preloaded:
            return
        
        with self._preload_lock:
            if self._preloaded:
                return
            
            try:
                with PerformanceTimer("模板预加载"):
                    # 预加载所有.md文件
                    template_files = list(self.template_dir.glob("*.md"))
                    
                    for template_file in template_files:
                        try:
                            content = template_file.read_text(encoding='utf-8')
                            cache_key = f"template:{template_file.name}"
                            self.cache.set(cache_key, content)
                        except Exception as e:
                            logger.warning(f"预加载模板失败 {template_file}: {e}")
                    
                    logger.info(f"✅ 预加载完成: {len(template_files)} 个模板")
                    self._preloaded = True
                    
            except Exception as e:
                logger.error(f"模板预加载失败: {e}")
    
    def get_template(self, template_name: str) -> Optional[str]:
        """获取模板内容（从缓存或文件）"""
        cache_key = f"template:{template_name}"
        
        # 先尝试从缓存获取
        content = self.cache.get(cache_key)
        if content is not None:
            return content
        
        # 缓存未命中，从文件读取
        try:
            template_path = self.template_dir / template_name
            if template_path.exists():
                content = template_path.read_text(encoding='utf-8')
                self.cache.set(cache_key, content)
                return content
        except Exception as e:
            logger.error(f"读取模板文件失败 {template_name}: {e}")
        
        return None


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._metrics = defaultdict(lambda: deque(maxlen=max_samples))
        self._lock = threading.RLock()
    
    def record_metric(self, name: str, value: float) -> None:
        """记录性能指标"""
        with self._lock:
            self._metrics[name].append({
                'value': value,
                'timestamp': time.time()
            })
    
    def get_statistics(self, name: str) -> Dict[str, float]:
        """获取指标统计信息"""
        with self._lock:
            values = [item['value'] for item in self._metrics[name]]
            
            if not values:
                return {}
            
            return {
                'count': len(values),
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'min': min(values),
                'max': max(values),
                'p95': self._percentile(values, 0.95),
                'p99': self._percentile(values, 0.99)
            }
    
    def _percentile(self, values: List[float], p: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """获取所有指标统计"""
        with self._lock:
            return {name: self.get_statistics(name) for name in self._metrics.keys()}
    
    def check_performance_threshold(self, name: str, threshold: float = 0.5) -> bool:
        """检查性能是否达标（< 500ms）"""
        stats = self.get_statistics(name)
        if not stats:
            return True
        
        # 检查平均值和95分位数
        return stats.get('mean', 0) < threshold and stats.get('p95', 0) < threshold


def performance_monitor(metric_name: str = None):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            
            with PerformanceTimer(name) as timer:
                result = func(*args, **kwargs)
            
            # 记录到全局性能监控器
            if hasattr(wrapper, '_monitor'):
                wrapper._monitor.record_metric(name, timer.get_duration())
            
            return result
        return wrapper
    return decorator


class FastHotkeyProcessor:
    """快速快捷键处理器 - 专门优化快捷键响应时间"""
    
    def __init__(self, template_dir: Path, config_manager: Any):
        self.template_dir = template_dir
        self.config_manager = config_manager
        
        # 初始化缓存和预加载器
        cache_size = getattr(config_manager, 'get', lambda x, y: y)('performance.template_cache_size', 50)
        cache_ttl = getattr(config_manager, 'get', lambda x, y: y)('performance.config_cache_ttl', 300)
        
        self.cache = PerformanceCache(max_size=cache_size, ttl=cache_ttl)
        self.preloader = TemplatePreloader(template_dir, self.cache)
        self.monitor = PerformanceMonitor()
        
        # 启动预加载
        self._start_preloading()
    
    def _start_preloading(self) -> None:
        """启动后台预加载"""
        def preload_worker():
            self.preloader.preload_templates()
        
        preload_thread = threading.Thread(target=preload_worker, daemon=True)
        preload_thread.start()
    
    @performance_monitor("hotkey_response_total")
    def process_hotkey(self, template_name: str, selected_text: str) -> Dict[str, Any]:
        """快速处理快捷键请求"""
        result = {
            'success': False,
            'processed_content': '',
            'template_name': template_name,
            'processing_time': 0,
            'error': None
        }
        
        start_time = time.perf_counter()
        
        try:
            # 1. 快速获取模板（优先从缓存）
            with PerformanceTimer("模板获取") as timer:
                template_content = self.preloader.get_template(template_name)
                
            if not template_content:
                result['error'] = f"模板文件不存在: {template_name}"
                return result
            
            # 2. 快速文本替换（避免复杂的模板引擎）
            with PerformanceTimer("文本处理") as timer:
                processed_content = self._fast_text_replacement(template_content, selected_text)
            
            result['success'] = True
            result['processed_content'] = processed_content
            
        except Exception as e:
            logger.error(f"快捷键处理失败: {e}")
            result['error'] = str(e)
        
        finally:
            result['processing_time'] = time.perf_counter() - start_time
            self.monitor.record_metric("hotkey_response_time", result['processing_time'])
        
        return result
    
    def _fast_text_replacement(self, template: str, text: str) -> str:
        """快速文本替换 - 避免复杂的模板引擎开销"""
        # 快速替换常用占位符
        replacements = {
            '{{text}}': text,
            '{{selected_text}}': text,
            '{{content}}': text,
            '{{input}}': text,
        }
        
        result = template
        for placeholder, replacement in replacements.items():
            result = result.replace(placeholder, replacement)
        
        return result
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            'cache_stats': self.cache.get_stats(),
            'performance_metrics': self.monitor.get_all_metrics(),
            'preload_status': self.preloader._preloaded,
            'performance_check': {
                'hotkey_response_ok': self.monitor.check_performance_threshold(
                    'hotkey_response_time', 0.5
                ),
                'template_loading_ok': self.monitor.check_performance_threshold(
                    'template_loading_time', 0.1
                )
            }
        }


class PerformanceOptimizer:
    """性能优化器主类"""
    
    def __init__(self, config_manager: Any = None):
        self.config_manager = config_manager
        self.monitor = PerformanceMonitor()
        self._optimizations_applied = False
        
        # 应用优化
        self._apply_optimizations()
    
    def _apply_optimizations(self) -> None:
        """应用性能优化"""
        if self._optimizations_applied:
            return
        
        try:
            # 1. 启用快速JSON解析
            self._optimize_json_parsing()
            
            # 2. 优化日志记录
            self._optimize_logging()
            
            # 3. 预热Python模块
            self._warm_up_modules()
            
            self._optimizations_applied = True
            logger.info("✅ 性能优化已应用")
            
        except Exception as e:
            logger.warning(f"性能优化应用失败: {e}")
    
    def _optimize_json_parsing(self) -> None:
        """优化JSON解析性能"""
        try:
            import ujson
            import json
            # 使用更快的ujson库（如果可用）
            json.loads = ujson.loads
            json.dumps = ujson.dumps
        except ImportError:
            pass
    
    def _optimize_logging(self) -> None:
        """优化日志记录性能"""
        # 对于性能关键路径，减少日志级别
        performance_loggers = [
            'modules.hotkey_listener',
            'modules.text_processor',
            'modules.template_parser'
        ]
        
        for logger_name in performance_loggers:
            perf_logger = logging.getLogger(logger_name)
            if perf_logger.level == logging.DEBUG:
                perf_logger.setLevel(logging.INFO)
    
    def _warm_up_modules(self) -> None:
        """预热Python模块"""
        try:
            # 预导入常用模块
            import re
            import json
            import yaml
            import time
            import threading
            
            # 预编译常用正则表达式
            re.compile(r'\{\{(\w+)\}\}')
            re.compile(r'---\n(.*?)\n---', re.DOTALL)
            
        except Exception as e:
            logger.debug(f"模块预热失败: {e}")
    
    @performance_monitor("optimization_check")
    def check_performance(self) -> Dict[str, Any]:
        """检查系统性能"""
        report = {
            'timestamp': time.time(),
            'optimizations_applied': self._optimizations_applied,
            'performance_status': 'unknown',
            'metrics': {},
            'recommendations': []
        }
        
        try:
            # 获取性能指标
            metrics = self.monitor.get_all_metrics()
            report['metrics'] = metrics
            
            # 检查关键指标
            hotkey_ok = self.monitor.check_performance_threshold('hotkey_response_time', 0.5)
            
            if hotkey_ok:
                report['performance_status'] = 'good'
            else:
                report['performance_status'] = 'needs_optimization'
                report['recommendations'].append(
                    "快捷键响应时间超过500ms，建议检查模板缓存和网络连接"
                )
            
        except Exception as e:
            report['error'] = str(e)
            logger.error(f"性能检查失败: {e}")
        
        return report


# 全局性能优化器实例
_global_optimizer = None

def get_global_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer()
    return _global_optimizer


def ensure_fast_response(target_time: float = 0.5):
    """确保快速响应装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                
                duration = time.perf_counter() - start_time
                if duration > target_time:
                    logger.warning(
                        f"⚠️ 响应时间超标: {func.__name__} 耗时 {duration:.3f}秒 "
                        f"(目标: {target_time}秒)"
                    )
                
                return result
                
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(f"函数执行失败 {func.__name__} (耗时 {duration:.3f}秒): {e}")
                raise
                
        return wrapper
    return decorator 