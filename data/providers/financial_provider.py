# data/providers/financial_provider.py — 财务数据 Provider
import akshare as ak
import pandas as pd
from data.providers.base import BaseProvider


class FinancialProvider(BaseProvider):
    """个股财务数据：营收增速、净利润增速、ROE、流通市值。"""

    def fetch_financials(self, code: str) -> dict:
        """返回最近季度财务指标。"""
        return self.fetch_with_retry(self._do_fetch_financials, code)

    def _do_fetch_financials(self, code: str) -> dict:
        result = {
            "revenue_yoy": None,
            "profit_yoy": None,
            "roe": None,
            "gross_margin": None,
        }
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code)
            if df is not None and len(df) > 0:
                row = df.iloc[0].to_dict()
                result["roe"] = self._safe_float(row.get("净资产收益率"))
                result["gross_margin"] = self._safe_float(
                    row.get("销售毛利率")
                )
        except Exception as e:
            self.logger.warning(f"{code} 财务指标拉取失败: {e}")

        try:
            df2 = ak.stock_profit_sheet_by_report_em(symbol=code)
            if df2 is not None and len(df2) >= 2:
                latest = df2.iloc[0].to_dict()
                prev = df2.iloc[1].to_dict()
                rev_latest = self._safe_float(latest.get("营业总收入"))
                rev_prev = self._safe_float(prev.get("营业总收入"))
                net_latest = self._safe_float(
                    latest.get("归属于母公司所有者的净利润")
                )
                net_prev = self._safe_float(
                    prev.get("归属于母公司所有者的净利润")
                )
                if rev_prev and rev_prev != 0:
                    result["revenue_yoy"] = round(
                        (rev_latest - rev_prev) / abs(rev_prev), 4
                    )
                if net_prev and net_prev != 0:
                    result["profit_yoy"] = round(
                        (net_latest - net_prev) / abs(net_prev), 4
                    )
        except Exception as e:
            self.logger.warning(f"{code} 利润表拉取失败: {e}")

        self.logger.info(f"{code} 财务数据拉取成功")
        return result

    def fetch_market_cap(self, code: str) -> float | None:
        """返回流通市值（亿）。"""
        try:
            info = ak.stock_individual_info_em(symbol=code)
            if info is not None:
                row = info.set_index("item")
                if "流通市值" in row.index:
                    val = row.loc["流通市值", "value"]
                    if isinstance(val, str):
                        val = float(val.replace(",", "").replace("亿", ""))
                    return float(val) / 1e8  # 转换为亿
        except Exception as e:
            self.logger.warning(f"{code} 市值拉取失败: {e}")
        return None

    @staticmethod
    def _safe_float(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
