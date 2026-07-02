# 趋势中军交易系统 —— 软件系统架构

> 版本 v1.0 | 2026-07-02
> 目标部署环境：个人开发机器（Windows/macOS/Linux），单用户

---

## 一、技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| **语言** | Python 3.11+ | 金融数据生态最完善（akshare/pandas/numpy） |
| **Web 框架** | FastAPI | 异步支持、自动 OpenAPI 文档、轻量 |
| **前端** | Jinja2 模板 + HTMX + Chart.js | 极简、无需 Node.js 工具链、单文件部署 |
| **数据库** | SQLite（单机） | 零配置、零运维、足够支撑单用户 10 年数据 |
| **任务调度** | APScheduler | 轻量、内嵌于 Python 进程、无需 Redis/RabbitMQ |
| **数据源** | akshare（免费开源） | 覆盖 A 股行情/板块/财务/资金流/公告 |
| **部署** | 单进程 FastAPI + APScheduler → 本地 localhost | 个人用不需要容器化 |

> **为什么不用**：
> - 没用 PostgreSQL → 单用户几万条数据，SQLite 完全够，且无需安装维护
> - 没用 Redis → 无高并发需求，内存缓存用 Python dict
> - 没用 React/Vue → 增加工具链复杂度，HTMX 交互足够
> - 没用 Docker → 个人单机部署，直接 `python main.py` 最快

---

## 二、项目结构

```
TrendCorp/
├── main.py                    # 应用入口，启动 FastAPI + APScheduler
├── config.py                  # 集中配置（阈值、权重、路径）
├── requirements.txt           # Python 依赖
│
├── data/                      # 数据层
│   ├── fetcher.py             # akshare 数据拉取封装
│   ├── schema.sql             # SQLite 建表语句
│   └── repository.py          # 数据库 CRUD 封装
│
├── engine/                    # 核心引擎（对应 ARCHITECTURE.md 子系统）
│   ├── market_scanner.py      # B-1 板块扫描器
│   ├── theme_selector.py      # B-2 主线确认器
│   ├── theme_monitor.py       # B-3 主线退潮预警器
│   ├── core_screener.py       # C-1 中军评分模型
│   ├── ma_monitor.py          # C-2 均线状态监控器
│   ├── position_manager.py    # D-1 仓位管理器
│   ├── order_executor.py      # D-2 订单执行器（生成指令，非自动下单）
│   ├── risk_controller.py     # E-1 三级熔断器
│   └── dashboard.py           # E-2 实时监控数据聚合
│
├── journal/                   # 复盘层
│   ├── trade_logger.py        # F-1 交易日志
│   ├── monthly_report.py      # F-2 月度绩效归因
│   └── param_tuner.py         # F-3 季度参数优化
│
├── web/                       # Web 展示层
│   ├── router.py              # FastAPI 路由定义
│   ├── templates/             # Jinja2 模板
│   │   ├── base.html
│   │   ├── dashboard.html     # 主仪表盘
│   │   ├── scanner.html       # 板块扫描 & 主线
│   │   ├── watchlist.html     # 中军候选池
│   │   ├── positions.html     # 当前持仓
│   │   ├── journal.html       # 交易日志
│   │   └── report.html        # 月度报告
│   └── static/
│       ├── style.css
│       └── app.js             # HTMX 交互 + Chart.js 图表
│
├── scheduler/                 # 定时任务
│   └── jobs.py                # 周度扫描、日终更新、月报生成
│
└── tests/                     # 测试
    ├── test_scanner.py
    ├── test_screener.py
    └── test_risk.py
```

---

## 三、数据库设计

```sql
-- ============================================
-- 板块表
-- ============================================
CREATE TABLE sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,       -- 申万/概念板块代码
    name            TEXT NOT NULL,              -- 板块名称
    type            TEXT NOT NULL,              -- 'sw_industry' | 'concept'
    is_active       INTEGER DEFAULT 1,         -- 是否仍在跟踪
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 板块扫描快照（每周一条/B-1输出）
-- ============================================
CREATE TABLE sector_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_id       INTEGER REFERENCES sector(id),
    snap_date       TEXT NOT NULL,              -- 快照日期

    -- B-1 四大评分维度
    trend_score     REAL,                       -- 趋势强度 (0-1)
    rel_strength    REAL,                       -- 相对强度 (0-1)
    fund_score      REAL,                       -- 资金确认 (0-1)
    echelon_score   REAL,                       -- 梯队完整性 (0-1)
    total_score     REAL,                       -- 加权总分

    -- 原始指标（便于回溯分析）
    ma5            REAL,                        -- 板块指数 MA5
    ma10           REAL,                        -- 板块指数 MA10
    ma21           REAL,                        -- 板块指数 MA21
    ma55           REAL,                        -- 板块指数 MA55
    ret_20d        REAL,                        -- 板块近 20 日涨幅
    hs300_ret_20d  REAL,                        -- 同期沪深 300 涨幅
    fund_flow_5d   REAL,                        -- 近 5 日主力净流入(亿)
    limit_up_cnt   INTEGER,                     -- 近 5 日涨停家数
    volume_ratio   REAL,                        -- 成交额占比 / 市值占比

    -- B-2 主线确认
    is_confirmed    INTEGER DEFAULT 0,          -- 0=排除 1=观察 2=确认主线
    confirm_reason  TEXT,                       -- 确认理由

    -- B-3 退潮预警
    alert_level     INTEGER DEFAULT 0,          -- 0=正常 1=减仓 2=退出
    alert_triggers  TEXT,                       -- 触发项列表

    UNIQUE(sector_id, snap_date)
);

-- ============================================
-- 个股表
-- ============================================
CREATE TABLE stock (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,       -- 如 '000001'
    name            TEXT NOT NULL,
    sector_id       INTEGER REFERENCES sector(id),
    market_cap      REAL,                       -- 流通市值(亿)
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 中军评分快照（每日/C-1输出）
-- ============================================
CREATE TABLE core_score_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER REFERENCES stock(id),
    snap_date       TEXT NOT NULL,

    -- C-1 五维评分
    market_cap_score    REAL,                   -- 市值规模 (0-1)
    liquidity_score     REAL,                   -- 流动性 (0-1)
    ma_structure_score  REAL,                   -- 均线结构 (0-1)
    vol_health_score    REAL,                   -- 量价健康度 (0-1)
    fundamental_score   REAL,                   -- 基本面质量 (0-1)
    total_score         REAL,                   -- 加权总分

    -- C-2 均线状态
    price           REAL,
    ma5             REAL,
    ma10            REAL,
    ma21            REAL,
    ma55            REAL,
    ma_deviation    REAL,                       -- 价格距 MA10 偏离百分比
    vol_ratio_20    REAL,                       -- 当日量 / 20日均量
    signal          TEXT,                       -- 'A_BUY' | 'B_BUY' | 'HOLD' | 'REDUCE' | 'EXIT'

    UNIQUE(stock_id, snap_date)
);

-- ============================================
-- 交易记录表（F-1）
-- ============================================
CREATE TABLE trade (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_no        TEXT NOT NULL UNIQUE,       -- T-YYYYMMDD-NNN
    stock_id        INTEGER REFERENCES stock(id),
    sector_id       INTEGER REFERENCES sector(id),
    direction       TEXT NOT NULL,              -- 'LONG'

    open_date       TEXT NOT NULL,
    open_price      REAL NOT NULL,
    open_reason     TEXT NOT NULL,              -- 'A_MA10_BOUNCE' | 'B_SECTOR_BREAK' | 'OTHER'
    open_ma10       REAL,
    open_position   REAL,                       -- 开仓仓位占比

    close_date      TEXT,
    close_price     REAL,
    close_reason    TEXT,                       -- 'TAKE_PROFIT','MA10_BREAK','MA21_BREAK','STOP_LOSS','SECTOR_EXIT'
    pnl_amount      REAL,
    pnl_pct         REAL,

    -- 复盘
    rule_compliant  INTEGER DEFAULT 1,          -- 是否合规
    deviation_note  TEXT,                       -- 如果有偏差，记录原因
    lesson          TEXT,                       -- 交易教会我的

    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 持仓表（当前状态/实时更新）
-- ============================================
CREATE TABLE position (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER REFERENCES stock(id),
    trade_id        INTEGER REFERENCES trade(id),
    shares          INTEGER NOT NULL,           -- 持有股数
    avg_cost        REAL NOT NULL,              -- 持仓均价
    current_price   REAL,                       -- 最新价格
    position_pct    REAL,                       -- 占净值百分比
    unrealized_pnl  REAL,                       -- 浮动盈亏

    ma10            REAL,
    ma21            REAL,
    ma10_status     TEXT,                       -- 'ABOVE' | 'BELOW'
    sector_alert    INTEGER DEFAULT 0,          -- 所属板块退潮预警等级

    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================
-- 风控日志表（E-1 熔断记录）
-- ============================================
CREATE TABLE risk_event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time      TEXT NOT NULL,
    event_type      TEXT NOT NULL,              -- 'STOCK_LOSS_8PCT' | 'DAILY_DD_3PCT' | 'WEEKLY_DD_5PCT'
                                                -- | 'MONTHLY_DD_10PCT' | 'CONSECUTIVE_STOP' | 'STRATEGY_DD_15PCT'
    event_level     TEXT NOT NULL,              -- 'L1_STOCK' | 'L2_DAILY' | 'L3_MONTHLY'
    detail          TEXT,
    action_taken    TEXT,                       -- 执行的措施
    resolved_at     TEXT                        -- 解禁时间
);

-- ============================================
-- 每日净值快照
-- ============================================
CREATE TABLE nav_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snap_date       TEXT NOT NULL UNIQUE,
    total_value      REAL NOT NULL,
    cash            REAL NOT NULL,
    positions_value REAL NOT NULL,
    daily_return    REAL,
    weekly_return   REAL,
    monthly_return  REAL,
    max_drawdown    REAL,
    position_pct    REAL                        -- 当前仓位占比
);
```

---

## 四、核心模块设计

### 4.1 数据拉取层 — `data/fetcher.py`

```python
"""
数据拉取封装。所有外部数据入口归一化到这个模块。
更换数据源只需改这个文件。
"""
from dataclasses import dataclass
from datetime import date
import akshare as ak
import pandas as pd

@dataclass
class DataFetcher:

    # ---- 板块数据 ----
    def fetch_sector_list(self) -> pd.DataFrame:
        """获取申万行业 + 概念板块列表"""
        pass

    def fetch_sector_daily(self, sector_code: str, start: date, end: date) -> pd.DataFrame:
        """板块日K（OHLCV + 成交额）"""
        pass

    def fetch_sector_fund_flow(self, sector_code: str, days: int = 5) -> pd.DataFrame:
        """板块主力资金净流入"""
        pass

    def fetch_sector_limit_up(self, sector_code: str, days: int = 5) -> int:
        """板块近N日涨停家数"""
        pass

    # ---- 个股数据 ----
    def fetch_stock_daily(self, code: str, start: date, end: date) -> pd.DataFrame:
        """个股日K + 均线计算"""
        pass

    def fetch_stock_financials(self, code: str) -> dict:
        """最近季度：营收增速、净利润增速、ROE、毛利率"""
        pass

    def fetch_stock_market_cap(self, code: str) -> float:
        """流通市值（亿）"""
        pass

    def fetch_index_daily(self, index_code: str, start: date, end: date) -> pd.DataFrame:
        """指数日K（沪深300等）"""
        pass

    # ---- 公告 ----
    def fetch_announcements(self, code: str, days: int = 30) -> list[dict]:
        """最近公告：业绩预告、重大合同、分析师覆盖"""
        pass
```

### 4.2 板块扫描器 — `engine/market_scanner.py`

```python
"""
B-1 板块扫描器。
每周执行一次，输出所有板块的四维评分。
"""
from dataclasses import dataclass, field
from datetime import date

@dataclass
class SectorScanResult:
    sector_code: str
    sector_name: str
    trend_score: float        # 0-1 趋势强度
    rel_strength: float       # 0-1 相对强度
    fund_score: float         # 0-1 资金确认
    echelon_score: float      # 0-1 梯队完整性
    total_score: float        # 加权总分

@dataclass
class MarketScanner:
    fetcher: 'DataFetcher'
    weights: dict = field(default_factory=lambda: {
        'trend': 0.35, 'rel_strength': 0.25,
        'fund': 0.25, 'echelon': 0.15
    })
    candidate_threshold: float = 0.6

    def scan_all(self, scan_date: date) -> list[SectorScanResult]:
        """
        1. 遍历全市场 ~200 个板块
        2. 计算每个板块的四维评分
        3. 返回 total_score >= 0.6 的候选列表，按评分降序
        """
        pass

    def _calc_trend_score(self, sector_code: str, scan_date: date) -> float:
        """MA5 > MA10 > MA21 > MA55，每满足一级 0.25 分"""
        pass

    def _calc_rel_strength(self, sector_code: str, scan_date: date) -> float:
        """近 20 日涨幅 / 沪深 300 涨幅，映射到 0-1"""
        pass

    def _calc_fund_score(self, sector_code: str, scan_date: date) -> float:
        """资金流 + 成交额占比"""
        pass

    def _calc_echelon_score(self, sector_code: str, scan_date: date) -> float:
        """涨停家数 + 大市值标的存在性"""
        pass
```

### 4.3 中军评分模型 — `engine/core_screener.py`

```python
"""
C-1 中军评分模型。
在主线的板块内，对所有成分股进行五维评分。
"""
@dataclass
class CoreScoreResult:
    stock_code: str
    stock_name: str
    market_cap_score: float      # 0-1 市值规模
    liquidity_score: float       # 0-1 流动性
    ma_structure_score: float    # 0-1 均线结构
    vol_health_score: float      # 0-1 量价健康度
    fundamental_score: float     # 0-1 基本面质量
    total_score: float

@dataclass
class CoreScreener:
    weights: dict = field(default_factory=lambda: {
        'market_cap': 0.15, 'liquidity': 0.20,
        'ma_structure': 0.25, 'vol_health': 0.25,
        'fundamental': 0.15
    })
    score_threshold: float = 0.65          # 合格中军最低分
    top_n_per_sector: int = 2              # 每个板块只取前 N 名

    def screen(self, sector_code: str, snap_date: date) -> list[CoreScoreResult]:
        """返回该板块评分最高的 ≤2 只中军标的"""
        pass
```

### 4.4 仓位管理器 — `engine/position_manager.py`

```python
"""
D-1 仓位管理器。纯计算模块，不操作资金。
"""
from enum import Enum

class SignalType(Enum):
    A_BUY   = "A级买点_MA10回踩企稳"
    B_BUY   = "B级买点_板块共振启动"
    ADD     = "加仓_回踩确认"
    REDUCE  = "减仓_MA10破位"
    EXIT    = "清仓_MA21破位或板块退潮"

class TradeOrder(NamedTuple):
    stock_code: str
    direction: str              # 'BUY' | 'SELL'
    target_pct: float           # 目标仓位百分比
    price_type: str             # 'LIMIT' | 'MARKET'
    limit_price: float | None   # 限价（限价单时有效）

@dataclass
class PositionManager:
    total_nav: float            # 当前总净值
    total_cap: float = 0.70     # 总仓位上限
    single_cap: float = 0.30    # 单票上限
    sector_cap: float = 0.35    # 单板块上限
    cash_min: float = 0.30      # 最低现金保留

    def calc_order(self, signal: SignalType, stock_code: str,
                   current_position_pct: float, ma10: float) -> TradeOrder | None:
        """
        输入：信号类型、当前仓位、MA10 值
        输出：交易指令（或 None 表示无需操作）
        """
        pass

    def _calc_buy_qty(self, target_pct: float) -> TradeOrder:
        """建仓：A级→目标仓位50%，B级→目标仓位30%"""
        pass
```

### 4.5 三级熔断器 — `engine/risk_controller.py`

```python
"""
E-1 三级熔断器。
权限最高，输出是强制性的。
"""
from enum import Enum

class FuseLevel(Enum):
    NORMAL          = 0   # 正常
    STOCK_STOP      = 1   # 个股止损
    DAILY_BAN       = 2   # 日内禁开新仓
    WEEKLY_BAN      = 3   # 本周禁开新仓
    MONTHLY_BAN     = 4   # 月度熔断

class RiskController:

    def check_stock(self, stock_code: str, unrealized_pnl_pct: float,
                    close_price: float, ma10: float, ma21: float) -> FuseLevel:
        """个股级检查：-8%止损、MA10破位、MA21破位"""
        if unrealized_pnl_pct <= -0.08:
            return FuseLevel.STOCK_STOP
        if close_price < ma21:
            return FuseLevel.STOCK_STOP
        if close_price < ma10:
            return FuseLevel.STOCK_STOP  # 第二天减半，但标记
        return FuseLevel.NORMAL

    def check_daily(self, daily_pnl_pct: float, consecutive_stops: int) -> FuseLevel:
        """日内级检查：日回撤-3%、连续2次止损"""
        if daily_pnl_pct <= -0.03 or consecutive_stops >= 2:
            return FuseLevel.DAILY_BAN
        return FuseLevel.NORMAL

    def check_weekly(self, weekly_pnl_pct: float) -> FuseLevel:
        """周度级检查：周回撤-5%"""
        if weekly_pnl_pct <= -0.05:
            return FuseLevel.WEEKLY_BAN
        return FuseLevel.NORMAL

    def check_monthly(self, monthly_pnl_pct: float) -> FuseLevel:
        """月度级检查：月回撤-10%"""
        if monthly_pnl_pct <= -0.10:
            return FuseLevel.MONTHLY_BAN
        return FuseLevel.NORMAL
```

---

## 五、数据流

### 5.1 周度扫描流（每周日触发）

```
APScheduler (周日 18:00)
    │
    ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ DataFetcher  │───→│ MarketScanner │───→│ThemeSelector │
│ 拉取全市场    │    │ B-1 四维评分   │    │ B-2 主线确认   │
│ 板块+指数数据  │    │ 输出候选列表   │    │ 输出确认主线   │
└─────────────┘    └──────────────┘    └──────┬───────┘
                                              │
                    ┌─────────────────────────┘
                    ▼
            ┌──────────────┐    ┌──────────────┐
            │ CoreScreener │───→│  SQLite      │
            │ C-1 中军筛选   │    │ sector_snapshot
            │ 每板块≤2只     │    │ core_score_snapshot
            └──────────────┘    └──────────────┘
```

### 5.2 日终更新流（每日收盘后触发）

```
APScheduler (每日 15:30)
    │
    ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ DataFetcher  │───→│ MAMonitor    │───→│ThemeMonitor  │
│ 拉取持仓+候选  │    │ C-2 均线状态   │    │ B-3 退潮预警   │
│ 当日行情      │    │ 生成买卖点信号  │    │ 生成减仓/退出   │
└─────────────┘    └──────┬───────┘    └──────┬───────┘
                          │                    │
                          └──────┬─────────────┘
                                 ▼
                         ┌──────────────┐
                         │ SQLite       │
                         │ core_score   │
                         │ sector_snap  │
                         │ position     │
                         │ nav_snapshot │
                         └──────────────┘
```

### 5.3 盘中交易流（人工触发 / 信号提醒）

```
用户查看 Dashboard
    │
    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Dashboard    │───→│PositionMgr   │───→│OrderExecutor │
│ 查看买卖点信号 │    │ D-1 仓位计算   │    │ D-2 生成指令   │
│ 决定是否执行   │    │ 目标仓位%     │    │ (不自动下单)   │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
                                       ┌──────────────┐
                                       │ 人工在券商App │
                                       │ 执行交易      │
                                       └──────┬───────┘
                                               │
                                               ▼
                                       ┌──────────────┐
                                       │ TradeLogger  │
                                       │ F-1 记录交易   │
                                       └──────────────┘
```

### 5.4 事件驱动流（止损实时）

```
APScheduler (每 5 分钟轮询价格，或手动刷新)
    │
    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ DataFetcher  │───→│RiskController│───→│ 触发了？       │
│ 实时拉取持仓价 │    │ E-1 三级熔断   │    │              │
└──────────────┘    └──────────────┘    └──┬──┬────┬──┘
                                           │  │    │
                                     L1个股 │ L2日│L3月
                                           │  │    │
                                           ▼  ▼    ▼
                                    ┌──────────────────┐
                                    │ Dashboard 红色警告 │
                                    │ + 邮件/通知提醒    │
                                    │ + 人工确认后执行   │
                                    └──────────────────┘
```

---

## 六、API 路由设计

```python
# web/router.py

# ── 页面路由 ──
GET  /                          → dashboard.html       # 主仪表盘
GET  /scanner                   → scanner.html         # 主线扫描 & 中军池
GET  /watchlist                 → watchlist.html       # 中军候选 + 均线状态
GET  /positions                 → positions.html       # 当前持仓 + 风控状态
GET  /journal                   → journal.html         # 交易日志列表
GET  /journal/<trade_no>        → journal_detail.html  # 单笔交易详情
GET  /report                    → report.html          # 月度绩效报告

# ── 数据 API（HTMX 局部刷新）──
GET  /api/dashboard/summary     → JSON  # 净值概览 + 熔断状态 + 持仓快照
GET  /api/scanner/latest        → JSON  # 最新一期扫描结果（候选+确认主线）
GET  /api/scanner/history       → JSON  # 历史扫描记录（图表用）
GET  /api/watchlist/scores      → JSON  # 当前中军池 + 评分 + 均线信号
GET  /api/positions/current     → JSON  # 实时持仓
GET  /api/risk/status           → JSON  # 当前风控状态
GET  /api/risk/events           → JSON  # 风控事件历史
GET  /api/performance/nav       → JSON  # 净值曲线数据（Chart.js）
GET  /api/performance/monthly   → JSON  # 月度收益表

# ── 操作 API ──
POST /api/trade/log             → JSON  # 手动记录一笔交易（从券商App执行后在系统录入）
POST /api/trade/eval            → JSON  # 提交复盘评估
POST /api/scheduler/run_scan    → JSON  # 手动触发周度扫描
POST /api/scheduler/run_eod     → JSON  # 手动触发日终更新

# ── 配置 API ──
GET  /api/config                → JSON  # 当前参数（权重、阈值）
PUT  /api/config                → JSON  # 更新参数（需要确认）
```

---

## 七、定时任务

```python
# scheduler/jobs.py

from apscheduler.schedulers.background import BackgroundScheduler

def register_jobs(scheduler: BackgroundScheduler):
    """
    所有定时任务在此注册。
    均在本地时区执行。
    """

    # 每周日 18:00 — 周度主线扫描
    scheduler.add_job(
        weekly_scan,
        trigger='cron', day_of_week='sun', hour=18, minute=0,
        id='weekly_scan'
    )

    # 每个交易日 15:30 — 日终更新
    scheduler.add_job(
        daily_eod,
        trigger='cron', day_of_week='mon-fri', hour=15, minute=30,
        id='daily_eod'
    )

    # 每个交易日 9:25 — 开盘前快照（竞价结束后）
    scheduler.add_job(
        pre_market_snapshot,
        trigger='cron', day_of_week='mon-fri', hour=9, minute=25,
        id='pre_market'
    )

    # 盘中每 5 分钟 — 价格轮询（仅在有持仓时生效）
    scheduler.add_job(
        intraday_price_check,
        trigger='interval', minutes=5,
        id='intraday_check'
    )

    # 每月最后一天 16:00 — 月度绩效报告
    scheduler.add_job(
        monthly_report,
        trigger='cron', day='last', hour=16, minute=0,
        id='monthly_report'
    )
```

---

## 八、前端页面布局

### 主仪表盘 (`/`)

```
┌──────────────────────────────────────────────────┐
│  📊 趋势中军 | 2026-07-02                        │
├────────────┬──────────┬──────────┬───────────────┤
│ 总净值      │ 今日     │ 本周     │ 本月          │
│ ¥112,350   │ +1.23%  │ +2.15%  │ +4.87%       │
├────────────┴──────────┴──────────┴───────────────┤
│ 熔断状态：🟢 正常  │ 仓位：52% │ 可用：¥53,200  │
├──────────────────────────────────────────────────┤
│                                                  │
│  📈 净值曲线（近3个月）                            │
│  [Chart.js 折线图]                                │
│                                                  │
├──────────────────────────────────────────────────┤
│  当前持仓         信号    浮盈     MA10  板块预警   │
│  ───────────────────────────────────────────────│
│  000001 平安银行  HOLD   +5.2%   ABOVE  🟢正常   │
│  600519 贵州茅台  A_BUY  +1.8%   NEAR   🟢正常   │
│  002415 海康威视  HOLD   -2.1%   ABOVE  🟡观察   │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 主线扫描页 (`/scanner`)

```
┌──────────────────────────────────────────────────┐
│  🔍 板块扫描 | 更新于 2026-06-28                   │
├──────────────────────────────────────────────────┤
│                                                  │
│  确认主线（2）：                                   │
│  ┌──────────────────────────────────────┐        │
│  │ 🥇 AI算力     总分 0.87  趋势▮▮▮▮ 资金▮▮▮▮ │  │
│  │   中军候选：中际旭创、工业富联              │  │
│  │   退潮预警：🟢 暂无                       │  │
│  └──────────────────────────────────────┘        │
│  ┌──────────────────────────────────────┐        │
│  │ 🥈 半导体设备  总分 0.73  趋势▮▮▮▮ 资金▮▮▮▬ │  │
│  │   中军候选：北方华创、中微公司              │  │
│  │   退潮预警：🟢 暂无                       │  │
│  └──────────────────────────────────────┘        │
│                                                  │
│  ── 观察主线 ────────────────────────────────    │
│  🥉 电力设备 0.68  |  消费电子 0.65  |  化工 0.62 │
│                                                  │
│  ── 退潮预警 ────────────────────────────────    │
│  🔴 游戏传媒  连续3天跑输+涨停萎缩+成交缩减       │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 九、config.py 配置汇总

```python
"""
所有可调参数集中管理。支持运行时通过 API 修改。
"""
from dataclasses import dataclass, field

@dataclass
class ScannerConfig:
    """B-1 板块扫描器参数"""
    weights: dict = field(default_factory=lambda: {
        'trend': 0.35, 'rel_strength': 0.25,
        'fund': 0.25, 'echelon': 0.15
    })
    candidate_threshold: float = 0.6          # 进入候选的最低总分
    confirmed_threshold: float = 3.0          # B-2 主线确认最低分(0-4)

@dataclass
class CoreScreenerConfig:
    """C-1 中军评分参数"""
    weights: dict = field(default_factory=lambda: {
        'market_cap': 0.15, 'liquidity': 0.20,
        'ma_structure': 0.25, 'vol_health': 0.25,
        'fundamental': 0.15
    })
    score_threshold: float = 0.65             # 合格中军最低分
    top_n_per_sector: int = 2                 # 每个板块取前 N
    market_cap_range: tuple = (100, 500)      # 最优市值范围(亿)

@dataclass
class PositionConfig:
    """D-1 仓位管理参数"""
    total_cap: float = 0.70                   # 总仓位上限
    single_cap: float = 0.30                  # 单票上限
    sector_cap: float = 0.35                  # 单板块上限
    cash_min: float = 0.30                    # 最低现金保留
    a_buy_first_pct: float = 0.50             # A级首次建仓比例
    b_buy_first_pct: float = 0.30             # B级首次建仓比例

@dataclass
class RiskConfig:
    """E-1 风控参数"""
    stock_loss_limit: float = -0.08           # 个股止损线
    daily_dd_limit: float = -0.03             # 日熔断线
    weekly_dd_limit: float = -0.05            # 周熔断线
    monthly_dd_limit: float = -0.10           # 月熔断线
    strategy_dd_limit: float = -0.15          # 策略熔断线
    consecutive_stop_limit: int = 2           # 连续止损阈值

@dataclass
class AppConfig:
    """应用总配置"""
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    screener: CoreScreenerConfig = field(default_factory=CoreScreenerConfig)
    position: PositionConfig = field(default_factory=PositionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    db_path: str = "data/trend_corp.db"
    initial_capital: float = 100_000.0
```

---

## 十、初始化与部署

```bash
# requirements.txt
fastapi==0.115.*
uvicorn==0.34.*
akshare>=1.16
pandas>=2.2
numpy>=2.1
jinja2>=3.1
apscheduler>=3.10
plotly>=5.24    # 可选：交互式图表

# 启动命令
cd TrendCorp
pip install -r requirements.txt
python main.py
# → 访问 http://localhost:8000
```

```python
# main.py
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from web.router import router
from scheduler.jobs import register_jobs
from data.repository import init_db

app = FastAPI(title="趋势中军交易系统", version="1.0")
app.include_router(router)

@app.on_event("startup")
async def startup():
    init_db()                                      # 建表
    scheduler = BackgroundScheduler()
    register_jobs(scheduler)
    scheduler.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 十一、实现优先级

按 MVP 迭代，不追求一次性完整：

| 迭代 | 内容 | 可验证的产出 |
|------|------|------------|
| **v0.1（2周）** | 数据层 + SQLite 建表 + 日K 拉取成功 | `python main.py` 后数据库有行情数据 |
| **v0.2（2周）** | B-1 板块扫描 + B-2 主线确认 + 终端输出 | 每周日能打印出"确认主线：AI算力 0.87" |
| **v0.3（2周）** | C-1 中军评分 + C-2 均线信号 | 每天能输出中军池的 MA10 偏离值和信号 |
| **v0.4（1周）** | D-1 仓位管理 + 基础 HTML 仪表盘 | 浏览器看到持仓和信号 |
| **v0.5（1周）** | E-1 熔断 + F-1 日志 | 手动输入一笔交易 → 数据库有记录 |
| **v0.6（1周）** | 周度/日度定时任务 + F-2 月度报告 | 系统自动在周日跑扫描，月末出报告 |
| **v1.0（1周）** | 前端完整仪表盘 + Chart.js 图表 | 所有页面可用，日常只需 10 分钟 |
