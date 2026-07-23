# engine/dashboard.py — 终端仪表盘 (M2) + 数据聚合 (M4)
import logging
from datetime import date, timedelta
from dataclasses import dataclass, field

from config import AppConfig
from data.providers.market_provider import MarketProvider
from data.providers.financial_provider import FinancialProvider
from engine.scanner.scanner import MarketScanner
from engine.screener.screener import CoreScreener
from engine.theme_selector import ThemeSelector
from engine.ma_monitor import MAMonitor
from repositories.sector_repository import SectorRepository
from repositories.nav_repository import NavRepository
from repositories.risk_repository import RiskRepository


@dataclass
class DashboardData:
    date: str
    total_nav: float
    daily_return: float
    weekly_return: float
    monthly_return: float
    position_pct: float
    cash: float
    fuse_level: str
    themes: list = field(default_factory=list)
    signals: list = field(default_factory=list)


def build_dashboard(cfg: AppConfig, market: MarketProvider,
                    financial: FinancialProvider, sector_repo: SectorRepository,
                    nav_repo: NavRepository,
                    risk_repo: RiskRepository = None) -> DashboardData:
    """M2 终端仪表盘数据聚合。"""
    logger = logging.getLogger("app.dashboard")
    today = date.today()

    # 净值
    latest_nav = nav_repo.get_latest()
    total_nav = latest_nav["total_value"] if latest_nav else cfg.initial_capital
    cash = latest_nav["cash"] if latest_nav else cfg.initial_capital
    pos_val = latest_nav["positions_value"] if latest_nav else 0
    pos_pct = latest_nav["position_pct"] if latest_nav else 0
    daily = latest_nav.get("daily_return", 0) or 0 if latest_nav else 0
    weekly = latest_nav.get("weekly_return", 0) or 0 if latest_nav else 0
    monthly = latest_nav.get("monthly_return", 0) or 0 if latest_nav else 0

    # P0-2: 从 RiskRepository 读取实际熔断状态
    fuse_level = "NORMAL"
    if risk_repo:
        events = risk_repo.get_recent(limit=1)
        if events:
            level_map = {
                "L1_STOCK": "STOCK_STOP",
                "L2_DAILY": "DAILY_BAN",
                "L2_WEEKLY": "WEEKLY_BAN",
                "L3_MONTHLY": "MONTHLY_BAN",
            }
            fuse_level = level_map.get(
                events[0].get("event_level", ""), "NORMAL"
            )

    # P0-2 修复: 主线扫描异常时生成降级面板
    scanner = MarketScanner(market, cfg.scanner.weights, cfg.scanner.candidate_threshold)
    try:
        scan_results = scanner.scan_all(today)
    except RuntimeError as e:
        logger.warning("主线扫描失败（数据不可用），生成降级面板: %s", e)
        return DashboardData(
            date=str(today), total_nav=total_nav, daily_return=daily,
            weekly_return=weekly, monthly_return=monthly,
            position_pct=pos_pct, cash=cash,
            fuse_level=fuse_level,
            themes=[], signals=[],
        )

    selector = ThemeSelector(cfg.scanner.confirmed_min_score)
    classified = selector.confirm(scan_results)
    themes = classified["confirmed"]

    # 中军筛选 + 信号
    screener = CoreScreener(market, financial, cfg.screener.weights,
                            cfg.screener.score_threshold, cfg.screener.top_n_per_sector)
    ma_mon = MAMonitor(market)
    signals = []

    for theme in themes[:3]:
        # P1-5 修复: 传递 sec_type
        cores = screener.screen(
            theme.get("sector_code", ""),
            theme.get("sector_name", ""),
            theme.get("sec_type", "concept"),
            today,
        )
        for core in cores:
            sig_result = ma_mon.check(core.stock_code, today)
            signals.append({
                "code": core.stock_code,
                "name": core.stock_name,
                "theme": theme.get("sector_name", ""),
                "score": core.total_score,
                "price": core.price,
                "ma10": core.ma10,
                "ma_deviation": core.ma_deviation,
                "signal": sig_result.get("signal"),
            })

    logger.info("Dashboard 数据聚合完成: %d 主线, %d 信号", len(themes), len(signals))
    return DashboardData(
        date=str(today), total_nav=total_nav, daily_return=daily,
        weekly_return=weekly, monthly_return=monthly,
        position_pct=pos_pct, cash=cash, fuse_level="NORMAL",
        themes=themes, signals=signals,
    )


def print_dashboard(data: DashboardData):
    """M2 终端仪表盘 — 纯文本打印。"""
    print()
    print("=" * 60)
    print(f"  趋势中军 Dashboard | {data.date}")
    print("=" * 60)
    print(f"  💰 总净值: ¥{data.total_nav:,.0f}  |  "
          f"日: {data.daily_return:+.2%}  |  "
          f"仓位: {data.position_pct:.0%}")
    print(f"  🛡️ 熔断: {data.fuse_level}  |  可用: ¥{data.cash:,.0f}")
    print()

    if data.themes:
        print("  📊 确认主线:")
        for i, t in enumerate(data.themes[:3], 1):
            medal = ["🥇", "🥈", "🥉"][i - 1]
            print(f"     {medal} {t.get('sector_name', '?')}  "
                  f"评分: {t.get('total_score', 0):.2f}")
    else:
        print("  📊 当前无确认主线（数据不足或市场无明确方向）")

    if data.signals:
        print()
        print("  📈 中军信号:")
        print(f"     {'代码':<8} {'名称':<10} {'主线':<12} {'信号':<10} "
              f"{'MA10偏离':>8}")
        print("     " + "-" * 52)
        for s in data.signals:
            sig_str = str(s['signal']).replace('SignalType.', '') if s['signal'] else '-'
            dev_str = f"{s['ma_deviation']:+.2%}" if s['ma_deviation'] else '-'
            print(f"     {s['code']:<8} {s['name']:<10} "
                  f"{s.get('theme', '')[:12]:<12} {sig_str:<10} {dev_str:>8}")
    else:
        print()
        print("  📈 暂无可交易信号")

    print()
    print("=" * 60)
