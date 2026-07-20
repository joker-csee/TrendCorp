# engine/ma_monitor.py — C-2 均线状态监控器 + A/B 级买卖点信号
import logging
from datetime import date, timedelta
from enum import Enum

from data.providers.market_provider import MarketProvider


class SignalType(Enum):
    A_BUY = "A_BUY"        # MA10 回踩企稳（最佳买点）
    B_BUY = "B_BUY"        # 板块共振启动（可用买点）
    HOLD = "HOLD"          # 继续持有
    REDUCE = "REDUCE"      # 跌破 MA10 — 减半仓
    EXIT = "EXIT"          # 跌破 MA21 — 清仓


class MAMonitor:
    """C-2 均线状态监控器。对每只中军/持仓输出信号。"""

    def __init__(self, market: MarketProvider):
        self.market = market
        self.logger = logging.getLogger("app.ma_monitor")

    def check(self, stock_code: str, snap_date: date,
              candle_type: str = "small_bull",
              # P1-4 修复: 增加板块共振参数
              sector_resonance: bool = False) -> dict:
        """返回 {signal, ma10, ma21, ma_deviation, price}。

        sector_resonance: 板块内 ≥3 只标的同步放量时设为 True。
        FIXME(M3): 当前由调用方（Workflow）传入，M2 无 Workflow 时默认 False。
        """
        start = snap_date - timedelta(days=80)
        df = self.market.fetch_stock_daily(stock_code, start, snap_date)
        if len(df) < 20:
            return {"signal": None, "error": "数据不足"}

        latest = df.iloc[-1]
        price = latest.get("close")
        ma10 = latest.get("ma10")
        ma21 = latest.get("ma21")
        vol = latest.get("volume", 0)
        vol_5m = df["volume"].tail(5).mean() if "volume" in df.columns else 0

        deviation = None
        if ma10 and ma10 != 0:
            deviation = (price - ma10) / ma10

        signal = self._determine_signal(price, ma10, ma21, deviation,
                                        vol, vol_5m, candle_type,
                                        sector_resonance)
        return {
            "signal": signal,
            "price": price,
            "ma10": ma10,
            "ma21": ma21,
            "ma_deviation": round(deviation, 4) if deviation else None,
            "vol_ratio_5d": round(vol / vol_5m, 4) if vol_5m > 0 else None,
        }

    def _determine_signal(self, price, ma10, ma21, deviation,
                          vol, vol_5m, candle_type,
                          sector_resonance: bool) -> SignalType | None:
        if price is None:
            return None

        # A级买点: 距 MA10 < 3% + 缩量 + 小阳/十字星
        if (ma10 and deviation is not None and abs(deviation) < 0.03
                and vol_5m > 0 and vol / vol_5m < 0.6
                and candle_type in ("small_bull", "doji")):
            return SignalType.A_BUY

        # P1-4 修复: B级买点需要板块共振条件
        if (ma10 and deviation is not None and 0.03 <= deviation < 0.08
                and vol_5m > 0 and vol / vol_5m > 1.5
                and sector_resonance):
            return SignalType.B_BUY

        # 止损信号
        if ma21 and price < ma21:
            return SignalType.EXIT
        if ma10 and price < ma10:
            return SignalType.REDUCE

        return SignalType.HOLD
