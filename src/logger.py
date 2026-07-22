"""
日志系统模块 — 统一的日志管理
支持：分级日志、文件输出、控制台输出、日志轮转
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class LogManager:
    """日志管理器"""

    def __init__(self, log_dir: str = 'logs', log_level: str = 'INFO'):
        """
        初始化日志管理器

        Args:
            log_dir: 日志目录
            log_level: 日志级别
        """
        self.log_dir = log_dir
        self.log_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
        self._loggers = {}

        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)

        # 初始化根日志
        self._setup_root_logger()

    def _setup_root_logger(self):
        """配置根日志"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # 清除现有处理器
        root_logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)

        # 文件处理器（所有日志）
        all_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'app.log'),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        all_handler.setLevel(self.log_level)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        all_handler.setFormatter(file_format)
        root_logger.addHandler(all_handler)

        # 错误日志处理器
        error_handler = RotatingFileHandler(
            os.path.join(self.log_dir, 'error.log'),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        root_logger.addHandler(error_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """
        获取日志器

        Args:
            name: 日志器名称

        Returns:
            logging.Logger: 日志器实例
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(self.log_level)
            self._loggers[name] = logger

        return self._loggers[name]

    def set_level(self, level: str):
        """
        设置日志级别

        Args:
            level: 日志级别
        """
        self.log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        logging.getLogger().setLevel(self.log_level)

        for logger in self._loggers.values():
            logger.setLevel(self.log_level)


# ==================== 全局实例 ====================

log_manager = LogManager()


# ==================== 便捷函数 ====================

def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return log_manager.get_logger(name)


def debug(msg: str, *args, **kwargs):
    """调试日志"""
    logging.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """信息日志"""
    logging.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """警告日志"""
    logging.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """错误日志"""
    logging.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """严重错误日志"""
    logging.critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """异常日志（包含堆栈）"""
    logging.exception(msg, *args, **kwargs)


# ==================== 装饰器 ====================

def log_function(logger_name: str = None, level: str = 'INFO'):
    """
    函数日志装饰器

    Args:
        logger_name: 日志器名称
        level: 日志级别
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = logger_name or func.__module__
            log = get_logger(name)
            log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

            # 记录调用
            log.log(log_level, f"Calling {func.__name__}")

            try:
                result = func(*args, **kwargs)
                log.log(log_level, f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                log.error(f"{func.__name__} failed: {str(e)}")
                raise

        return wrapper
    return decorator


# ==================== 测试 ====================

if __name__ == '__main__':
    print("Logger Module Test")
    print("=" * 50)

    # 测试日志
    log = get_logger('test')
    log.debug("This is debug")
    log.info("This is info")
    log.warning("This is warning")
    log.error("This is error")

    # 测试装饰器
    @log_function('test_decorator')
    def test_func():
        return "success"

    result = test_func()
    print(f"\nResult: {result}")

    # 检查日志文件
    log_dir = 'logs'
    if os.path.exists(log_dir):
        print(f"\nLog files:")
        for f in os.listdir(log_dir):
            path = os.path.join(log_dir, f)
            size = os.path.getsize(path)
            print(f"  {f}: {size} bytes")

    print("\nDone!")
