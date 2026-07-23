# scheduler/jobs.py — 定时任务注册（仅调用 Workflow，不直接调用 Engine）
import logging


def register_jobs(scheduler, weekly, daily, monthly):
    """注册所有定时任务。只接收 Workflow 对象，不直接引用 Engine。"""

    # 每周日 18:00 — 周度主线扫描
    scheduler.add_job(
        weekly.run,
        trigger="cron",
        day_of_week="sun",
        hour=18,
        minute=0,
        id="weekly_scan",
        name="周度主线扫描",
    )

    # 每个交易日 15:30 — 日终更新
    scheduler.add_job(
        daily.run,
        trigger="cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="daily_eod",
        name="日终更新",
    )

    # 月末最后一天 16:00 — 月度报告
    scheduler.add_job(
        monthly.run,
        trigger="cron",
        day="last",
        hour=16,
        minute=0,
        id="monthly_report",
        name="月度绩效报告",
    )

    # P1-1: 盘中每 5 分钟价格轮询止损
    scheduler.add_job(
        _placeholder_stop_check,
        trigger="interval",
        minutes=5,
        id="stop_loss_poll",
        name="价格轮询止损",
    )

    logger = logging.getLogger("scheduler.jobs")
    logger.info("定时任务注册完成: weekly/daily/monthly + stop_loss_poll")


def _placeholder_stop_check():
    """P1-1: 价格轮询占位。M5 替换为真正的 PositionManager + RiskController 集成。"""
    pass
