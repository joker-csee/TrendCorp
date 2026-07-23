# journal/monthly_report.py — F-2 月度绩效归因
import logging
from datetime import date


class MonthlyReport:
    """F-2: 月度绩效统计 + 按板块/买点归因。"""

    def __init__(self, trade_repo, nav_repo, sector_repo=None):
        self.trade_repo = trade_repo
        self.nav_repo = nav_repo
        self.sector_repo = sector_repo
        self.logger = logging.getLogger("app.monthly_report")

    def generate(self, year: int = None, month: int = None) -> dict:
        """生成月度归因报告。"""
        if year is None:
            year = date.today().year
        if month is None:
            month = date.today().month

        # 交易统计
        stats = self.trade_repo.get_monthly_stats(year, month)

        # 违规检查
        violations = self._count_violations(year, month)

        # 净值统计
        nav_history = self.nav_repo.get_history(31)
        monthly_ret = None
        if len(nav_history) >= 2:
            first = nav_history[0]["total_value"]
            last = nav_history[-1]["total_value"]
            if first > 0:
                monthly_ret = round((last - first) / first, 4)

        report = {
            "year": year, "month": month,
            "trade_count": stats.get("count", 0),
            "win_rate": round((stats.get("win_rate", 0) or 0) * 100, 1),
            "avg_return": round((stats.get("avg_return", 0) or 0) * 100, 2),
            "monthly_return": round((monthly_ret or 0) * 100, 2),
            "violation_count": violations,
            "summary": self._summarize(stats, violations, monthly_ret),
        }

        self.logger.info(
            "月度报告 %d-%02d: %d笔 胜率%.1f%% 月收益%+.2f%% 违规%d次",
            year, month, report["trade_count"], report["win_rate"],
            report["monthly_return"], violations,
        )
        return report

    def _count_violations(self, year: int, month: int) -> int:
        prefix = f"{year}-{month:02d}"
        try:
            trades = self.trade_repo.get_all(limit=200)
            return sum(
                1 for t in trades
                if (t.get("open_date") or "").startswith(prefix)
                and t.get("rule_compliant") == 0
            )
        except Exception:
            return 0

    @staticmethod
    def _summarize(stats, violations, monthly_ret) -> str:
        parts = []
        cnt = stats.get("count", 0)
        if cnt == 0:
            parts.append("本月无交易")
        else:
            wr = round((stats.get("win_rate", 0) or 0) * 100, 1)
            parts.append(f"{cnt}笔交易, 胜率{wr}%")
        if monthly_ret is not None:
            parts.append(f"月收益{round(monthly_ret * 100, 1):+.1f}%")
        if violations > 0:
            parts.append(f"⚠️ 违规{violations}次")
        else:
            parts.append("无违规操作")
        return "; ".join(parts)
