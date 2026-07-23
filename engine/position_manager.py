# engine/position_manager.py — D-1 仓位管理器
import logging
from enum import Enum


class TradeDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrder:
    def __init__(self, stock_code: str, direction: TradeDirection,
                 target_pct: float, price_type: str,
                 limit_price: float | None = None):
        self.stock_code = stock_code
        self.direction = direction
        self.target_pct = target_pct
        self.price_type = price_type
        self.limit_price = limit_price

    def __repr__(self):
        return (f"TradeOrder({self.direction.value} {self.stock_code} "
                f"{self.target_pct:.1%} @{self.price_type})")


class PositionManager:
    """D-1 仓位管理器。"""

    def __init__(self, total_cap: float = 0.70, single_cap: float = 0.30,
                 sector_cap: float = 0.35, cash_min: float = 0.30,
                 a_buy_first: float = 0.50, b_buy_first: float = 0.30):
        self.total_cap = total_cap
        self.single_cap = single_cap
        self.sector_cap = sector_cap
        self.cash_min = cash_min
        self.a_buy_first = a_buy_first
        self.b_buy_first = b_buy_first
        self.logger = logging.getLogger("app.position_mgr")

    # P1-3 修复: 新增 fuse_level 参数，内部检查熔断
    def calc_buy(self, signal: str, stock_code: str,
                 current_stock_pct: float, current_total_pct: float,
                 current_sector_pct: float = 0.0,
                 ma10: float = None,
                 fuse_level=None) -> 'TradeOrder | None':
        """计算建仓指令。fuse_level 不为 NORMAL 时禁止开仓。"""
        # P1-3: 熔断时内部拒绝，不再依赖调用方
        from engine.risk_controller import FuseLevel, RiskController
        if fuse_level is not None and RiskController.is_blocked(fuse_level):
            self.logger.warning(
                "风控熔断状态 %s，禁止开仓", fuse_level.value
            )
            return None

        if current_total_pct >= self.total_cap:
            self.logger.warning(
                "总仓位已达上限 %.0f%%，拒绝开仓 %s",
                self.total_cap * 100, stock_code,
            )
            return None

        if current_stock_pct >= self.single_cap:
            self.logger.warning(
                "单票仓位已达上限 %.0f%%，拒绝加仓 %s",
                self.single_cap * 100, stock_code,
            )
            return None

        if signal == "A_BUY":
            target_pct = self.single_cap * self.a_buy_first
        elif signal == "B_BUY":
            target_pct = self.single_cap * self.b_buy_first
        else:
            return None

        # 裁剪：总仓位上限
        room_total = self.total_cap - current_total_pct
        if target_pct > room_total:
            old = target_pct
            target_pct = room_total
            # P2-2: 裁剪日志使用 WARNING
            self.logger.warning(
                "总仓位将触及上限 %d%%，建仓比例从 %.1f%% 调整为 %.1f%%",
                int(self.total_cap * 100), old * 100, target_pct * 100,
            )

        # 裁剪：单票上限
        room_single = self.single_cap - current_stock_pct
        if target_pct > room_single:
            target_pct = room_single

        # 裁剪：单板块上限
        room_sector = self.sector_cap - current_sector_pct
        if target_pct > room_sector:
            target_pct = room_sector

        # BRT-08: 最低现金保留
        after_buy = current_total_pct + target_pct
        max_allowed = 1.0 - self.cash_min
        if after_buy > max_allowed:
            old = target_pct
            target_pct = max_allowed - current_total_pct
            if target_pct <= 0:
                self.logger.warning(
                    "最低现金限制（%.0f%%），无法开仓", self.cash_min * 100
                )
                return None
            self.logger.info(
                "最低现金限制: %.1f%% -> %.1f%%", old * 100, target_pct * 100,
            )

        limit_price = None
        if ma10 is not None:
            limit_price = round(ma10 * 1.005, 2)

        return TradeOrder(
            stock_code=stock_code,
            direction=TradeDirection.BUY,
            target_pct=round(target_pct, 4),
            price_type="LIMIT",
            limit_price=limit_price,
        )

    def calc_sell(self, signal: str, current_stock_pct: float,
                  stock_code: str = "") -> 'TradeOrder | None':
        """计算减仓/清仓指令。

        P1-2 修复: EXIT(M21破位)→MARKET  SECTOR_EXIT(退潮)→LIMIT
        """
        if signal == "REDUCE":
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=round(current_stock_pct * 0.5, 4),
                price_type="LIMIT",
            )
        elif signal == "EXIT":
            # MA21 破位 → 市价清仓（紧急）
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=current_stock_pct,
                price_type="MARKET",
            )
        elif signal == "SECTOR_EXIT":
            # P1-2: 板块退潮 → 限价清仓（非紧急）
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=current_stock_pct,
                price_type="LIMIT",
            )
        elif signal == "STOP_LOSS":
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=current_stock_pct,
                price_type="MARKET",
            )
        return None
