# workflow/daily_workflow.py — 日终更新
from datetime import date

from workflow.base import BaseWorkflow
from data.providers.market_provider import MarketProvider
from engine.ma_monitor import MAMonitor
from engine.theme_monitor import ThemeMonitor
from repositories.position_repository import PositionRepository
from repositories.trade_repository import TradeRepository
from repositories.nav_repository import NavRepository
from repositories.sector_repository import SectorRepository


class DailyWorkflow(BaseWorkflow):
    """交易日 15:30 执行：更新行情 → 均线信号 → 退潮预警 → 风控 → 净值快照。"""

    def __init__(self, market: MarketProvider,
                 ma_monitor: MAMonitor,
                 theme_monitor: ThemeMonitor,
                 position_repo: PositionRepository,
                 trade_repo: TradeRepository,
                 nav_repo: NavRepository,
                 sector_repo: SectorRepository,
                 initial_capital: float = 100_000.0):
        super().__init__()
        self.market = market
        self.ma_monitor = ma_monitor
        self.theme_monitor = theme_monitor
        self.position_repo = position_repo
        self.trade_repo = trade_repo
        self.nav_repo = nav_repo
        self.sector_repo = sector_repo
        self.initial_capital = initial_capital

    def execute(self):
        today = date.today()
        snap = today.isoformat()

        # Step 1: 更新持仓行情
        self.logger.info("Step 1/5: 更新持仓标的行情")
        positions = self.position_repo.get_all()
        holdings = []
        for pos in positions:
            try:
                result = self.ma_monitor.check(
                    stock_code=str(pos.get("stock_id", "")),
                    snap_date=today,
                )
                holdings.append({**pos, **result})
            except Exception as e:
                self.logger.warning("持仓 %s 行情更新失败: %s",
                                    pos.get("stock_id"), e)

        # Step 2: 均线信号更新
        self.logger.info("Step 2/5: 均线信号检查")
        for h in holdings:
            sig = h.get("signal")
            if sig is not None:
                sig_str = str(sig).replace("SignalType.", "")
                if sig_str in ("REDUCE", "EXIT"):
                    self.logger.info(
                        "持仓 %s: 触发 %s 信号", h.get("stock_id"), sig_str
                    )

        # Step 3: 退潮预警
        self.logger.info("Step 3/5: 板块退潮预警")
        # 收集持仓涉及的所有板块
        sector_ids = {h.get("sector_id") for h in holdings if h.get("sector_id")}
        for sid in sector_ids:
            sec = self.sector_repo.get_by_id(sid)
            if not sec:
                continue
            try:
                alert = self.theme_monitor.check(
                    sec["code"], sec["type"], today
                )
                if alert["alert_level"] > 0:
                    self.logger.info(
                        "板块 %s 退潮预警: level=%d, triggers=%s",
                        sec["name"], alert["alert_level"], alert["triggers"],
                    )
            except Exception as e:
                self.logger.warning(
                    "板块 %s 退潮检查失败: %s", sec.get("code"), e
                )

        # Step 4: 计算净值
        self.logger.info("Step 4/5: 更新净值快照")
        latest_nav = self.nav_repo.get_latest()
        prev_total = latest_nav["total_value"] if latest_nav else self.initial_capital

        positions_value = sum(
            (h.get("current_price", 0) or 0) * (h.get("shares", 0) or 0)
            for h in holdings
        )
        # 现金 = 总净值 - 持仓市值（简化）
        cash = max(0, prev_total - positions_value)
        total_value = cash + positions_value
        daily_ret = (total_value - prev_total) / prev_total if prev_total > 0 else 0
        pos_pct = positions_value / total_value if total_value > 0 else 0

        # 最大回撤
        history = self.nav_repo.get_history(90)
        peak = prev_total
        for row in history:
            peak = max(peak, row.get("total_value", prev_total))
        mdd = (total_value - peak) / peak if peak > 0 else 0

        self.nav_repo.save_snapshot(
            snap_date=snap,
            total_value=total_value,
            cash=cash,
            positions_value=positions_value,
            daily_return=round(daily_ret, 6),
            max_drawdown=round(mdd, 6),
            position_pct=round(pos_pct, 4),
        )

        # Step 5: 日志摘要
        self.logger.info(
            "Step 5/5: 日终完成 — 总净值 ¥%.0f, 日收益 %+.2f%%, 仓位 %.0f%%, MDD %.1f%%",
            total_value, daily_ret * 100, pos_pct * 100, mdd * 100,
        )
