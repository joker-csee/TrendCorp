# 趋势中军交易系统 —— 软件系统架构

> 版本 v1.1 | 2026-07-02
> 变更：采纳架构评审 A-1~A-3、B-1~B-4 全部建议
> 原则：单用户、单进程、零外部依赖中间件、`python main.py` 即可运行

---

## 一、技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| **语言** | Python 3.11+ | `akshare` 覆盖 A 股全部数据需求 |
| **Web 框架** | FastAPI | 异步、自动 OpenAPI 文档 |
| **前端** | Jinja2 + HTMX + Chart.js | 极简，无需 Node.js，单文件部署 |
| **数据库** | SQLite | 单用户几万条数据绰绰有余，零运维 |
| **任务调度** | APScheduler | 内嵌 Python 进程，无需 Redis |
| **数据源** | akshare（免费开源） | 行情 + 板块 + 财务 + 资金流 + 公告 |
| **日志** | Python logging 标准库 | 不引入第三方，按模块分流到三个文件 |
| **环境配置** | python-dotenv（`.env`） | 唯一新增依赖，换机不换码 |
| **部署** | `python main.py` → localhost:8000 | |

> 不引入：Redis / PostgreSQL / Docker / RabbitMQ / Kafka / 微服务 / DDD / CQRS。

---

## 二、项目结构

```
TrendCorp/
├── main.py                         # 应用入口
├── config.py                       # 策略参数 + 从 .env 读取路径
├── .env.example                    # 环境变量模板（提交 git）
├── .env                            # 实际环境变量（gitignore）
├── requirements.txt
│
├── data/                           # ── 数据层 ──
│   ├── schema.sql                  # SQLite 建表 9 张
│   └── providers/                  # B-2: 按数据域拆分
│       ├── __init__.py
│       ├── base.py                 # Provider 基类（重试、日志）
│       ├── market_provider.py      # 板块/个股日K、均线、资金流
│       ├── financial_provider.py   # 营收增速、净利润、ROE
│       └── announcement_provider.py# 业绩预告、合同、分析师覆盖
│
├── engine/                         # ── 核心引擎层 ──
│   ├── scanner/                    # A-1: 板块扫描，按评分维度拆分
│   │   ├── __init__.py
│   │   ├── trend.py                # 趋势强度（MA排列）
│   │   ├── rel_strength.py         # 相对强度（vs 沪深300）
│   │   ├── fund_flow.py            # 资金确认（主力净流入 + 成交占比）
│   │   ├── echelon.py              # 梯队完整性（涨停数 + 大市值存在）
│   │   └── scanner.py              # B-1 流程编排（组装四个维度）
│   ├── screener/                   # A-1: 中军筛选，按评分维度拆分
│   │   ├── __init__.py
│   │   ├── market_cap.py           # 市值规模（最优 100-500 亿）
│   │   ├── liquidity.py            # 流动性（成交额板块排名）
│   │   ├── ma_structure.py         # 均线结构（MA5>10>21>55）
│   │   ├── vol_health.py           # 量价健康度（涨放量/跌缩量）
│   │   ├── fundamental.py          # 基本面质量（营收 + 净利润增速）
│   │   └── screener.py             # C-1 流程编排
│   ├── theme_selector.py           # B-2 主线确认器
│   ├── theme_monitor.py            # B-3 主线退潮预警器
│   ├── ma_monitor.py               # C-2 均线状态监控器
│   ├── position_manager.py         # D-1 仓位管理器
│   ├── order_executor.py           # D-2 订单执行器
│   ├── risk_controller.py          # E-1 三级熔断器
│   └── dashboard.py                # E-2 仪表盘数据聚合
│
├── repositories/                   # ── 持久化层 A-2: 按领域拆分 ──
│   ├── __init__.py
│   ├── sector_repository.py        # sector + sector_snapshot
│   ├── stock_repository.py         # stock
│   ├── core_score_repository.py    # core_score_snapshot
│   ├── trade_repository.py         # trade
│   ├── position_repository.py      # position
│   ├── risk_repository.py          # risk_event
│   └── nav_repository.py           # nav_snapshot
│
├── workflow/                       # ── 编排层 B-1 ──
│   ├── __init__.py
│   ├── base.py                     # Workflow 基类（日志/异常/耗时）
│   ├── weekly_workflow.py          # 周日：数据→扫描→确认→筛选→存库
│   ├── daily_workflow.py           # 日终：行情→均线→退潮→信号
│   └── monthly_workflow.py         # 月末：绩效报告→归档
│
├── scheduler/
│   └── jobs.py                     # 定时触发，只调 Workflow，不直接调 Engine
│
├── journal/                        # ── 复盘层 ──
│   ├── trade_logger.py             # F-1 交易日志
│   ├── monthly_report.py           # F-2 月度归因
│   └── param_tuner.py              # F-3 季度参数优化
│
├── web/                            # ── 展示层 ──
│   ├── router.py                   # FastAPI 路由
│   ├── schemas.py                  # B-3: 统一 APIResponse 模型
│   ├── templates/                  # 6 个 Jinja2 模板
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── scanner.html
│   │   ├── watchlist.html
│   │   ├── positions.html
│   │   ├── journal.html
│   │   └── report.html
│   └── static/
│       ├── style.css
│       └── app.js
│
├── logs/                           # A-3: 日志输出目录
│   ├── .gitkeep
│   ├── app.log                     # INFO+ 所有 Engine/Workflow/数据更新
│   ├── scheduler.log               # 定时任务启停 + 异常
│   └── error.log                   # ERROR+ 完整堆栈汇总
│
└── tests/
    ├── test_scanner/
    ├── test_screener/
    └── test_risk.py
```

---

## 三、数据库设计（不变）

9 张表：`sector` → `sector_snapshot` → `stock` → `core_score_snapshot` → `trade` → `position` → `risk_event` → `nav_snapshot`

（完整 DDL 参见原架构 v1.0，未修改）

---

## 四、分层与调用关系

```
┌──────────────────────────────────────────────────┐
│                    Web 层                         │
│  router.py  ←  schemas.py（统一 APIResponse）     │
│  Jinja2 模板 + HTMX 局部刷新                      │
└────────────────────┬─────────────────────────────┘
                     │ 调用
┌────────────────────▼─────────────────────────────┐
│                 Workflow 层（B-1）                 │
│  weekly_workflow  /  daily_workflow  /  monthly   │
│  "做什么、按什么顺序做"                             │
└────────────────────┬─────────────────────────────┘
                     │ 编排
┌────────────────────▼─────────────────────────────┐
│                  Engine 层                         │
│  scanner/  screener/  theme_*  ma_monitor         │
│  position_manager  risk_controller  dashboard      │
│  "每件事怎么算"                                     │
└────────┬──────────────────────────────┬───────────┘
         │ 持久化                        │ 数据获取
┌────────▼──────────┐      ┌────────────▼──────────┐
│  repositories/    │      │  data/providers/      │
│  7 个领域 Repo    │      │  market/financial/    │
│  (SQLite CRUD)    │      │  announcement         │
└───────────────────┘      └───────────────────────┘
```

**调用规则**：

| 调用方向 | 允许？ |
|---------|:----:|
| Router → Workflow | ✅ |
| Router → Engine（只读查询，如 Dashboard） | ✅ |
| Workflow → Engine | ✅ |
| Workflow → Provider | ✅（拉取数据步骤） |
| Engine → Repository / Provider | ✅ |
| Scheduler → Workflow | ✅ |
| Scheduler → Engine | ❌ 不直接调，必须通过 Workflow |
| Engine → Engine（跨模块直接调用） | ❌ 必须通过 Workflow 编排 |

---

## 五、核心模块设计

### 5.1 Provider 层（B-2）

```python
# data/providers/base.py
import logging
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """所有数据 Provider 的基类：统一日志 + 重试。"""
    def __init__(self, max_retries: int = 3):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_retries = max_retries

    def fetch_with_retry(self, func, *args, **kwargs):
        """带重试的数据拉取。失败记录 error.log。"""
        # ...重试逻辑 + 异常日志
        pass


# data/providers/market_provider.py
class MarketProvider(BaseProvider):
    """板块/个股日K、均线计算、资金流、成交额。"""
    def fetch_sector_daily(self, code: str, start, end) -> pd.DataFrame: ...
    def fetch_stock_daily(self, code: str, start, end) -> pd.DataFrame: ...
    def fetch_sector_fund_flow(self, code: str, days: int) -> float: ...
    def fetch_index_daily(self, code: str, start, end) -> pd.DataFrame: ...


# data/providers/financial_provider.py
class FinancialProvider(BaseProvider):
    """营收增速、净利润增速、ROE、毛利率、流通市值。"""
    def fetch_financials(self, code: str) -> dict: ...
    def fetch_market_cap(self, code: str) -> float: ...


# data/providers/announcement_provider.py
class AnnouncementProvider(BaseProvider):
    """业绩预告、重大合同、分析师覆盖。"""
    def fetch_performance_forecast(self, days: int) -> list[dict]: ...
    def fetch_major_contracts(self, days: int) -> list[dict]: ...
```

### 5.2 Scanner 子模块（A-1）

```python
# engine/scanner/trend.py
def calc_trend_score(ma5, ma10, ma21, ma55) -> float:
    """MA5 > MA10 > MA21 > MA55，每满足一级 +0.25。返回 0-1。"""

# engine/scanner/rel_strength.py
def calc_rel_strength(sector_ret_20d, hs300_ret_20d) -> float:
    """近 20 日板块涨幅 / 沪深 300 涨幅，映射到 0-1。"""

# engine/scanner/fund_flow.py
def calc_fund_score(net_inflow_5d, volume_ratio) -> float:
    """资金净流入 + 成交额占比，两项都满足得 1.0。"""

# engine/scanner/echelon.py
def calc_echelon_score(limit_up_cnt, has_large_cap) -> float:
    """涨停家数 ≥ 3 + 存在 > 100 亿市值标的，两项都满足得 1.0。"""

# engine/scanner/scanner.py
class MarketScanner:
    """B-1 板块扫描器。遍历全市场板块，组装四个维度评分。"""
    def __init__(self, market_provider, weights, threshold):
        self.trend = TrendScorer()
        self.strength = RelStrengthScorer()
        self.fund = FundFlowScorer()
        self.echelon = EchelonScorer()
        # weights / threshold 从 config.py 注入

    def scan_all(self, date) -> list[ScanResult]:
        for sector in self.market_provider.fetch_all_sectors():
            trend = self.trend.calc(sector)
            strength = self.strength.calc(sector, date)
            fund = self.fund.calc(sector, date)
            echelon = self.echelon.calc(sector, date)
            total = (trend * 0.35 + strength * 0.25 +
                     fund * 0.25 + echelon * 0.15)
            if total >= self.threshold:
                results.append(ScanResult(...))
        return sorted(results, key=lambda r: r.total_score, reverse=True)
```

### 5.3 Screener 子模块（A-1）

`screener/` 子目录结构与 Scanner 类似：`market_cap.py`、`liquidity.py`、`ma_structure.py`、`vol_health.py`、`fundamental.py` 各管一个维度，`screener.py` 做流程编排。权重从 `config.py` 注入。

### 5.4 Workflow 层（B-1）

```python
# workflow/base.py
import logging
import time
from abc import ABC, abstractmethod

class BaseWorkflow(ABC):
    """所有 Workflow 的基类：统一日志记录开始/结束/耗时/异常。"""
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def run(self):
        start = time.time()
        self.logger.info(f"{self.__class__.__name__} 开始")
        try:
            self.execute()
        except Exception as e:
            self.logger.exception(f"{self.__class__.__name__} 异常: {e}")
            raise
        finally:
            elapsed = time.time() - start
            self.logger.info(f"{self.__class__.__name__} 完成，耗时 {elapsed:.1f}s")

    @abstractmethod
    def execute(self):
        """子类实现具体流程步骤。"""
        pass


# workflow/weekly_workflow.py
class WeeklyWorkflow(BaseWorkflow):
    def __init__(self, market_provider, scanner, theme_selector,
                 screener, sector_repo, core_score_repo):
        self.market = market_provider
        self.scanner = scanner
        self.selector = theme_selector
        self.screener = screener
        self.sector_repo = sector_repo
        self.core_score_repo = core_score_repo

    def execute(self):
        """周日执行：更新数据 → 扫描板块 → 确认主线 → 筛选中军 → 存库。"""
        self.logger.info("Step 1/5: 更新全市场板块数据")
        # ...拉取数据

        self.logger.info("Step 2/5: 扫描板块（B-1 四维评分）")
        scan_results = self.scanner.scan_all(today)

        self.logger.info("Step 3/5: 确认主线（B-2 持续性验证）")
        confirmed = self.selector.confirm(scan_results)

        self.logger.info("Step 4/5: 筛选中军（C-1 五维评分）")
        for theme in confirmed:
            cores = self.screener.screen(theme.sector_code, today)

        self.logger.info("Step 5/5: 保存快照到 SQLite")
        self.sector_repo.save_snapshot(...)
        self.core_score_repo.save_snapshot(...)

        self.logger.info(f"完成。确认主线 {len(confirmed)} 个，中军候选 {total_cores} 只")


# workflow/daily_workflow.py
class DailyWorkflow(BaseWorkflow):
    """日终执行：更新持仓行情 → 均线状态 → 退潮预警 → 生成信号。"""
    def execute(self):
        # Step 1: 更新持仓 + 候选池当日行情
        # Step 2: C-2 均线状态计算，生成 A/B/HOLD/REDUCE/EXIT 信号
        # Step 3: B-3 退潮预警检查
        # Step 4: E-1 风控状态检查
        # Step 5: 更新 nav_snapshot
        pass


# workflow/monthly_workflow.py
class MonthlyWorkflow(BaseWorkflow):
    """月末执行：生成绩效报告 + 归档快照。"""
    def execute(self):
        pass
```

Scheduler 变为极薄的一层——只注册触发时机，不包含任何业务逻辑：

```python
# scheduler/jobs.py
def register_jobs(scheduler, weekly: WeeklyWorkflow,
                  daily: DailyWorkflow, monthly: MonthlyWorkflow):
    scheduler.add_job(weekly.run,  trigger='cron', day_of_week='sun', hour=18)
    scheduler.add_job(daily.run,   trigger='cron', day_of_week='mon-fri', hour=15, minute=30)
    scheduler.add_job(monthly.run, trigger='cron', day='last', hour=16)
```

### 5.5 Repository 层（A-2）

```python
# repositories/sector_repository.py
class SectorRepository:
    """sector + sector_snapshot 的 CRUD。"""
    def __init__(self, db_path: str): ...
    def upsert_sector(self, code, name, type) -> int: ...
    def save_snapshot(self, sector_id, snap: SectorScanResult) -> int: ...
    def get_latest_snapshot(self) -> list[dict]: ...
    def get_history(self, sector_id, months: int) -> pd.DataFrame: ...

# repositories/trade_repository.py
class TradeRepository:
    """trade 表的 CRUD。"""
    def insert_trade(self, trade: TradeRecord) -> int: ...
    def update_close(self, trade_id, close_price, reason) -> None: ...
    def get_open_trades(self) -> list[dict]: ...
    def get_monthly_stats(self, year, month) -> dict: ...

# 其余 5 个 Repository 各自负责一张或一组相关表
```

### 5.6 风控与熔断（E-1，不变）

三个独立方法，权限高于任何 Engine：

```python
class RiskController:
    def check_stock(self, pnl_pct, close, ma10, ma21) -> FuseLevel: ...
    def check_daily(self, daily_pnl, consecutive_stops) -> FuseLevel: ...
    def check_monthly(self, monthly_pnl) -> FuseLevel: ...
```

### 5.7 API 响应统一（B-3）

```python
# web/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class APIResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str = ""
    timestamp: str = ""

    @classmethod
    def ok(cls, data=None, message="ok"):
        return cls(success=True, data=data, message=message,
                   timestamp=datetime.now().isoformat())

    @classmethod
    def fail(cls, message="error"):
        return cls(success=False, message=message,
                   timestamp=datetime.now().isoformat())
```

所有 API 路由返回值包装为 `APIResponse`，前端统一判断 `success` 字段。

---

## 六、日志系统（A-3）

```python
# config.py 中的日志配置
import logging
import os

def setup_logging(log_dir: str, level: str = "INFO"):
    """初始化三个日志文件 + 控制台输出。"""
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # app.log — 所有 INFO 及以上
    app_handler = logging.FileHandler(f"{log_dir}/app.log", encoding='utf-8')
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    # scheduler.log — 定时任务专用
    sched_handler = logging.FileHandler(f"{log_dir}/scheduler.log", encoding='utf-8')
    sched_handler.setLevel(logging.INFO)
    sched_handler.setFormatter(formatter)

    # error.log — 所有 ERROR 及以上，含完整堆栈
    error_handler = logging.FileHandler(f"{log_dir}/error.log", encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 控制台同步输出
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    root.addHandler(app_handler)
    root.addHandler(sched_handler)
    root.addHandler(error_handler)
    root.addHandler(console)
```

日志不记录行情数据本身（数据在 SQLite 里），只记录：
- 数据拉取的**成功/失败**和条数
- 每个 Engine 计算的**输入/输出摘要**
- 每个 Workflow 步骤的**开始/完成/耗时**
- 所有异常**完整堆栈**

---

## 七、环境配置（B-4）

```bash
# .env.example（提交到 git）
DATABASE_PATH=data/trend_corp.db
LOG_DIR=logs
LOG_LEVEL=INFO
INITIAL_CAPITAL=100000
DATA_CACHE_DIR=data/cache
```

```python
# config.py 中读取
from dotenv import load_dotenv
import os

load_dotenv()  # 如果 .env 不存在，用下方的默认值

@dataclass
class AppConfig:
    db_path: str = os.getenv("DATABASE_PATH", "data/trend_corp.db")
    log_dir: str = os.getenv("LOG_DIR", "logs")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "100000"))
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    screener: CoreScreenerConfig = field(default_factory=CoreScreenerConfig)
    position: PositionConfig = field(default_factory=PositionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
```

---

## 八、数据流

### 周度扫描

```
Scheduler (周日 18:00)
    │
    ▼
WeeklyWorkflow.execute()
    │
    ├─→ MarketProvider.fetch_all_sectors()     # 拉取板块数据
    ├─→ MarketScanner.scan_all()               # B-1 四维评分
    ├─→ ThemeSelector.confirm()                # B-2 主线确认
    ├─→ CoreScreener.screen()                  # C-1 中军五维评分
    └─→ SectorRepo.save() / CoreScoreRepo.save()
    │
    ▼
  logs/app.log  ← 每步都有日志
```

### 日终更新

```
Scheduler (交易日 15:30)
    │
    ▼
DailyWorkflow.execute()
    │
    ├─→ MarketProvider.fetch_*()               # 更新持仓 + 候选池行情
    ├─→ MAMonitor.check_all()                  # C-2 均线状态 + 信号
    ├─→ ThemeMonitor.check_all()               # B-3 退潮预警
    ├─→ RiskController.check_*()               # E-1 熔断检查
    └─→ NavRepo.save_snapshot()                # 净值快照
    │
    ▼
  如有信号变化或熔断触发 → Dashboard 红色提示
```

### 盘中交易（人工）

```
Dashboard 查看信号
    │
    ▼
 人工判断 → 券商 App 执行
    │
    ▼
POST /api/trade/log  ← TradeLogger 录入
```

### 价格轮询（止损监控）

```
APScheduler (每 5 分钟，仅持仓时生效)
    │
    ▼
RiskController.check_stock()
    │
    ├─ 未触发 → 无事发生
    └─ 触发 L1/L2/L3 → Dashboard 弹警告 + error.log 记录
```

---

## 九、API 路由

```python
# ── 页面 ──
GET  /                   → dashboard.html       # 主仪表盘
GET  /scanner            → scanner.html         # 板块扫描 & 主线 & 中军池
GET  /positions          → positions.html       # 持仓 + 风控状态
GET  /journal            → journal.html         # 交易日志列表
GET  /journal/<id>       → journal_detail.html  # 单笔详情
GET  /report             → report.html          # 月度绩效

# ── 数据 API（JSON，统一 APIResponse 格式）──
GET  /api/dashboard      → APIResponse{净值/仓位/熔断状态/持仓快照}
GET  /api/scanner/latest → APIResponse{最新扫描结果}
GET  /api/positions      → APIResponse{当前持仓 + 信号}
GET  /api/risk/status    → APIResponse{熔断等级/触发历史}
GET  /api/nav/history    → APIResponse{净值曲线数据，供 Chart.js}

# ── 操作 API ──
POST /api/trade/log      → APIResponse   # 录入交易
POST /api/workflow/scan  → APIResponse   # 手动触发周度扫描
POST /api/workflow/eod   → APIResponse   # 手动触发日终更新

# ── 配置 API ──
GET  /api/config         → APIResponse{所有策略参数}
PUT  /api/config         → APIResponse   # 更新参数（季度窗口内可用）
```

---

## 十、启动文件

```python
# main.py
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from config import AppConfig
from data.providers.market_provider import MarketProvider
from data.providers.financial_provider import FinancialProvider
from data.providers.announcement_provider import AnnouncementProvider
from engine.scanner.scanner import MarketScanner
from engine.screener.screener import CoreScreener
# ...其他 Engine import
from workflow.weekly_workflow import WeeklyWorkflow
from workflow.daily_workflow import DailyWorkflow
from workflow.monthly_workflow import MonthlyWorkflow
from scheduler.jobs import register_jobs
from web.router import router

app = FastAPI(title="趋势中军交易系统", version="1.1")
app.include_router(router)

@app.on_event("startup")
async def startup():
    cfg = AppConfig()
    setup_logging(cfg.log_dir, cfg.log_level)
    logger = logging.getLogger("main")
    logger.info("趋势中军交易系统 v1.1 启动")

    # 初始化 Provider
    market = MarketProvider()
    financial = FinancialProvider()
    announcement = AnnouncementProvider()

    # 初始化 Repository
    sector_repo = SectorRepository(cfg.db_path)
    # ...其余 repo

    # 初始化 Engine
    scanner = MarketScanner(market, cfg.scanner.weights, cfg.scanner.threshold)
    screener = CoreScreener(market, financial, cfg.screener.weights, cfg.screener.threshold)
    # ...其余 engine

    # 初始化 Workflow
    weekly = WeeklyWorkflow(market, scanner, theme_selector, screener, sector_repo, core_score_repo)
    daily = DailyWorkflow(market, ma_monitor, theme_monitor, risk_ctrl, nav_repo)
    monthly = MonthlyWorkflow(trade_repo, nav_repo)

    # 注册定时任务
    scheduler = BackgroundScheduler()
    register_jobs(scheduler, weekly, daily, monthly)
    scheduler.start()
    logger.info("定时任务已注册")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 十一、实施优先级（更新后）

| 迭代 | 范围 | 新增 vs v1.0 |
|------|------|:---:|
| **v0.1** | 日志系统 + `.env` + Provider 拆分 + SQLite 建表 + 行情拉取 | A-3, B-2, B-4 |
| **v0.2** | scanner/ + screener/ Engine 拆分 + Repository 拆分 | A-1, A-2 |
| **v0.3** | Workflow 层 + theme_selector + ma_monitor | B-1 |
| **v0.4** | position_manager + risk_controller + order_executor | — |
| **v0.5** | FastAPI + schemas + Dashboard HTML | B-3 |
| **v0.6** | Scheduler 定时任务 + 月报 | — |
| **v1.0** | 完整前端 + Chart.js + 端到端联调 | — |
