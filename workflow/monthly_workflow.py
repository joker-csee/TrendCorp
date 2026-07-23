# workflow/monthly_workflow.py — 月度绩效报告
from datetime import date

from workflow.base import BaseWorkflow
from repositories.trade_repository import TradeRepository
from repositories.nav_repository import NavRepository


class MonthlyWorkflow(BaseWorkflow):
    """月末执行：生成月度归因报告 + 统计。"""

    def __init__(self, trade_repo: TradeRepository,
                 nav_repo: NavRepository):
        super().__init__()
        self.trade_repo = trade_repo
        self.nav_repo = nav_repo

    def execute(self):
        today = date.today()
        year, month = today.year, today.month

        self.logger.info("生成 %d-%02d 月度报告", year, month)

        # 交易统计
        stats = self.trade_repo.get_monthly_stats(year, month)

        # 净值统计
        nav_history = self.nav_repo.get_history(31)

        self.logger.info(
            "月度报告: %d笔交易, 胜率 %.1f%%, 均收益 %+.2f%%",
            stats.get("count", 0),
            (stats.get("win_rate", 0) or 0) * 100,
            (stats.get("avg_return", 0) or 0) * 100,
        )

        return {
            "year": year,
            "month": month,
            "trade_count": stats.get("count", 0),
            "win_rate": stats.get("win_rate", 0),
            "avg_return": stats.get("avg_return", 0),
            "nav_points": len(nav_history),
        }
