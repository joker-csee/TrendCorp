# 趋势中军交易系统 —— 集中配置
import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# 日志配置
# ============================================================

def setup_logging(log_dir: str | None = None, level: str | None = None):
    """初始化日志系统：app.log / scheduler.log / error.log + 控制台。"""
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "logs")
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))

    # app.log — INFO+
    app_handler = logging.FileHandler(
        os.path.join(log_dir, "app.log"), encoding="utf-8"
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)
    root.addHandler(app_handler)

    # scheduler.log — INFO+
    sched_handler = logging.FileHandler(
        os.path.join(log_dir, "scheduler.log"), encoding="utf-8"
    )
    sched_handler.setLevel(logging.INFO)
    sched_handler.setFormatter(formatter)
    root.addHandler(sched_handler)

    # error.log — ERROR+
    error_handler = logging.FileHandler(
        os.path.join(log_dir, "error.log"), encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # 控制台
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    root.info("日志系统初始化完成")


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
    confirmed_min_score: float = 3.0  # B-2 主线确认最低分


@dataclass
class CoreScreenerConfig:
    weights: dict = field(default_factory=lambda: {
        "market_cap": 0.15, "liquidity": 0.20,
        "ma_structure": 0.25, "vol_health": 0.25,
        "fundamental": 0.15,
    })
    score_threshold: float = 0.65
    top_n_per_sector: int = 2
    market_cap_range: tuple = (100, 500)  # 最优市值区间（亿）


@dataclass
class PositionConfig:
    total_cap: float = 0.70
    single_cap: float = 0.30
    sector_cap: float = 0.35
    cash_min: float = 0.30
    a_buy_first_pct: float = 0.50  # A级首次建仓比例
    b_buy_first_pct: float = 0.30  # B级首次建仓比例


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
