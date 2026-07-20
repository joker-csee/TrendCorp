# engine/scanner/scanner.py — B-1 板块扫描流程编排
import logging
from datetime import date, timedelta
from dataclasses import dataclass

import pandas as pd

from config import ScannerConfig
from data.providers.market_provider import MarketProvider
from engine.scanner import trend, rel_strength, fund_flow, echelon


@dataclass
class SectorScanResult:
    sector_code: str
    sector_name: str
    sec_type: str
    trend_score: float
    rel_strength: float
    fund_score: float
    echelon_score: float
    total_score: float
    # 原始指标
    ma5: float = None
    ma10: float = None
    ma21: float = None
    ma55: float = None
    ret_20d: float = None
    hs300_ret_20d: float = None
    fund_flow_5d: float = None
    limit_up_cnt: int = None
    volume_ratio: float = None


class MarketScanner:
    """B-1 板块扫描器。遍历全市场板块，组装四个维度评分。"""

    def __init__(self, market: MarketProvider, weights: dict = None,
                 threshold: float = 0.6):
        self.market = market
        self.weights = weights or {
            "trend": 0.35, "rel_strength": 0.25,
            "fund": 0.25, "echelon": 0.15,
        }
        self.threshold = threshold
        self.logger = logging.getLogger("app.scanner")

    def scan_all(self, scan_date: date) -> list[SectorScanResult]:
        sectors = self._load_active_sectors()
        hs300_ret = self._get_hs300_return(scan_date)
        results = []

        for _, sec in sectors.iterrows():
            try:
                result = self._scan_one(sec, scan_date, hs300_ret)
                if result is not None:
                    results.append(result)
            except Exception as e:
                self.logger.warning(
                    "板块 %s 扫描失败: %s", sec.get("code"), e
                )

        results.sort(key=lambda r: r.total_score, reverse=True)
        self.logger.info(
            "扫描完成: 全市场 %d 个板块 → %d 个候选 (threshold=%.2f)",
            len(sectors), len(results), self.threshold,
        )
        return results

    def _scan_one(self, sec, scan_date: date, hs300_ret: float
                  ) -> SectorScanResult | None:
        code = str(sec["code"])
        name = str(sec["name"])
        sec_type = str(sec["type"])
        start = scan_date - timedelta(days=80)

        df = self.market.fetch_sector_daily(code, sec_type, start, scan_date)
        if len(df) < 20:
            return None

        latest = df.iloc[-1]
        ret_20d = (latest["close"] - df.iloc[-20]["close"]) / abs(df.iloc[-20]["close"]) if len(df) >= 20 else 0.0

        t = trend.calc_trend_score(
            latest.get("ma5"), latest.get("ma10"),
            latest.get("ma21"), latest.get("ma55"),
        )
        r = rel_strength.calc_rel_strength(ret_20d, hs300_ret)
        ff = self.market.fetch_sector_fund_flow(code)
        vr = self._estimate_volume_ratio(df)
        f = fund_flow.calc_fund_score(ff, vr)
        e = echelon.calc_echelon_score(
            self._count_limit_ups(df), int(latest.get("close", 0)) > 0
        )

        total = (t * self.weights["trend"] + r * self.weights["rel_strength"] +
                 f * self.weights["fund"] + e * self.weights["echelon"])

        if total < self.threshold:
            return None

        return SectorScanResult(
            sector_code=code, sector_name=name, sec_type=sec_type,
            trend_score=t, rel_strength=r, fund_score=f, echelon_score=e,
            total_score=round(total, 4),
            ma5=latest.get("ma5"), ma10=latest.get("ma10"),
            ma21=latest.get("ma21"), ma55=latest.get("ma55"),
            ret_20d=round(ret_20d, 4), hs300_ret_20d=round(hs300_ret, 4),
            fund_flow_5d=ff, limit_up_cnt=self._count_limit_ups(df),
            volume_ratio=round(vr, 4),
        )

    def _load_active_sectors(self) -> pd.DataFrame:
        try:
            return self.market.fetch_all_sectors()
        except Exception:
            self.logger.warning("实时拉取板块失败，尝试使用缓存")
            raise

    def _get_hs300_return(self, scan_date: date) -> float:
        try:
            df = self.market.fetch_index_daily(
                "000300", scan_date - timedelta(days=80), scan_date
            )
            if len(df) >= 20:
                return (df.iloc[-1]["close"] - df.iloc[-20]["close"]) / abs(df.iloc[-20]["close"])
        except Exception as e:
            self.logger.warning("沪深300 拉取失败: %s", e)
        return 0.0

    @staticmethod
    def _count_limit_ups(df: pd.DataFrame, days: int = 5) -> int:
        if "close" not in df.columns or len(df) < days:
            return 0
        recent = df.tail(days)
        count = 0
        for i in range(1, len(recent)):
            prev_close = recent.iloc[i - 1]["close"]
            curr_close = recent.iloc[i]["close"]
            if prev_close and prev_close > 0 and (curr_close - prev_close) / prev_close >= 0.095:
                count += 1
        return count

    @staticmethod
    def _estimate_volume_ratio(df: pd.DataFrame, days: int = 5) -> float:
        """板块成交额近 5 日均值 / 近 20 日均值（简化版成交占比替代）。"""
        if "amount" not in df.columns or len(df) < 20:
            return 1.0
        avg5 = df["amount"].tail(days).mean()
        avg20 = df["amount"].tail(20).mean()
        if avg20 == 0:
            return 1.0
        return avg5 / avg20
