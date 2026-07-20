# engine/screener/screener.py — C-1 中军筛选流程编排
import logging
from datetime import date, timedelta
from dataclasses import dataclass

import pandas as pd

from data.providers.market_provider import MarketProvider
from data.providers.financial_provider import FinancialProvider
from engine.screener import (market_cap, liquidity, ma_structure,
                              vol_health, fundamental)


@dataclass
class CoreScoreResult:
    stock_code: str
    stock_name: str
    sector_code: str
    market_cap_score: float
    liquidity_score: float
    ma_structure_score: float
    vol_health_score: float
    fundamental_score: float
    total_score: float
    price: float = None
    ma5: float = None
    ma10: float = None
    ma21: float = None
    ma55: float = None
    ma_deviation: float = None
    vol_ratio_20: float = None
    signal: str = None


class CoreScreener:
    """C-1 中军五维评分筛选器。每个板块最多返回 top_n 只中军。"""

    def __init__(self, market: MarketProvider, financial: FinancialProvider,
                 weights: dict = None, threshold: float = 0.65, top_n: int = 2):
        self.market = market
        self.financial = financial
        self.weights = weights or {
            "market_cap": 0.15, "liquidity": 0.20,
            "ma_structure": 0.25, "vol_health": 0.25,
            "fundamental": 0.15,
        }
        self.threshold = threshold
        self.top_n = top_n
        self.logger = logging.getLogger("app.screener")

    def screen(self, sector_code: str, sector_name: str,
               snap_date: date) -> list[CoreScoreResult]:
        """对板块内所有成分股进行五维评分，返回 top_n。"""
        try:
            stocks = self._get_sector_stocks(sector_code)
        except Exception as e:
            self.logger.warning("板块 %s 成分股获取失败: %s", sector_code, e)
            return []

        results = []
        for _, s in stocks.iterrows():
            try:
                result = self._score_one(s, snap_date)
                if result is not None:
                    results.append(result)
            except Exception as e:
                self.logger.debug("个股 %s 评分跳过: %s", s.get("代码", "?"), e)

        results.sort(key=lambda r: r.total_score, reverse=True)
        top = results[:self.top_n]
        self.logger.info(
            "板块 %s: %d 只成分股 → %d 合格 → 选取 %d 只中军",
            sector_name, len(stocks), len(results), len(top),
        )
        return top

    def _score_one(self, stock_info,
                   snap_date: date) -> CoreScoreResult | None:
        code = str(stock_info.get("代码", ""))
        name = str(stock_info.get("名称", ""))
        sector_code = str(stock_info.get("板块代码", ""))
        if not code or len(code) < 6:
            return None

        # 拉取行情 + 均线
        start = snap_date - timedelta(days=120)
        df = self.market.fetch_stock_daily(code, start, snap_date)
        if len(df) < 30:
            return None
        latest = df.iloc[-1]
        ma5_val = latest.get("ma5")
        ma10_val = latest.get("ma10")
        ma21_val = latest.get("ma21")
        ma55_val = latest.get("ma55")
        price = latest.get("close")

        # 五维评分
        mc = self.financial.fetch_market_cap(code) or 0
        mcs = market_cap.calc_market_cap_score(mc)

        avg_vol = df["volume"].tail(20).mean() if "volume" in df.columns else 0
        liq_rank = self._estimate_rank(code, avg_vol)
        liq = liquidity.calc_liquidity_score(liq_rank)

        mas = ma_structure.calc_ma_structure_score(ma5_val, ma10_val, ma21_val, ma55_val)

        up_avg, dn_avg, pb_vol, pk_vol = self._calc_vol_profile(df)
        vh = vol_health.calc_vol_health_score(up_avg, dn_avg, pb_vol, pk_vol)

        fin = self.financial.fetch_financials(code)
        fund = fundamental.calc_fundamental_score(
            fin.get("revenue_yoy"), fin.get("profit_yoy")
        )

        total = (mcs * self.weights["market_cap"] +
                 liq * self.weights["liquidity"] +
                 mas * self.weights["ma_structure"] +
                 vh * self.weights["vol_health"] +
                 fund * self.weights["fundamental"])

        if total < self.threshold:
            return None

        # MA 偏离度
        dev = None
        if ma10_val and ma10_val != 0:
            dev = round((price - ma10_val) / ma10_val, 4)

        vol_ratio = None
        vol_20m = df["volume"].tail(20).mean() if "volume" in df.columns else 0
        if vol_20m > 0:
            vol_ratio = round(
                (df["volume"].iloc[-1] if "volume" in df.columns else 0) / vol_20m, 4
            )

        return CoreScoreResult(
            stock_code=code, stock_name=name, sector_code=sector_code,
            market_cap_score=round(mcs, 4),
            liquidity_score=round(liq, 4),
            ma_structure_score=round(mas, 4),
            vol_health_score=round(vh, 4),
            fundamental_score=round(fund, 4),
            total_score=round(total, 4),
            price=price, ma5=ma5_val, ma10=ma10_val, ma21=ma21_val, ma55=ma55_val,
            ma_deviation=dev, vol_ratio_20=vol_ratio,
        )

    def _get_sector_stocks(self, sector_code: str) -> pd.DataFrame:
        try:
            return ak.stock_board_concept_cons_em(symbol=sector_code)
        except Exception:
            pass
        try:
            return ak.stock_board_industry_cons_em(symbol=sector_code)
        except Exception:
            pass
        return pd.DataFrame()

    @staticmethod
    def _estimate_rank(code: str, avg_vol: float) -> int:
        # 没有全市场排名的简化实现：返回中等排名
        if avg_vol > 1e9:
            return 3
        if avg_vol > 5e8:
            return 5
        if avg_vol > 1e8:
            return 8
        return 12

    @staticmethod
    def _calc_vol_profile(df: pd.DataFrame):
        if "close" not in df.columns or "volume" not in df.columns:
            return 0, 0, 0, 0
        if len(df) < 20:
            return 0, 0, 0, 0
        up_mask = df["close"].pct_change() > 0
        dn_mask = df["close"].pct_change() < 0
        up_avg = df.loc[up_mask, "volume"].mean() if up_mask.any() else 0
        dn_avg = df.loc[dn_mask, "volume"].mean() if dn_mask.any() else 0
        pb_vol = df["volume"].tail(5).min()
        pk_vol = df["volume"].max()
        return up_avg, dn_avg, pb_vol, pk_vol


# 延迟导入避免循环
import akshare as ak
