# engine/risk_controller.py — E-1 三级熔断器
import logging
from datetime import datetime
from enum import Enum


class FuseLevel(Enum):
    NORMAL = "NORMAL"
    STOCK_STOP = "STOCK_STOP"
    DAILY_BAN = "DAILY_BAN"
    WEEKLY_BAN = "WEEKLY_BAN"
    MONTHLY_BAN = "MONTHLY_BAN"


class RiskController:
    """E-1 三级熔断器。权限最高，输出是强制性的。"""

    def __init__(self, stock_loss_limit: float = -0.08,
                 daily_dd_limit: float = -0.03,
                 weekly_dd_limit: float = -0.05,
                 monthly_dd_limit: float = -0.10,
                 strategy_dd_limit: float = -0.15,
                 consecutive_stop_limit: int = 2,
                 risk_repo=None):
        self.stock_loss_limit = stock_loss_limit
        self.daily_dd_limit = daily_dd_limit
        self.weekly_dd_limit = weekly_dd_limit
        self.monthly_dd_limit = monthly_dd_limit
        self.strategy_dd_limit = strategy_dd_limit
        self.consecutive_stop_limit = consecutive_stop_limit
        self.consecutive_stops = 0
        # P0-1: 注入 RiskRepository 以持久化熔断事件
        self.risk_repo = risk_repo
        self.logger = logging.getLogger("app.risk_ctrl")

    # ---- P0-1: 事件持久化 ----

    def _log_event(self, event_type: str, level: str, detail: str = None):
        if self.risk_repo:
            try:
                self.risk_repo.log(
                    event_time=datetime.now().isoformat(),
                    event_type=event_type,
                    event_level=level,
                    detail=detail,
                )
            except Exception as e:
                self.logger.error("熔断事件写入失败: %s", e)

    # ---- L1: 个股 ----

    def check_stock(self, pnl_pct: float, close_price: float,
                    ma10: float = None, ma21: float = None) -> FuseLevel:
        """BRT-06: 止损优先级高于均线信号。"""
        if pnl_pct <= self.stock_loss_limit:
            self.logger.warning(
                "L1 熔断触发: 个股亏损 %.1f%% >= %.1f%%",
                abs(pnl_pct * 100), abs(self.stock_loss_limit * 100),
            )
            self.consecutive_stops += 1
            self._log_event(
                "STOCK_LOSS_8PCT", "L1_STOCK",
                f"亏损 {pnl_pct:.2%}，触发 -{abs(self.stock_loss_limit):.0%} 止损",
            )
            return FuseLevel.STOCK_STOP

        if ma21 is not None and close_price < ma21:
            self.logger.warning("L1: 跌破 MA21，触发清仓")
            self._log_event(
                "MA21_BREAK", "L1_STOCK",
                f"收盘价 {close_price} < MA21 {ma21}",
            )
            return FuseLevel.STOCK_STOP

        return FuseLevel.NORMAL

    # ---- L2: 日内/周度 ----

    def check_daily(self, daily_pnl_pct: float,
                    recent_stops: int = None) -> FuseLevel:
        stops = recent_stops if recent_stops is not None else self.consecutive_stops

        if daily_pnl_pct <= self.daily_dd_limit:
            self.logger.warning(
                "L2 熔断触发: 日回撤 %.1f%%", abs(daily_pnl_pct * 100),
            )
            self._log_event(
                "DAILY_DD_3PCT", "L2_DAILY",
                f"日回撤 {daily_pnl_pct:.2%}",
            )
            return FuseLevel.DAILY_BAN

        if stops >= self.consecutive_stop_limit:
            self.logger.warning(
                "L2 熔断触发: 连续 %d 次止损", stops,
            )
            self._log_event(
                "CONSECUTIVE_STOP", "L2_DAILY",
                f"连续 {stops} 次止损",
            )
            return FuseLevel.DAILY_BAN

        return FuseLevel.NORMAL

    def check_weekly(self, weekly_pnl_pct: float) -> FuseLevel:
        if weekly_pnl_pct <= self.weekly_dd_limit:
            self.logger.warning(
                "L2 熔断触发: 周回撤 %.1f%%", abs(weekly_pnl_pct * 100),
            )
            self._log_event(
                "WEEKLY_DD_5PCT", "L2_WEEKLY",
                f"周回撤 {weekly_pnl_pct:.2%}",
            )
            return FuseLevel.WEEKLY_BAN
        return FuseLevel.NORMAL

    # ---- L3: 月度 ----

    def check_monthly(self, monthly_pnl_pct: float) -> FuseLevel:
        if monthly_pnl_pct <= self.monthly_dd_limit:
            self.logger.warning(
                "L3 熔断触发: 月回撤 %.1f%%", abs(monthly_pnl_pct * 100),
            )
            self._log_event(
                "MONTHLY_DD_10PCT", "L3_MONTHLY",
                f"月回撤 {monthly_pnl_pct:.2%}",
            )
            return FuseLevel.MONTHLY_BAN
        return FuseLevel.NORMAL

    def reset_consecutive_stops(self):
        self.consecutive_stops = 0

    @staticmethod
    def is_blocked(level: FuseLevel) -> bool:
        """BRT-05: 熔断状态下禁止开仓。"""
        return level in (FuseLevel.DAILY_BAN, FuseLevel.WEEKLY_BAN,
                         FuseLevel.MONTHLY_BAN)

    # ---- P0-2: Dashboard 读取熔断状态 ----

    def current_fuse_level(self) -> str:
        """从 risk_event 表读取最近一次熔断状态（供 Dashboard 使用）。"""
        if self.risk_repo:
            events = self.risk_repo.get_recent(limit=1)
            if events:
                level_map = {
                    "L1_STOCK": "STOCK_STOP",
                    "L2_DAILY": "DAILY_BAN",
                    "L2_WEEKLY": "WEEKLY_BAN",
                    "L3_MONTHLY": "MONTHLY_BAN",
                }
                return level_map.get(
                    events[0].get("event_level", ""), "NORMAL"
                )
        return "NORMAL"
