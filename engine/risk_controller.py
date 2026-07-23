# engine/risk_controller.py — E-1 三级熔断器
import logging
from enum import Enum


class FuseLevel(Enum):
    NORMAL = "NORMAL"            # 正常
    STOCK_STOP = "STOCK_STOP"    # L1: 个股止损
    DAILY_BAN = "DAILY_BAN"      # L2: 日内禁开新仓
    WEEKLY_BAN = "WEEKLY_BAN"    # L2: 本周禁开新仓
    MONTHLY_BAN = "MONTHLY_BAN"  # L3: 月度熔断


class RiskController:
    """E-1 三级熔断器。权限最高，输出是强制性的。"""

    def __init__(self, stock_loss_limit: float = -0.08,
                 daily_dd_limit: float = -0.03,
                 weekly_dd_limit: float = -0.05,
                 monthly_dd_limit: float = -0.10,
                 strategy_dd_limit: float = -0.15,
                 consecutive_stop_limit: int = 2):
        self.stock_loss_limit = stock_loss_limit
        self.daily_dd_limit = daily_dd_limit
        self.weekly_dd_limit = weekly_dd_limit
        self.monthly_dd_limit = monthly_dd_limit
        self.strategy_dd_limit = strategy_dd_limit
        self.consecutive_stop_limit = consecutive_stop_limit
        self.consecutive_stops = 0
        self.logger = logging.getLogger("app.risk_ctrl")

    def check_stock(self, pnl_pct: float, close_price: float,
                    ma10: float = None, ma21: float = None) -> FuseLevel:
        """L1: 个股级检查。BRT-06: 止损优先级高于均线信号。"""
        if pnl_pct <= self.stock_loss_limit:
            self.logger.warning(
                "L1 熔断触发: 个股亏损 %.1f%% >= %.1f%%",
                abs(pnl_pct * 100), abs(self.stock_loss_limit * 100),
            )
            self.consecutive_stops += 1
            return FuseLevel.STOCK_STOP

        if ma21 is not None and close_price < ma21:
            self.logger.warning("L1: 跌破 MA21，触发清仓")
            return FuseLevel.STOCK_STOP

        return FuseLevel.NORMAL

    def check_daily(self, daily_pnl_pct: float,
                    recent_stops: int = None) -> FuseLevel:
        """L2: 日内/周度级检查。"""
        stops = recent_stops if recent_stops is not None else self.consecutive_stops

        if daily_pnl_pct <= self.daily_dd_limit:
            self.logger.warning(
                "L2 熔断触发: 日回撤 %.1f%%", abs(daily_pnl_pct * 100),
            )
            return FuseLevel.DAILY_BAN

        if stops >= self.consecutive_stop_limit:
            self.logger.warning(
                "L2 熔断触发: 连续 %d 次止损", stops,
            )
            return FuseLevel.DAILY_BAN

        return FuseLevel.NORMAL

    def check_weekly(self, weekly_pnl_pct: float) -> FuseLevel:
        if weekly_pnl_pct <= self.weekly_dd_limit:
            self.logger.warning(
                "L2 熔断触发: 周回撤 %.1f%%", abs(weekly_pnl_pct * 100),
            )
            return FuseLevel.WEEKLY_BAN
        return FuseLevel.NORMAL

    def check_monthly(self, monthly_pnl_pct: float) -> FuseLevel:
        if monthly_pnl_pct <= self.monthly_dd_limit:
            self.logger.warning(
                "L3 熔断触发: 月回撤 %.1f%%", abs(monthly_pnl_pct * 100),
            )
            return FuseLevel.MONTHLY_BAN
        return FuseLevel.NORMAL

    def reset_consecutive_stops(self):
        self.consecutive_stops = 0

    def is_blocked(self, level: FuseLevel) -> bool:
        """BRT-05: 熔断状态下禁止开仓。"""
        return level in (FuseLevel.DAILY_BAN, FuseLevel.WEEKLY_BAN,
                         FuseLevel.MONTHLY_BAN)
