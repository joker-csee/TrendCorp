# 趋势中军交易系统 — 应用入口
import logging
import os
import sqlite3
from datetime import date, timedelta

from config import AppConfig, setup_logging
from data.providers.market_provider import MarketProvider
from data.providers.financial_provider import FinancialProvider
from data.providers.announcement_provider import AnnouncementProvider
from repositories.sector_repository import SectorRepository
from repositories.stock_repository import StockRepository
from repositories.nav_repository import NavRepository


def _init_db(db_path: str):
    """执行 schema.sql 建表 + 启用 WAL 模式。

    P2-2: DDL 操作天然不适合 Repository 模式（建表不属于 CRUD），
    故直接在连接上执行。P2-4: 同时启用 WAL 防止后续并发写锁冲突。
    """
    schema_path = os.path.join(os.path.dirname(__file__), "data", "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"schema.sql 不存在: {schema_path}")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with open(schema_path, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        logging.getLogger("init").info("数据库初始化完成 (WAL 模式)")
    finally:
        conn.close()


def _init_sectors(market: MarketProvider, sector_repo: SectorRepository):
    """首次启动时拉取并存储全市场板块列表。"""
    logger = logging.getLogger("init")
    df = market.fetch_all_sectors()
    count = 0
    for _, row in df.iterrows():
        try:
            sector_repo.upsert_sector(
                code=str(row["code"]),
                name=str(row["name"]),
                sec_type=str(row["type"]),
            )
            count += 1
        except Exception as e:
            logger.warning(f"板块入库失败 {row.get('code')}: {e}")
    logger.info(f"全市场板块入库完成，共 {count} 个")


def _init_initial_nav(cfg: AppConfig, nav_repo: NavRepository):
    """写入初始净值记录。"""
    today = str(date.today())
    existing = nav_repo.get_latest()
    if existing:
        logging.getLogger("init").info("净值记录已存在，跳过初始化")
        return
    nav_repo.save_snapshot(
        snap_date=today,
        total_value=cfg.initial_capital,
        cash=cfg.initial_capital,
        positions_value=0.0,
    )
    logging.getLogger("init").info(
        "初始净值记录写入: ¥%s", f"{cfg.initial_capital:,.0f}"
    )


def initialize(cfg: AppConfig = None):
    """执行系统初始化：建表 → 拉取板块 → 写入初始净值。"""
    if cfg is None:
        cfg = AppConfig()

    setup_logging(cfg.log_dir, cfg.log_level)
    logger = logging.getLogger("init")
    logger.info("趋势中军交易系统 v1.0 - M1 初始化开始")

    _init_db(cfg.db_path)

    market = MarketProvider()
    financial = FinancialProvider()
    announcement = AnnouncementProvider()

    sector_repo = SectorRepository(cfg.db_path)
    stock_repo = StockRepository(cfg.db_path)
    nav_repo = NavRepository(cfg.db_path)

    _init_sectors(market, sector_repo)
    _init_initial_nav(cfg, nav_repo)

    logger.info("M1 初始化完成")
    return {
        "market": market,
        "financial": financial,
        "announcement": announcement,
        "sector_repo": sector_repo,
        "stock_repo": stock_repo,
        "nav_repo": nav_repo,
        "config": cfg,
    }


def main():
    """直接启动时执行初始化。"""
    initialize()


def run_weekly():
    """M3: 手动触发周度 Workflow。"""
    ctx = _setup_m3_context()
    from workflow.weekly_workflow import WeeklyWorkflow
    wf = WeeklyWorkflow(
        market=ctx["market"],
        scanner=ctx["scanner"],
        theme_selector=ctx["theme_selector"],
        screener=ctx["screener"],
        sector_repo=ctx["sector_repo"],
        stock_repo=ctx["stock_repo"],
        core_score_repo=ctx["core_score_repo"],
    )
    wf.run()


def run_daily():
    """M3: 手动触发日终 Workflow。"""
    ctx = _setup_m3_context()
    from workflow.daily_workflow import DailyWorkflow
    wf = DailyWorkflow(
        market=ctx["market"],
        ma_monitor=ctx["ma_monitor"],
        theme_monitor=ctx["theme_monitor"],
        position_repo=ctx["position_repo"],
        trade_repo=ctx["trade_repo"],
        nav_repo=ctx["nav_repo"],
        sector_repo=ctx["sector_repo"],
        initial_capital=ctx["config"].initial_capital,
    )
    wf.run()


def run_monthly():
    """M3: 手动触发月度 Workflow。"""
    ctx = _setup_m3_context()
    from workflow.monthly_workflow import MonthlyWorkflow
    wf = MonthlyWorkflow(
        trade_repo=ctx["trade_repo"],
        nav_repo=ctx["nav_repo"],
    )
    return wf.run()


def _setup_m3_context():
    """M3: 初始化所有组件（复用 initialize 的数据层 + 新建 Engine）。"""
    import logging as _logging
    cfg = AppConfig()
    setup_logging(cfg.log_dir, cfg.log_level)
    logger = _logging.getLogger("app")

    market = MarketProvider()
    financial = FinancialProvider()
    announcement = AnnouncementProvider()

    from repositories.sector_repository import SectorRepository
    from repositories.stock_repository import StockRepository
    from repositories.nav_repository import NavRepository
    from repositories.core_score_repository import CoreScoreRepository
    from repositories.position_repository import PositionRepository
    from repositories.trade_repository import TradeRepository

    sector_repo = SectorRepository(cfg.db_path)
    stock_repo = StockRepository(cfg.db_path)
    nav_repo = NavRepository(cfg.db_path)
    core_score_repo = CoreScoreRepository(cfg.db_path)
    position_repo = PositionRepository(cfg.db_path)
    trade_repo = TradeRepository(cfg.db_path)

    from engine.scanner.scanner import MarketScanner
    from engine.theme_selector import ThemeSelector
    from engine.screener.screener import CoreScreener
    from engine.ma_monitor import MAMonitor
    from engine.theme_monitor import ThemeMonitor

    scanner = MarketScanner(market, cfg.scanner.weights, cfg.scanner.candidate_threshold)
    theme_selector = ThemeSelector(cfg.scanner.confirmed_min_score)
    screener = CoreScreener(market, financial, cfg.screener.weights,
                            cfg.screener.score_threshold, cfg.screener.top_n_per_sector)
    ma_monitor = MAMonitor(market)
    theme_monitor = ThemeMonitor(market)

    return {
        "config": cfg,
        "market": market,
        "financial": financial,
        "announcement": announcement,
        "sector_repo": sector_repo,
        "stock_repo": stock_repo,
        "nav_repo": nav_repo,
        "core_score_repo": core_score_repo,
        "position_repo": position_repo,
        "trade_repo": trade_repo,
        "scanner": scanner,
        "theme_selector": theme_selector,
        "screener": screener,
        "ma_monitor": ma_monitor,
        "theme_monitor": theme_monitor,
    }


def dashboard():
    """M2: 终端仪表盘模式。"""
    import sys
    cfg = AppConfig()
    setup_logging(cfg.log_dir, cfg.log_level)
    logger = logging.getLogger("app")

    # 初始化数据层
    market = MarketProvider()
    financial = FinancialProvider()
    sector_repo = SectorRepository(cfg.db_path)
    nav_repo = NavRepository(cfg.db_path)

    # P1-6 修复: 先检查板块数据是否存在，存在则跳过拉取
    _init_db(cfg.db_path)
    existing_sectors = sector_repo.get_all_active()
    if existing_sectors:
        logger.info("板块数据已存在（%d 个），跳过拉取", len(existing_sectors))
    else:
        # N1: sector 表为空 + API 不可用时不应崩溃
        try:
            _init_sectors(market, sector_repo)
        except RuntimeError as e:
            logger.warning("板块初始化失败（网络不可用）: %s", e)
    _init_initial_nav(cfg, nav_repo)

    from engine.dashboard import build_dashboard, print_dashboard
    data = build_dashboard(cfg, market, financial, sector_repo, nav_repo)
    print_dashboard(data)


if __name__ == "__main__":
    import sys
    argv = sys.argv
    if "--dashboard" in argv:
        dashboard()
    elif "--weekly" in argv:
        run_weekly()
    elif "--daily" in argv:
        run_daily()
    elif "--monthly" in argv:
        run_monthly()
    else:
        main()
