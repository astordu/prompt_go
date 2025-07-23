#!/usr/bin/env python3
"""
本地提示词管理软件 - 主程序入口

这是一个通过全局快捷键触发的本地提示词管理软件。
支持：
- 获取当前选中的文本
- 将文本插入预设的提示词模板
- 调用AI模型处理
- 将结果流式输出到光标位置

作者：AI Assistant
版本：v1.0.0
"""

import sys
import os
import signal
import argparse
import logging
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from modules import (
        GlobalConfigManager,
        HotkeyConfigManager,
        ProjectInitializer,
        initialize_on_startup,
        TextProcessor
    )
    from modules.hotkey_listener import HotkeyListener
except ImportError as e:
    print(f"错误：无法导入必要的模块 - {e}")
    print("请确保所有模块文件都存在且正确安装了依赖包")
    sys.exit(1)


class PromptManager:
    """本地提示词管理软件主类"""
    
    def __init__(self, config_dir: str = "config", prompt_dir: str = "prompt"):
        """
        初始化提示词管理器
        
        Args:
            config_dir: 配置文件目录
            prompt_dir: 提示词模板目录
        """
        self.config_dir = Path(config_dir)
        self.prompt_dir = Path(prompt_dir)
        self.running = False
        
        # 核心组件
        self.global_config: Optional[GlobalConfigManager] = None
        self.hotkey_config: Optional[HotkeyConfigManager] = None
        self.text_processor: Optional[TextProcessor] = None
        self.hotkey_listener: Optional[HotkeyListener] = None
        self.project_initializer: Optional[ProjectInitializer] = None
        
        # 统计信息
        self.start_time = None
        self.processed_requests = 0
        self.error_count = 0
        
        # 设置日志
        self._setup_logging_from_config()
        
        # 进程管理
        self.pid_file = None
        self._shutdown_event = None
        
        logger = logging.getLogger(__name__)
        logger.info(f"提示词管理器初始化 - 配置目录: {config_dir}, 模板目录: {prompt_dir}")
    
    def _setup_logging(self, log_level: str = "INFO", log_file: str = "prompt_manager.log", 
                      max_size: int = 10*1024*1024, backup_count: int = 5):
        """
        设置增强的日志配置
        
        Args:
            log_level: 日志级别
            log_file: 日志文件路径
            max_size: 单个日志文件最大大小（字节）
            backup_count: 保留的日志文件数量
        """
        import logging.handlers
        from datetime import datetime
        
        # 清除现有的处理器，避免重复
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 设置日志级别
        level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(level)
        
        # 创建格式器
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 1. 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
        
        # 2. 轮转文件处理器
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            console_handler.emit(logging.LogRecord(
                name=__name__,
                level=logging.WARNING,
                pathname="",
                lineno=0,
                msg=f"无法创建日志文件 {log_file}: {e}",
                args=(),
                exc_info=None
            ))
        
        # 3. 错误文件处理器
        try:
            error_handler = logging.handlers.RotatingFileHandler(
                f"error_{log_file}",
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(detailed_formatter)
            logger.addHandler(error_handler)
        except Exception:
            pass  # 如果错误日志文件创建失败，静默忽略
        
        # 记录启动信息
        startup_logger = logging.getLogger(__name__)
        startup_logger.info(f"日志系统初始化完成 - 级别: {log_level}, 文件: {log_file}")
        startup_logger.debug(f"日志配置 - 最大大小: {max_size/1024/1024:.1f}MB, 备份数: {backup_count}")
    
    def _setup_logging_from_config(self):
        """从配置文件设置日志"""
        try:
            # 尝试从配置文件读取日志设置
            config_file = self.config_dir / "global_config.yaml"
            if config_file.exists():
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                log_config = config.get('logging', {})
                self._setup_logging(
                    log_level=log_config.get('level', 'INFO'),
                    log_file=log_config.get('file', 'prompt_manager.log'),
                    max_size=log_config.get('max_size', 10*1024*1024),
                    backup_count=log_config.get('backup_count', 5)
                )
            else:
                # 使用默认配置
                self._setup_logging()
        except Exception as e:
            # 如果配置读取失败，使用默认设置
            self._setup_logging()
            logger = logging.getLogger(__name__)
            logger.warning(f"日志配置读取失败，使用默认设置: {e}")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        获取日志统计信息
        
        Returns:
            Dict[str, Any]: 日志统计信息
        """
        stats = {
            'handlers': [],
            'level': logging.getLevelName(logging.getLogger().level),
            'log_files': []
        }
        
        try:
            logger = logging.getLogger()
            
            # 处理器信息
            for handler in logger.handlers:
                handler_info = {
                    'type': type(handler).__name__,
                    'level': logging.getLevelName(handler.level)
                }
                
                if hasattr(handler, 'baseFilename'):
                    handler_info['file'] = handler.baseFilename
                    # 检查文件大小
                    try:
                        file_path = Path(handler.baseFilename)
                        if file_path.exists():
                            handler_info['size'] = file_path.stat().st_size
                            stats['log_files'].append({
                                'path': str(file_path),
                                'size': handler_info['size']
                            })
                    except Exception:
                        pass
                
                stats['handlers'].append(handler_info)
                
        except Exception as e:
            stats['error'] = str(e)
        
        return stats
    
    def cleanup_old_logs(self, days: int = 30):
        """
        清理旧的日志文件
        
        Args:
            days: 保留天数
        """
        logger = logging.getLogger(__name__)
        
        try:
            import glob
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 查找日志文件
            log_patterns = [
                "prompt_manager.log.*",
                "error_prompt_manager.log.*"
            ]
            
            cleaned_count = 0
            cleaned_size = 0
            
            for pattern in log_patterns:
                for log_file in glob.glob(pattern):
                    try:
                        file_path = Path(log_file)
                        if file_path.exists():
                            # 检查文件修改时间
                            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                            if file_time < cutoff_date:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                cleaned_count += 1
                                cleaned_size += file_size
                                logger.debug(f"删除旧日志文件: {log_file}")
                    except Exception as e:
                        logger.warning(f"删除日志文件失败 {log_file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"清理完成: 删除 {cleaned_count} 个旧日志文件，释放 {cleaned_size/1024/1024:.1f}MB 空间")
            else:
                logger.debug("没有需要清理的旧日志文件")
                
        except Exception as e:
            logger.error(f"日志清理失败: {e}")
    
    def initialize(self) -> bool:
        """
        初始化所有组件
        
        Returns:
            bool: 初始化是否成功
        """
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("开始初始化提示词管理器...")
            
            # 1. 项目结构初始化
            logger.info("初始化项目结构...")
            self.project_initializer = ProjectInitializer()
            init_result = initialize_on_startup()
            
            if not init_result['success']:
                logger.error(f"项目初始化失败: {init_result.get('error')}")
                return False
            
            logger.info(f"项目初始化成功: {init_result['message']}")
            
            # 2. 配置管理器初始化
            logger.info("初始化配置管理器...")
            self.global_config = GlobalConfigManager(self.config_dir)
            self.hotkey_config = HotkeyConfigManager(self.config_dir)
            
            # 加载配置
            try:
                self.global_config.load_config()
                self.hotkey_config.load_config()
                logger.info("配置文件加载成功")
            except Exception as e:
                logger.warning(f"配置文件加载失败，将使用默认配置: {e}")
            
            # 3. 文本处理器初始化
            logger.info("初始化文本处理器...")
            self.text_processor = TextProcessor(
                template_dir=self.prompt_dir,
                config_dir=self.config_dir
            )
            
            # 检查平台能力
            capabilities = self.text_processor.get_platform_capabilities()
            logger.info(f"平台能力检测: {capabilities['platform']}")
            
            if not capabilities['clipboard_available']:
                logger.warning("剪贴板功能不可用")
            if not capabilities['copy_simulation_available']:
                logger.warning("按键模拟功能不可用")
            
            # 4. 快捷键监听器初始化
            logger.info("初始化快捷键监听器...")
            self.hotkey_listener = HotkeyListener(
                config_dir=self.config_dir,
                template_dir=self.prompt_dir
            )
            
            # 设置快捷键处理回调
            self._setup_hotkey_callbacks()
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化过程中发生异常: {e}")
            return False
    
    def _setup_hotkey_callbacks(self):
        """设置快捷键处理回调"""
        logger = logging.getLogger(__name__)
        
        def hotkey_handler(template_name: str):
            """处理快捷键触发事件"""
            try:
                logger.info(f"处理模板: {template_name}")
                self.processed_requests += 1
                
                # 执行完整的文本处理流程
                result = self.text_processor.process_template_with_ai_complete(template_name)
                
                if result['success']:
                    logger.info(f"模板处理成功: {template_name}")
                else:
                    logger.warning(f"模板处理失败: {result.get('error')}")
                    self.error_count += 1
                    
            except Exception as e:
                logger.error(f"快捷键处理异常: {e}")
                self.error_count += 1
        
        # 设置回调函数
        if self.hotkey_listener:
            self.hotkey_listener.register_all_hotkeys(hotkey_handler)
    
    def start(self) -> bool:
        """
        启动提示词管理器
        
        Returns:
            bool: 启动是否成功
        """
        logger = logging.getLogger(__name__)
        
        if self.running:
            logger.warning("提示词管理器已经在运行中")
            return True
        
        try:
            logger.info("启动提示词管理器...")
            
            # 检查组件是否已初始化
            if not all([self.global_config, self.hotkey_config, 
                       self.text_processor, self.hotkey_listener]):
                logger.error("组件未完全初始化，无法启动")
                return False
            
            # 启动快捷键监听器（如果尚未启动）
            if not self.hotkey_listener.is_listening:
                if not self.hotkey_listener.start_listening():
                    logger.error("快捷键监听器启动失败")
                    return False
            else:
                logger.info("快捷键监听器已在运行中")
            
            self.running = True
            self.start_time = time.time()
            
            logger.info("提示词管理器启动成功")
            logger.info("快捷键监听已激活，可以开始使用快捷键...")
            
            # 打印快捷键映射信息
            self._print_hotkey_info()
            
            return True
            
        except Exception as e:
            logger.error(f"启动过程中发生异常: {e}")
            return False
    
    def _print_hotkey_info(self):
        """打印快捷键信息"""
        logger = logging.getLogger(__name__)
        
        try:
            if self.hotkey_listener:
                mappings = self.hotkey_listener.config_manager.get_all_mappings()
                if mappings:
                    logger.info("当前快捷键映射:")
                    for hotkey, template in mappings.items():
                        logger.info(f"  {hotkey} -> {template}")
                else:
                    logger.warning("没有找到快捷键映射配置")
        except Exception as e:
            logger.warning(f"获取快捷键信息失败: {e}")
    
    def stop(self):
        """停止提示词管理器"""
        logger = logging.getLogger(__name__)
        
        if not self.running:
            logger.info("提示词管理器未在运行")
            return
        
        try:
            logger.info("正在停止提示词管理器...")
            
            # 停止快捷键监听器
            if self.hotkey_listener:
                self.hotkey_listener.stop_listening()
            
            # 清理资源
            if self.text_processor:
                # 清理模型客户端缓存
                self.text_processor._model_clients.clear()
            
            self.running = False
            
            # 打印统计信息
            self._print_statistics()
            
            logger.info("提示词管理器已停止")
            
        except Exception as e:
            logger.error(f"停止过程中发生异常: {e}")
    
    def _print_statistics(self):
        """打印运行统计信息"""
        logger = logging.getLogger(__name__)
        
        try:
            if self.start_time:
                runtime = time.time() - self.start_time
                logger.info(f"运行统计:")
                logger.info(f"  运行时长: {runtime:.1f} 秒")
                logger.info(f"  处理请求数: {self.processed_requests}")
                logger.info(f"  错误次数: {self.error_count}")
                if self.processed_requests > 0:
                    success_rate = (self.processed_requests - self.error_count) / self.processed_requests * 100
                    logger.info(f"  成功率: {success_rate:.1f}%")
        except Exception as e:
            logger.warning(f"统计信息打印失败: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("重新加载配置...")
            
            if self.global_config:
                self.global_config.load_config()
            
            if self.hotkey_config:
                self.hotkey_config.load_config()
            
            if self.hotkey_listener:
                self.hotkey_listener.reload_config()
            
            logger.info("配置重新加载完成")
            
        except Exception as e:
            logger.error(f"配置重新加载失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取程序运行状态
        
        Returns:
            Dict[str, Any]: 状态信息
        """
        status = {
            'running': self.running,
            'start_time': self.start_time,
            'processed_requests': self.processed_requests,
            'error_count': self.error_count,
            'components': {
                'global_config': self.global_config is not None,
                'hotkey_config': self.hotkey_config is not None,
                'text_processor': self.text_processor is not None,
                'hotkey_listener': self.hotkey_listener is not None
            }
        }
        
        if self.start_time:
            status['runtime'] = time.time() - self.start_time
        
        return status
    
    def create_pid_file(self, pid_file_path: str = "prompt_manager.pid") -> bool:
        """
        创建PID文件
        
        Args:
            pid_file_path: PID文件路径
            
        Returns:
            bool: 是否成功创建
        """
        logger = logging.getLogger(__name__)
        
        try:
            pid_path = Path(pid_file_path)
            
            # 检查是否已存在PID文件
            if pid_path.exists():
                try:
                    existing_pid = int(pid_path.read_text().strip())
                    # 检查进程是否仍在运行
                    import psutil
                    if psutil.pid_exists(existing_pid):
                        logger.error(f"程序已在运行 (PID: {existing_pid})")
                        return False
                    else:
                        logger.warning(f"发现过期的PID文件，将删除: {pid_file_path}")
                        pid_path.unlink()
                except (ValueError, FileNotFoundError):
                    logger.warning(f"无效的PID文件，将删除: {pid_file_path}")
                    pid_path.unlink()
            
            # 创建新的PID文件
            current_pid = os.getpid()
            pid_path.write_text(str(current_pid))
            self.pid_file = pid_path
            
            logger.info(f"PID文件已创建: {pid_file_path} (PID: {current_pid})")
            return True
            
        except Exception as e:
            logger.error(f"创建PID文件失败: {e}")
            return False
    
    def remove_pid_file(self):
        """删除PID文件"""
        logger = logging.getLogger(__name__)
        
        try:
            if self.pid_file and self.pid_file.exists():
                self.pid_file.unlink()
                logger.info(f"PID文件已删除: {self.pid_file}")
                self.pid_file = None
        except Exception as e:
            logger.warning(f"删除PID文件失败: {e}")
    
    def graceful_shutdown(self, timeout: int = 10):
        """
        优雅关闭程序
        
        Args:
            timeout: 关闭超时时间（秒）
        """
        logger = logging.getLogger(__name__)
        logger.info(f"开始优雅关闭程序 (超时: {timeout}秒)...")
        
        start_time = time.time()
        
        try:
            # 1. 停止接收新请求
            logger.info("1. 停止快捷键监听...")
            if self.hotkey_listener:
                self.hotkey_listener.stop_listening()
            
            # 2. 等待当前处理中的请求完成
            logger.info("2. 等待当前请求完成...")
            while time.time() - start_time < timeout:
                # 在实际应用中，这里可以检查是否有正在处理的请求
                # 目前我们简单等待一段时间
                time.sleep(0.1)
                break  # 由于我们的应用是同步的，直接跳出
            
            # 3. 清理资源
            logger.info("3. 清理资源...")
            if self.text_processor:
                # 清理模型客户端
                if hasattr(self.text_processor, '_model_clients'):
                    for client in self.text_processor._model_clients.values():
                        if hasattr(client, 'close'):
                            client.close()
                    self.text_processor._model_clients.clear()
            
            # 4. 保存状态和统计信息
            logger.info("4. 保存最终状态...")
            self._print_statistics()
            
            # 5. 删除PID文件
            logger.info("5. 清理PID文件...")
            self.remove_pid_file()
            
            self.running = False
            logger.info("优雅关闭完成")
            
        except Exception as e:
            logger.error(f"优雅关闭过程中发生异常: {e}")
            # 强制停止
            self.running = False
            self.remove_pid_file()
    
    def wait_for_shutdown(self):
        """等待关闭信号"""
        logger = logging.getLogger(__name__)
        
        try:
            while self.running:
                time.sleep(0.5)  # 减少CPU使用
        except KeyboardInterrupt:
            logger.info("接收到键盘中断信号")
        except Exception as e:
            logger.error(f"等待关闭过程中发生异常: {e}")


def setup_signal_handlers(prompt_manager: PromptManager):
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger = logging.getLogger(__name__)
        logger.info(f"接收到信号 {signum}，准备优雅退出...")
        prompt_manager.graceful_shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # macOS和Linux支持更多信号
    if hasattr(signal, 'SIGHUP'):
        def reload_handler(signum, frame):
            logger = logging.getLogger(__name__)
            logger.info(f"接收到重载信号 {signum}，重新加载配置...")
            prompt_manager.reload_config()
        
        signal.signal(signal.SIGHUP, reload_handler)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='本地提示词管理软件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                    # 使用默认配置启动
  python main.py --config custom    # 使用自定义配置目录
  python main.py --prompt templates # 使用自定义模板目录
  python main.py --debug            # 启用调试模式
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config',
        help='配置文件目录 (默认: config)'
    )
    
    parser.add_argument(
        '--prompt', '-p',
        default='prompt',
        help='提示词模板目录 (默认: prompt)'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='提示词管理器 v1.0.0'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 设置调试模式
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        print("调试模式已启用")
    
    # 创建提示词管理器
    prompt_manager = PromptManager(
        config_dir=args.config,
        prompt_dir=args.prompt
    )
    
    # 设置信号处理器
    setup_signal_handlers(prompt_manager)
    
    logger = logging.getLogger(__name__)
    
    try:
        # 初始化
        logger.info("=" * 50)
        logger.info("本地提示词管理软件 v1.0.0")
        logger.info("=" * 50)
        
        # 创建PID文件
        if not prompt_manager.create_pid_file():
            logger.error("PID文件创建失败，可能程序已在运行")
            sys.exit(1)
        
        if not prompt_manager.initialize():
            logger.error("初始化失败，程序退出")
            prompt_manager.remove_pid_file()
            sys.exit(1)
        
        # 启动
        if not prompt_manager.start():
            logger.error("启动失败，程序退出")
            prompt_manager.remove_pid_file()
            sys.exit(1)
        
        # 主循环
        logger.info("程序运行中，按 Ctrl+C 退出")
        logger.info("发送 SIGHUP 信号可重新加载配置")
        
        # 使用新的等待机制
        prompt_manager.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("接收到键盘中断信号")
    except Exception as e:
        logger.error(f"程序运行异常: {e}")
        sys.exit(1)
    
    finally:
        # 确保优雅关闭
        if prompt_manager.running:
            prompt_manager.graceful_shutdown()


if __name__ == "__main__":
    main() 