# data/providers/base.py — Provider 基类
import logging
import time
from abc import ABC
from typing import Callable, Any


class BaseProvider(ABC):
    """所有数据 Provider 的基类：统一日志 + 重试 + 耗时记录。"""

    def __init__(self, max_retries: int = 3):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_retries = max_retries

    def fetch_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """带指数退避重试的数据拉取。失败记录 error.log。"""
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                self.logger.debug(
                    "%s 第 %d 次尝试成功，耗时 %.1fs",
                    func.__name__, attempt, elapsed,
                )
                return result
            except Exception as e:
                last_exc = e
                wait = 2 ** (attempt - 1)  # 1s, 2s, 4s
                self.logger.warning(
                    "%s 第 %d/%d 次失败: %s，%ds 后重试",
                    func.__name__, attempt, self.max_retries, e, wait,
                )
                if attempt < self.max_retries:
                    time.sleep(wait)

        self.logger.exception(
            "%s 全部 %d 次重试均失败", func.__name__, self.max_retries
        )
        raise last_exc
