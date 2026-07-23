# engine/theme_monitor.py — B-3 主线退潮预警器
import logging
from datetime import date, timedelta

from data.providers.market_provider import MarketProvider


class ThemeMonitor:
    """B-3 退潮预警：4 项信号，≥2 项触发 → 减仓，≥3 项 → 退出。"""

    def __init__(self, market: MarketProvider):
        self.market = market
        self.logger = logging.getLogger("app.theme_monitor")

    def check(self, sector_code: str, sec_type: str, check_date: date,
              core_codes: list[str] = None) -> dict:
        """返回 {alert_level: 0|1|2, triggers: [...]}。

        P1-5 修复: core_codes 用于检查第4条件（中军放量长阴）。
        """
        triggers = []

        # 1. 连续 3 天跑输沪深 300
        if self._underperforming(sector_code, sec_type, check_date):
            triggers.append("连续跑输沪深300")

        # 2. 涨停家数不足
        if self._limit_up_scarce(sector_code, sec_type, check_date):
            triggers.append("涨停家数<2")

        # 3. 成交额萎缩
        if self._volume_shrinking(sector_code, sec_type, check_date):
            triggers.append("成交萎缩>40%")

        # 4. 中军放量长阴 — P1-5: M3 实现
        # FIXME(M4): 需要 Workflow 传入中军标的列表（当前从持仓推断）
        if core_codes:
            if self._core_crash_detected(core_codes, check_date):
                triggers.append("中军放量长阴")

        cnt = len(triggers)
        alert_level = 0
        if cnt >= 3:
            alert_level = 2
        elif cnt >= 2:
            alert_level = 1

        if alert_level > 0:
            self.logger.info(
                "板块 %s 退潮预警: level=%d, triggers=%s",
                sector_code, alert_level, triggers,
            )

        return {"alert_level": alert_level, "triggers": triggers}

    def _core_crash_detected(self, codes: list[str], check_date) -> bool:
        """检查持仓中是否有放量长阴（跌幅>5%+量>20日均量的2倍）。"""
        from datetime import timedelta
        for code in codes:
            try:
                start = check_date - timedelta(days=30)
                df = self.market.fetch_stock_daily(code, start, check_date)
                if len(df) < 2:
                    continue
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                pct = (latest["close"] - prev["close"]) / prev["close"]
                avg_vol_20 = df["volume"].tail(20).mean() if "volume" in df.columns else 0
                if pct <= -0.05 and avg_vol_20 > 0 and latest.get("volume", 0) > avg_vol_20 * 2:
                    return True
            except Exception:
                continue
        return False

    def _underperforming(self, code, sec_type, check_date) -> bool:
        try:
            end = check_date
            start = end - timedelta(days=10)
            df = self.market.fetch_sector_daily(code, sec_type, start, end)
            hs300 = self.market.fetch_index_daily("000300", start, end)
            if len(df) < 3 or len(hs300) < 3:
                return False
            sec_ret = (df.iloc[-1]["close"] - df.iloc[-3]["close"]) / abs(df.iloc[-3]["close"])
            idx_ret = (hs300.iloc[-1]["close"] - hs300.iloc[-3]["close"]) / abs(hs300.iloc[-3]["close"])
            return sec_ret < idx_ret
        except Exception:
            return False

    def _limit_up_scarce(self, code, sec_type, check_date) -> bool:
        try:
            df = self.market.fetch_sector_daily(code, sec_type,
                                                check_date - timedelta(days=30),
                                                check_date)
            if len(df) < 5:
                return False
            recent = df.tail(5)
            cnt = 0
            for i in range(1, len(recent)):
                prev = recent.iloc[i - 1]["close"]
                curr = recent.iloc[i]["close"]
                if prev > 0 and (curr - prev) / prev >= 0.095:
                    cnt += 1
            return cnt < 2
        except Exception:
            return False

    def _volume_shrinking(self, code, sec_type, check_date) -> bool:
        try:
            df = self.market.fetch_sector_daily(code, sec_type,
                                                check_date - timedelta(days=40),
                                                check_date)
            if len(df) < 20 or "amount" not in df.columns:
                return False
            avg20 = df["amount"].tail(20).mean()
            avg5 = df["amount"].tail(5).mean()
            return avg20 > 0 and (avg5 / avg20) < 0.6
        except Exception:
            return False
