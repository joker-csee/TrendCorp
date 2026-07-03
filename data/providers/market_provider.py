# data/providers/market_provider.py — 行情数据 Provider
import pandas as pd
from datetime import date, timedelta
import akshare as ak
from data.providers.base import BaseProvider


class MarketProvider(BaseProvider):
    """板块/个股日K、均线、资金流、成交额、指数行情。"""

    # ---- 板块 ----

    def fetch_all_sectors(self) -> pd.DataFrame:
        """获取申万行业 + 概念板块列表。返回 [code, name, type]"""
        frames = []

        try:
            sw = ak.index_stock_cons_csindex(symbol="000811")
            sw = sw.rename(columns={"成分券代码": "code", "成分券名称": "name"})
            sw["type"] = "sw_industry"
            frames.append(sw[["code", "name", "type"]])
        except Exception as e:
            self.logger.warning(f"申万行业拉取失败: {e}")

        try:
            gn = ak.stock_board_concept_name_em()
            gn = gn.rename(columns={"代码": "code", "板块名称": "name"})
            gn["type"] = "concept"
            frames.append(gn[["code", "name", "type"]])
        except Exception as e:
            self.logger.warning(f"概念板块拉取失败: {e}")

        if not frames:
            raise RuntimeError("所有板块数据源均拉取失败")
        result = pd.concat(frames, ignore_index=True)
        self.logger.info(f"板块列表拉取成功，共 {len(result)} 个")
        return result

    def fetch_sector_daily(
        self, code: str, start: date, end: date
    ) -> pd.DataFrame:
        """板块日K（OHLCV），自动计算 MA5/10/21/55。"""
        return self.fetch_with_retry(
            self._do_fetch_sector_daily, code, start, end
        )

    def _do_fetch_sector_daily(
        self, code: str, start: date, end: date
    ) -> pd.DataFrame:
        df = ak.stock_board_concept_hist_em(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=""
        )
        col_map = {
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns=col_map)
        keep = [c for c in col_map.values() if c in df.columns]
        df = df[keep].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = self._add_mas(df)
        self.logger.info(f"板块 {code} 日K拉取成功，{len(df)} 行")
        return df

    # ---- 个股 ----

    def fetch_stock_daily(
        self, code: str, start: date, end: date
    ) -> pd.DataFrame:
        """个股日K + 均线。"""
        return self.fetch_with_retry(
            self._do_fetch_stock_daily, code, start, end
        )

    def _do_fetch_stock_daily(
        self, code: str, start: date, end: date
    ) -> pd.DataFrame:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq"
        )
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume",
            "成交额": "amount",
        })
        keep = [c for c in
                ["date", "open", "high", "low", "close", "volume", "amount"]
                if c in df.columns]
        df = df[keep].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = self._add_mas(df)
        return df

    # ---- 指数 ----

    def fetch_index_daily(
        self, index_code: str, start: date, end: date
    ) -> pd.DataFrame:
        """指数日K（沪深300等）。"""
        return self.fetch_with_retry(
            self._do_fetch_index_daily, index_code, start, end
        )

    def _do_fetch_index_daily(
        self, index_code: str, start: date, end: date
    ) -> pd.DataFrame:
        df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        mask = (df["date"] >= pd.Timestamp(start)) & (
            df["date"] <= pd.Timestamp(end)
        )
        df = df[mask].copy()
        self.logger.info(f"指数 {index_code} 日K拉取成功，{len(df)} 行")
        return df

    # ---- 资金流 ----

    def fetch_sector_fund_flow(self, code: str, days: int = 5) -> float:
        """板块近 N 日主力净流入（亿元）。"""
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念板块")
            if code in df["代码"].values:
                return float(df.loc[df["代码"] == code, "主力净流入"].values[0])
        except Exception:
            pass
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="5日", sector_type="概念板块")
            if code in df["代码"].values:
                return float(df.loc[df["代码"] == code, "主力净流入"].values[0])
        except Exception as e:
            self.logger.warning(f"板块 {code} 资金流拉取失败: {e}")
        return 0.0

    # ---- 工具 ----

    @staticmethod
    def _add_mas(df: pd.DataFrame) -> pd.DataFrame:
        """为 DataFrame 增加 MA5/MA10/MA21/MA55 列。"""
        if "close" not in df.columns or len(df) == 0:
            return df
        df = df.copy()
        for w in [5, 10, 21, 55]:
            col = f"ma{w}"
            df[col] = df["close"].rolling(window=w, min_periods=max(1, w // 2)).mean()
        return df
