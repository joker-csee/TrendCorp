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
    """D-1 仓位管理器：计算建仓/加仓/减仓比例，执行所有硬上限裁剪。

    硬约束（来自 config.PositionConfig）：
    - total_cap:     总仓位 ≤ 70%
    - single_cap:    单票 ≤ 30%
    - sector_cap:    单板块 ≤ 35%
    - cash_min:      最低现金保留 ≥ 30%
    """

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

    def calc_buy(self, signal: str, stock_code: str,
                 current_stock_pct: float, current_total_pct: float,
                 current_sector_pct: float = 0.0,
                 ma10: float = None) -> TradeOrder | None:
        """计算建仓指令。

        signal: 'A_BUY' | 'B_BUY'
        返回 TradeOrder 或 None（触发限制时）。
        """
        # BRT-05: 熔断时禁止开仓（由调用方在调用前检查）
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

        # 计算目标仓位
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
            self.logger.info(
                "总仓位限制: %.1f%% -> %.1f%%", old * 100, target_pct * 100,
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
                self.logger.warning("最低现金限制（%.0f%%），无法开仓", self.cash_min * 100)
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
                  stock_code: str = "") -> TradeOrder | None:
        """计算减仓/清仓指令。"""
        if signal == "REDUCE":
            sell_pct = current_stock_pct * 0.5  # 减半仓
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=round(sell_pct, 4),
                price_type="LIMIT",
            )
        elif signal in ("EXIT", "STOP_LOSS"):
            return TradeOrder(
                stock_code=stock_code,
                direction=TradeDirection.SELL,
                target_pct=current_stock_pct,  # 全部清仓
                price_type="MARKET",            # 市价单，保命优先
            )
        return None
