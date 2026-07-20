# data/providers/market_provider.py — 行情数据 Provider
import pandas as pd
from datetime import date, timedelta
import akshare as ak
from data.providers.base import BaseProvider


class MarketProvider(BaseProvider):
    """板块/个股日K、均线、资金流、成交额、指数行情。"""

    # ---- 板块 ----

    def fetch_all_sectors(self) -> pd.DataFrame:
        """获取东方财富行业板块 + 概念板块列表。返回 [code, name, type]"""
        frames = []

        # 东方财富行业板块（P0-1 修复: 使用正确 API）
        try:
            sw = self.fetch_with_retry(ak.stock_board_industry_name_em)
            sw = sw.rename(columns={"板块代码": "code", "板块名称": "name"})
            sw["type"] = "industry"
            frames.append(sw[["code", "name", "type"]])
        except Exception as e:
            self.logger.warning(f"行业板块拉取失败: {e}")

        # 概念板块（P0-3 修复: 使用 fetch_with_retry）
        try:
            gn = self.fetch_with_retry(ak.stock_board_concept_name_em)
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
        self, code: str, sec_type: str, start: date, end: date
    ) -> pd.DataFrame:
        """板块日K（OHLCV），自动计算 MA5/10/21/55。

        P0-2 修复: 新增 sec_type 参数，根据板块类型路由到不同 API。
        """
        return self.fetch_with_retry(
            self._do_fetch_sector_daily, code, sec_type, start, end
        )

    def _do_fetch_sector_daily(
        self, code: str, sec_type: str, start: date, end: date
    ) -> pd.DataFrame:
        if sec_type == "concept":
            df = ak.stock_board_concept_hist_em(
                symbol=code, period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust=""
            )
        else:
            df = ak.stock_board_industry_hist_em(
                symbol=code, period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust=""
            )
        return self._normalize_ohlcv(df, label=f"板块 {code}")

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
        return self._normalize_ohlcv(df, label=f"个股 {code}")

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
        # P2-5 修复: 统一列重命名
        return self._normalize_ohlcv(df, label=f"指数 {index_code}",
                                     date_col="date", has_volume=True)

    # ---- 资金流 ----

    def fetch_sector_fund_flow(self, code: str, days: int = 5) -> float:
        """板块近 N 日主力净流入（亿元）。"""
        for indicator in ("今日", "5日"):
            for sec_type in ("概念板块", "行业板块"):
                try:
                    df = ak.stock_sector_fund_flow_rank(
                        indicator=indicator, sector_type=sec_type
                    )
                    if code in df["代码"].values:
                        val = float(
                            df.loc[df["代码"] == code, "主力净流入"].values[0]
                        )
                        self.logger.debug(
                            f"板块 {code} 资金流({indicator}/{sec_type}): {val}"
                        )
                        return val
                except Exception:
                    continue
        self.logger.warning(f"板块 {code} 资金流拉取失败（所有来源）")
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
            df[col] = df["close"].rolling(
                window=w, min_periods=max(1, w // 2)
            ).mean()
        return df

    @staticmethod
    def _normalize_ohlcv(
        df: pd.DataFrame, label: str = "",
        date_col: str = "日期", has_volume: bool = True
    ) -> pd.DataFrame:
        """P2-5 修复: 统一列重命名 + 均线计算。"""
        col_map = {
            date_col: "date",
            "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close",
        }
        if has_volume:
            col_map.update({"成交量": "volume", "成交额": "amount"})

        df = df.rename(columns={k: v for k, v in col_map.items()
                                if k in df.columns})
        keep = [v for v in col_map.values() if v in df.columns]
        df = df[keep].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df = MarketProvider._add_mas(df)
        if label:
            import logging
            logging.getLogger("MarketProvider").info(
                f"{label} 日K拉取成功，{len(df)} 行"
            )
        return df
