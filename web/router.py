# web/router.py — FastAPI 路由定义
import logging
from datetime import date

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.schemas import APIResponse

router = APIRouter()
import os as _os
_tpl_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "web", "templates")
templates = Jinja2Templates(directory=_tpl_dir)
logger = logging.getLogger("app.web")


# ── 页面路由 ──

@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/scanner", response_class=HTMLResponse)
async def scanner_page(request: Request):
    return templates.TemplateResponse(request, "scanner.html")


@router.get("/positions", response_class=HTMLResponse)
async def positions_page(request: Request):
    return templates.TemplateResponse(request, "positions.html")


@router.get("/journal", response_class=HTMLResponse)
async def journal_page(request: Request):
    return templates.TemplateResponse(request, "journal.html")


@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request):
    return templates.TemplateResponse(request, "report.html")


# ── 数据 API ──

@router.get("/api/dashboard", response_model=APIResponse)
async def api_dashboard(request: Request):
    try:
        from engine.dashboard import build_dashboard
        app = request.app
        data = build_dashboard(
            app.state.cfg, app.state.market, app.state.financial,
            app.state.sector_repo, app.state.nav_repo,
            risk_repo=app.state.risk_repo,
        )
        return APIResponse.ok(data={
            "date": data.date, "total_nav": data.total_nav,
            "daily_return": data.daily_return,
            "weekly_return": data.weekly_return,
            "monthly_return": data.monthly_return,
            "position_pct": data.position_pct, "cash": data.cash,
            "fuse_level": data.fuse_level,
            "themes": data.themes, "signals": data.signals,
        })
    except RuntimeError as e:
        return APIResponse.fail(message=f"数据不可用: {e}")


@router.get("/api/scanner/latest", response_model=APIResponse)
async def api_scanner(request: Request):
    try:
        rows = request.app.state.sector_repo.get_latest_snapshot()
        return APIResponse.ok(data=rows)
    except Exception as e:
        return APIResponse.fail(message=str(e))


@router.get("/api/positions", response_model=APIResponse)
async def api_positions(request: Request):
    try:
        positions = request.app.state.position_repo.get_all()
        return APIResponse.ok(data=positions)
    except Exception as e:
        return APIResponse.fail(message=str(e))


@router.get("/api/nav/history", response_model=APIResponse)
async def api_nav(request: Request, days: int = 90):
    try:
        rows = request.app.state.nav_repo.get_history(days)
        return APIResponse.ok(data=rows)
    except Exception as e:
        return APIResponse.fail(message=str(e))


@router.get("/api/risk/status", response_model=APIResponse)
async def api_risk(request: Request):
    try:
        events = request.app.state.risk_repo.get_recent(limit=5)
        return APIResponse.ok(data=events)
    except Exception as e:
        return APIResponse.fail(message=str(e))


# ── 操作 API ──

@router.post("/api/trade/log", response_model=APIResponse)
async def api_trade_log(request: Request):
    try:
        body = await request.json()
        result = request.app.state.trade_logger.log_open(
            stock_code=body["stock_code"],
            open_price=body["open_price"],
            open_reason=body.get("open_reason", "MANUAL"),
            open_ma10=body.get("open_ma10"),
            position_pct=body.get("position_pct", 0),
        )
        return APIResponse.ok(data=result)
    except Exception as e:
        return APIResponse.fail(message=str(e))


@router.post("/api/workflow/scan", response_model=APIResponse)
async def api_workflow_scan(request: Request):
    try:
        from workflow.weekly_workflow import WeeklyWorkflow
        app = request.app
        wf = WeeklyWorkflow(
            market=app.state.market, scanner=app.state.scanner,
            theme_selector=app.state.theme_selector,
            screener=app.state.screener,
            sector_repo=app.state.sector_repo,
            stock_repo=app.state.stock_repo,
            core_score_repo=app.state.core_score_repo,
        )
        wf.run()
        # P1-6: 返回扫描统计
        snapshots = app.state.sector_repo.get_latest_snapshot()
        confirmed = sum(1 for s in snapshots if s.get("is_confirmed") == 2)
        return APIResponse.ok(data={
            "total_scanned": len(snapshots),
            "confirmed_themes": confirmed,
        }, message=f"扫描完成: {len(snapshots)}板块, {confirmed}确认主线")
    except Exception as e:
        return APIResponse.fail(message=str(e))


# P0-3: 日终 Workflow Web 端点
@router.post("/api/workflow/eod", response_model=APIResponse)
async def api_workflow_eod(request: Request):
    try:
        from workflow.daily_workflow import DailyWorkflow
        app = request.app
        wf = DailyWorkflow(
            market=app.state.market,
            ma_monitor=app.state.ma_monitor,
            theme_monitor=app.state.theme_monitor,
            position_repo=app.state.position_repo,
            trade_repo=app.state.trade_repo,
            nav_repo=app.state.nav_repo,
            sector_repo=app.state.sector_repo,
            stock_repo=app.state.stock_repo,
            initial_capital=app.state.cfg.initial_capital,
        )
        wf.run()
        return APIResponse.ok(message="日终更新完成")
    except Exception as e:
        return APIResponse.fail(message=str(e))


# P1-2: 平仓 API
@router.post("/api/trade/close", response_model=APIResponse)
async def api_trade_close(request: Request):
    try:
        body = await request.json()
        trade_id = body["trade_id"]
        close_price = body["close_price"]
        close_reason = body.get("close_reason", "TAKE_PROFIT")
        rule_compliant = body.get("rule_compliant", True)
        lesson = body.get("lesson")
        request.app.state.trade_logger.log_close(
            trade_id=trade_id,
            close_price=close_price,
            close_reason=close_reason,
            rule_compliant=rule_compliant,
            lesson=lesson,
        )
        return APIResponse.ok(message="平仓记录已更新")
    except Exception as e:
        return APIResponse.fail(message=str(e))


@router.get("/api/report", response_model=APIResponse)
async def api_report(request: Request,
                     year: int = None, month: int = None):
    try:
        if year is None:
            year = date.today().year
        if month is None:
            month = date.today().month
        report = request.app.state.monthly_report.generate(year, month)
        return APIResponse.ok(data=report)
    except Exception as e:
        return APIResponse.fail(message=str(e))
