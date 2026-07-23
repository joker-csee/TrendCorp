-- 趋势中军交易系统 v1.0 — SQLite 建表脚本
-- 共 9 张表，含外键约束和索引

-- ============================================================
-- 板块表
-- ============================================================
CREATE TABLE IF NOT EXISTS sector (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('industry', 'concept')),
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 板块扫描快照（每周一条 / B-1 输出）
-- ============================================================
CREATE TABLE IF NOT EXISTS sector_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_id       INTEGER NOT NULL REFERENCES sector(id),
    snap_date       TEXT NOT NULL,

    trend_score     REAL,
    rel_strength    REAL,
    fund_score      REAL,
    echelon_score   REAL,
    total_score     REAL,

    ma5             REAL,
    ma10            REAL,
    ma21            REAL,
    ma55            REAL,
    ret_20d         REAL,
    hs300_ret_20d   REAL,
    fund_flow_5d    REAL,
    limit_up_cnt    INTEGER,
    volume_ratio    REAL,

    is_confirmed    INTEGER DEFAULT 0,
    confirm_reason  TEXT,
    alert_level     INTEGER DEFAULT 0,
    alert_triggers  TEXT,

    UNIQUE(sector_id, snap_date)
);

-- ============================================================
-- 个股表
-- ============================================================
CREATE TABLE IF NOT EXISTS stock (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    sector_id       INTEGER REFERENCES sector(id),
    market_cap      REAL,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 中军评分快照（每日 / C-1 输出）
-- ============================================================
CREATE TABLE IF NOT EXISTS core_score_snapshot (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id            INTEGER NOT NULL REFERENCES stock(id),
    snap_date           TEXT NOT NULL,

    market_cap_score    REAL,
    liquidity_score     REAL,
    ma_structure_score  REAL,
    vol_health_score    REAL,
    fundamental_score   REAL,
    total_score         REAL,

    price               REAL,
    ma5                 REAL,
    ma10                REAL,
    ma21                REAL,
    ma55                REAL,
    ma_deviation        REAL,
    vol_ratio_20        REAL,
    signal              TEXT,

    UNIQUE(stock_id, snap_date)
);

-- ============================================================
-- 交易记录表（F-1）
-- ============================================================
CREATE TABLE IF NOT EXISTS trade (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_no        TEXT NOT NULL UNIQUE,
    stock_id        INTEGER REFERENCES stock(id),
    sector_id       INTEGER REFERENCES sector(id),
    direction       TEXT NOT NULL DEFAULT 'LONG',

    open_date       TEXT NOT NULL,
    open_price      REAL NOT NULL,
    open_reason     TEXT NOT NULL,
    open_ma10       REAL,
    open_position   REAL,

    close_date      TEXT,
    close_price     REAL,
    close_reason    TEXT,
    pnl_amount      REAL,
    pnl_pct         REAL,

    rule_compliant  INTEGER DEFAULT 1,
    deviation_note  TEXT,
    lesson          TEXT,

    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 持仓表（当前状态）
-- ============================================================
CREATE TABLE IF NOT EXISTS position (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER UNIQUE REFERENCES stock(id),
    trade_id        INTEGER REFERENCES trade(id),
    shares          INTEGER NOT NULL DEFAULT 0,
    avg_cost        REAL NOT NULL,
    current_price   REAL,
    position_pct    REAL,
    unrealized_pnl  REAL,

    ma10            REAL,
    ma21            REAL,
    ma10_status     TEXT,
    sector_alert    INTEGER DEFAULT 0,

    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- 风控日志表（E-1）
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    event_level     TEXT NOT NULL,
    detail          TEXT,
    action_taken    TEXT,
    resolved_at     TEXT
);

-- ============================================================
-- 每日净值快照
-- ============================================================
CREATE TABLE IF NOT EXISTS nav_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snap_date       TEXT NOT NULL UNIQUE,
    total_value     REAL NOT NULL,
    cash            REAL NOT NULL,
    positions_value REAL NOT NULL,
    daily_return    REAL,
    weekly_return   REAL,
    monthly_return  REAL,
    max_drawdown    REAL,
    position_pct    REAL
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sector_snapshot_date ON sector_snapshot(snap_date);
CREATE INDEX IF NOT EXISTS idx_core_score_snapshot_date ON core_score_snapshot(snap_date);
CREATE INDEX IF NOT EXISTS idx_trade_open_date ON trade(open_date);
CREATE INDEX IF NOT EXISTS idx_nav_snapshot_date ON nav_snapshot(snap_date);
CREATE INDEX IF NOT EXISTS idx_risk_event_time ON risk_event(event_time);
