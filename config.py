# 趋势中军交易系统 —— 集中配置
import logging
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

_ENV_LOADED = load_dotenv()

# P1-1: .env 缺失时输出 WARNING
if not _ENV_LOADED:
    logging.getLogger("config").warning(
        "未找到 .env 文件，使用默认配置"
    )


# ============================================================
# 日志配置（P1-2 修复：按 logger hierarchy 分离输出）
# ============================================================

def setup_logging(log_dir: str | None = None, level: str | None = None):
    """初始化日志系统。

    日志分流规则：
    - app.log:     logging.getLogger("app") 及其子 logger
    - scheduler.log: logging.getLogger("scheduler") 及其子 logger
    - error.log:   所有 ERROR+ 消息聚合
    - 控制台:      所有 INFO+ 消息
    """
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "logs")
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_level = getattr(logging, level.upper())

    root = logging.getLogger()
    root.setLevel(log_level)

    # 移除已有 handler（防止重复添加）
    root.handlers.clear()

    # ---- app.log — 仅 "app" 及 root（非 scheduler）----
    class AppFilter(logging.Filter):
        def filter(self, record):
            return not record.name.startswith("scheduler")

    app_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"), encoding="utf-8"
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(fmt)
    app_handler.addFilter(AppFilter())
    root.addHandler(app_handler)

    # ---- scheduler.log — 仅 "scheduler" ----
    class SchedulerFilter(logging.Filter):
        def filter(self, record):
            return record.name.startswith("scheduler")

    sched_handler = logging.FileHandler(
        os.path.join(log_dir, "scheduler.log"), encoding="utf-8"
    )
    sched_handler.setLevel(logging.INFO)
    sched_handler.setFormatter(fmt)
    sched_handler.addFilter(SchedulerFilter())
    root.addHandler(sched_handler)

    # ---- error.log — 所有 ERROR+ ----
    error_handler = logging.FileHandler(
        os.path.join(log_dir, "error.log"), encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    root.addHandler(error_handler)

    # ---- 控制台 — 所有 INFO+ ----
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    logging.getLogger("app").info("日志系统初始化完成")


# ============================================================
# 子配置
# ============================================================

@dataclass
class ScannerConfig:
    weights: dict = field(default_factory=lambda: {
        "trend": 0.35, "rel_strength": 0.25,
        "fund": 0.25, "echelon": 0.15,
    })
    candidate_threshold: float = 0.6
    confirmed_min_score: float = 3.0


@dataclass
class CoreScreenerConfig:
    weights: dict = field(default_factory=lambda: {
        "market_cap": 0.15, "liquidity": 0.20,
        "ma_structure": 0.25, "vol_health": 0.25,
        "fundamental": 0.15,
    })
    score_threshold: float = 0.65
    top_n_per_sector: int = 2
    market_cap_range: tuple = (100, 500)


@dataclass
class PositionConfig:
    total_cap: float = 0.70
    single_cap: float = 0.30
    sector_cap: float = 0.35
    cash_min: float = 0.30
    a_buy_first_pct: float = 0.50
    b_buy_first_pct: float = 0.30


@dataclass
class RiskConfig:
    stock_loss_limit: float = -0.08
    daily_dd_limit: float = -0.03
    weekly_dd_limit: float = -0.05
    monthly_dd_limit: float = -0.10
    strategy_dd_limit: float = -0.15
    consecutive_stop_limit: int = 2


# ============================================================
# 应用总配置
# ============================================================

@dataclass
class AppConfig:
    db_path: str = field(default_factory=lambda: os.getenv(
        "DATABASE_PATH", "data/trend_corp.db"
    ))
    log_dir: str = field(default_factory=lambda: os.getenv(
        "LOG_DIR", "logs"
    ))
    log_level: str = field(default_factory=lambda: os.getenv(
        "LOG_LEVEL", "INFO"
    ))
    initial_capital: float = field(
        default_factory=lambda: float(os.getenv("INITIAL_CAPITAL", "100000"))
    )
    data_cache_dir: str = field(default_factory=lambda: os.getenv(
        "DATA_CACHE_DIR", "data/cache"
    ))

    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    screener: CoreScreenerConfig = field(default_factory=CoreScreenerConfig)
    position: PositionConfig = field(default_factory=PositionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
