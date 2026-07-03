# data/providers/announcement_provider.py — 公告数据 Provider
import akshare as ak
import pandas as pd
from datetime import date, timedelta
from data.providers.base import BaseProvider


class AnnouncementProvider(BaseProvider):
    """业绩预告、重大合同公告拉取。"""

    def fetch_performance_forecast(
        self, lookback_days: int = 7
    ) -> list[dict]:
        """最近 N 天的业绩预告。"""
        return self.fetch_with_retry(
            self._do_fetch_performance_forecast, lookback_days
        )

    def _do_fetch_performance_forecast(
        self, lookback_days: int
    ) -> list[dict]:
        try:
            df = ak.stock_yjyg_em(date="".join(
                str(date.today()).split("-")[:3]
            ).replace("-", ""))
            if df is None or len(df) == 0:
                self.logger.info("最近无业绩预告")
                return []
            results = []
            today = pd.Timestamp.now().normalize()
            cutoff = today - timedelta(days=lookback_days)
            for _, row in df.iterrows():
                try:
                    notice_date = pd.Timestamp(row.get("公告日期"))
                    if notice_date >= cutoff:
                        results.append({
                            "stock_code": str(row.get("股票代码", "")),
                            "stock_name": str(row.get("股票简称", "")),
                            "forecast_type": str(row.get("预告类型", "")),
                            "notice_date": str(notice_date.date()),
                            "profit_range": str(row.get("预计净利润", "")),
                        })
                except Exception:
                    continue
            self.logger.info(f"业绩预告拉取成功，{len(results)} 条")
            return results
        except Exception as e:
            self.logger.warning(f"业绩预告拉取失败: {e}")
            return []
