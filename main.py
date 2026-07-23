# 趋势中军交易系统 — 应用入口 (v1.0 M5)
import logging
import os
import sqlite3
import sys
from datetime import date

from config import AppConfig, setup_logging
from data.providers.market_provider import MarketProvider
from data.providers.financial_provider import FinancialProvider
from data.providers.announcement_provider import AnnouncementProvider
from repositories.sector_repository import SectorRepository
from repositories.stock_repository import StockRepository
from repositories.nav_repository import NavRepository
from repositories.core_score_repository import CoreScoreRepository
from repositories.position_repository import PositionRepository
from repositories.trade_repository import TradeRepository
from repositories.risk_repository import RiskRepository


def _init_db(db_path: str):
    """DDL + WAL。P2-2: DDL 不适合 Repository 模式，直接执行。"""
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
    today = str(date.today())
    existing = nav_repo.get_latest()
    if existing:
        logging.getLogger("init").info("净值记录已存在，跳过初始化")
        return
    nav_repo.save_snapshot(today, cfg.initial_capital, cfg.initial_capital, 0.0)


def create_engines(cfg, market, financial):
    """M5: 集中创建所有 Engine 对象。"""
    from engine.scanner.scanner import MarketScanner
    from engine.theme_selector import ThemeSelector
    from engine.screener.screener import CoreScreener
    from engine.ma_monitor import MAMonitor
    from engine.theme_monitor import ThemeMonitor
    from engine.position_manager import PositionManager
    from engine.risk_controller import RiskController
    from engine.order_executor import OrderExecutor

    return {
        "scanner": MarketScanner(market, cfg.scanner.weights, cfg.scanner.candidate_threshold),
        "theme_selector": ThemeSelector(cfg.scanner.confirmed_min_score),
        "screener": CoreScreener(market, financial, cfg.screener.weights,
                                  cfg.screener.score_threshold, cfg.screener.top_n_per_sector),
        "ma_monitor": MAMonitor(market),
        "theme_monitor": ThemeMonitor(market),
        "position_mgr": PositionManager(cfg.position.total_cap, cfg.position.single_cap,
                                         cfg.position.sector_cap, cfg.position.cash_min,
                                         cfg.position.a_buy_first_pct, cfg.position.b_buy_first_pct),
        "risk_ctrl": RiskController(cfg.risk.stock_loss_limit, cfg.risk.daily_dd_limit,
                                     cfg.risk.weekly_dd_limit, cfg.risk.monthly_dd_limit,
                                     cfg.risk.strategy_dd_limit, cfg.risk.consecutive_stop_limit),
        "order_executor": OrderExecutor(),
    }


def create_repos(cfg):
    return {
        "sector_repo": SectorRepository(cfg.db_path),
        "stock_repo": StockRepository(cfg.db_path),
        "nav_repo": NavRepository(cfg.db_path),
        "core_score_repo": CoreScoreRepository(cfg.db_path),
        "position_repo": PositionRepository(cfg.db_path),
        "trade_repo": TradeRepository(cfg.db_path),
        "risk_repo": RiskRepository(cfg.db_path),
    }


def create_journal(trade_repo, stock_repo, sector_repo, nav_repo):
    from journal.trade_logger import TradeLogger
    from journal.monthly_report import MonthlyReport
    return {
        "trade_logger": TradeLogger(trade_repo, stock_repo, sector_repo),
        "monthly_report": MonthlyReport(trade_repo, nav_repo, sector_repo),
    }


def serve():
    """M5: 启动 FastAPI Web 服务。"""
    cfg = AppConfig()
    setup_logging(cfg.log_dir, cfg.log_level)
    logger = logging.getLogger("app")
    logger.info("趋势中军交易系统 v1.0 — Web 服务启动")

    _init_db(cfg.db_path)

    market = MarketProvider()
    financial = FinancialProvider()
    announcement = AnnouncementProvider()

    repos = create_repos(cfg)
    engines = create_engines(cfg, market, financial)
    journals = create_journal(repos["trade_repo"], repos["stock_repo"],
                               repos["sector_repo"], repos["nav_repo"])

    # 初始化板块数据
    existing = repos["sector_repo"].get_all_active()
    if not existing:
        try:
            _init_sectors(market, repos["sector_repo"])
        except RuntimeError as e:
            logger.warning("板块初始化失败（网络不可用）: %s", e)
    else:
        logger.info("板块数据已存在（%d 个），跳过拉取", len(existing))
    _init_initial_nav(cfg, repos["nav_repo"])

    # RiskController 注入 RiskRepository
    engines["risk_ctrl"].risk_repo = repos["risk_repo"]

    # FastAPI 应用
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from apscheduler.schedulers.background import BackgroundScheduler
    from web.router import router
    from scheduler.jobs import register_jobs
    from workflow.weekly_workflow import WeeklyWorkflow
    from workflow.daily_workflow import DailyWorkflow
    from workflow.monthly_workflow import MonthlyWorkflow

    app = FastAPI(title="趋势中军交易系统", version="1.0")
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # P0-4: 全局异常处理器 — 未捕获异常返回统一 APIResponse 格式
    from fastapi.responses import JSONResponse as _JR
    from web.schemas import APIResponse as _AR

    @app.exception_handler(Exception)
    async def _global_handler(request, exc):
        return _JR(
            status_code=200,
            content=_AR.fail(message=str(exc)).model_dump(),
        )

    app.include_router(router)

    # 挂载所有组件到 app.state
    app.state.cfg = cfg
    app.state.market = market
    app.state.financial = financial
    for name, obj in {**repos, **engines, **journals}.items():
        setattr(app.state, name, obj)

    # 注册定时任务
    scheduler = BackgroundScheduler()
    wf_weekly = WeeklyWorkflow(
        market=market, scanner=engines["scanner"],
        theme_selector=engines["theme_selector"],
        screener=engines["screener"],
        sector_repo=repos["sector_repo"],
        stock_repo=repos["stock_repo"],
        core_score_repo=repos["core_score_repo"],
    )
    wf_daily = DailyWorkflow(
        market=market, ma_monitor=engines["ma_monitor"],
        theme_monitor=engines["theme_monitor"],
        position_repo=repos["position_repo"],
        trade_repo=repos["trade_repo"],
        nav_repo=repos["nav_repo"],
        sector_repo=repos["sector_repo"],
        stock_repo=repos["stock_repo"],
        initial_capital=cfg.initial_capital,
    )
    wf_monthly = MonthlyWorkflow(
        trade_repo=repos["trade_repo"],
        nav_repo=repos["nav_repo"],
    )
    register_jobs(scheduler, wf_weekly, wf_daily, wf_monthly)
    scheduler.start()
    logger.info("定时任务已注册: weekly/daily/monthly/stop_loss_poll")

    logger.info("Web 服务就绪 → http://localhost:8000")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def main():
    """直接启动时执行初始化。"""
    cfg = AppConfig()
    setup_logging(cfg.log_dir, cfg.log_level)
    _init_db(cfg.db_path)
    market = MarketProvider()
    repos = create_repos(cfg)
    _init_sectors(market, repos["sector_repo"])
    _init_initial_nav(cfg, repos["nav_repo"])
    logging.getLogger("init").info("M1-M5 初始化完成")


# CLI 入口
if __name__ == "__main__":
    argv = sys.argv
    if "--serve" in argv or "--web" in argv:
        serve()
    elif "--dashboard" in argv:
        # Legacy M2 terminal dashboard
        cfg = AppConfig()
        setup_logging(cfg.log_dir, cfg.log_level)
        market = MarketProvider(); financial = FinancialProvider()
        repos = create_repos(cfg)
        _init_db(cfg.db_path)
        from engine.dashboard import build_dashboard, print_dashboard
        data = build_dashboard(cfg, market, financial,
                               repos["sector_repo"], repos["nav_repo"],
                               risk_repo=repos["risk_repo"])
        print_dashboard(data)
    else:
        main()
