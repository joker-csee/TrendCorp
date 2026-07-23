# workflow/base.py — Workflow 基类（日志/耗时/异常）
import logging
import time
from abc import ABC, abstractmethod


class BaseWorkflow(ABC):
    """所有 Workflow 的基类：统一日志记录开始/结束/耗时/异常。

    子类只需实现 execute() 方法。
    """

    def __init__(self):
        self.logger = logging.getLogger(
            f"scheduler.{self.__class__.__name__}"
        )

    def run(self):
        name = self.__class__.__name__
        start = time.time()
        self.logger.info("%s 开始", name)
        try:
            self.execute()
        except Exception as e:
            self.logger.exception("%s 异常: %s", name, e)
            raise
        finally:
            elapsed = time.time() - start
            self.logger.info("%s 完成，耗时 %.1fs", name, elapsed)

    @abstractmethod
    def execute(self):
        """子类实现具体流程步骤。"""
        pass
