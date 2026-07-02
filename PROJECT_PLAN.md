# 趋势中军交易系统 —— 项目计划与测试用例

> 版本 v1.0 | 2026-07-02
> 基于 SYSTEM_ARCHITECTURE.md v1.1
> 目标：10 周内交付可用的 V1.0

---

## 一、里程碑总览

```
 Week 1-2          Week 3-4         Week 5-6         Week 7-8        Week 9-10
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  M1      │    │  M2      │    │  M3      │    │  M4      │    │  M5      │
│ v0.1     │───→│ v0.2     │───→│ v0.3     │───→│ v0.4     │───→│ v1.0     │
│ 数据底座  │    │ 核心引擎  │    │ 流程编排  │    │ 风控仓位  │    │ Web交付   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
  里程碑验收      里程碑验收       里程碑验收       里程碑验收       里程碑验收
  SQLite有数据    Scanner输出      Workflow跑通    熔断触发正确    浏览器可用
```

| 里程碑 | 版本 | 周 | 核心目标 | 验收标准 |
|--------|------|:--:|------|---------|
| **M1** | v0.1 | 1-2 | 数据底座可用 | SQLite 中有完整的板块/个股/指数日K数据，日志正常输出 |
| **M2** | v0.2 | 3-4 | 核心引擎可用 | 终端打印出正确的板块扫描结果和中军评分排序 |
| **M3** | v0.3 | 5-6 | 流程编排可用 | 手动触发 weekly_workflow，完整跑通 5 步流程无异常 |
| **M4** | v0.4 | 7-8 | 风控仓位可用 | 模拟触发各种止损场景，熔断器全部正确响应 |
| **M5** | v1.0 | 9-10 | 完整系统可用 | 浏览器打开 Dashboard，查看信号、录入交易、查看报告 |

---

## 二、M1: v0.1 — 数据底座（Week 1-2）

### 2.1 开发任务

| 编号 | 任务 | 预估 | 依赖 | 产出 |
|------|------|:--:|------|------|
| T1.1 | 项目骨架初始化 | 2h | — | `main.py`、`config.py`、`requirements.txt` 可运行 |
| T1.2 | `.env` 环境配置 | 1h | T1.1 | `.env.example` + `config.py` 从 `.env` 读取 |
| T1.3 | 日志系统 | 2h | T1.1 | `setup_logging()` 三文件输出，启动时可见日志 |
| T1.4 | SQLite 建表 | 3h | T1.1 | `schema.sql` 9 张表全部创建，外键约束正确 |
| T1.5 | `BaseProvider` 基类 | 1.5h | T1.3 | 重试逻辑 + 异常日志 |
| T1.6 | `MarketProvider` | 4h | T1.5 | 拉取板块列表、板块日K、个股日K、沪深300日K |
| T1.7 | `FinancialProvider` | 2h | T1.5 | 拉取个股营收增速、净利润增速、ROE、流通市值 |
| T1.8 | `AnnouncementProvider` | 2h | T1.5 | 拉取业绩预告、重大合同公告 |
| T1.9 | 初始化脚本 | 1h | T1.4~T1.8 | `python main.py` 启动后自动建表 + 拉取首轮数据 |
| T1.10 | `NavRepository` + `SectorRepository` | 2h | T1.4 | 两个基础 Repo 实现，其余 Repo 随需补 |

**M1 总预估：20.5h（约 2 周，每天 2-3h）**

### 2.2 M1 测试用例

#### TC-1.1 环境配置加载
```
前置：.env 文件存在且内容为：
  DATABASE_PATH=data/test.db
  LOG_DIR=logs
  LOG_LEVEL=DEBUG
  INITIAL_CAPITAL=100000

步骤：
  1. 启动 python main.py
  2. 检查 config.py 中的 AppConfig 实例

预期：
  - AppConfig.db_path == "data/test.db"
  - AppConfig.log_dir == "logs"
  - AppConfig.log_level == "DEBUG"
  - AppConfig.initial_capital == 100000.0
```

#### TC-1.2 默认值回退
```
前置：.env 文件不存在或被删除

步骤：
  1. 启动 python main.py

预期：
  - 系统不报错，使用 config.py 中的硬编码默认值启动
  - db_path == "data/trend_corp.db"
  - log_level == "INFO"
  - 日志中有一条 WARNING："未找到 .env 文件，使用默认配置"
```

#### TC-1.3 日志三文件输出
```
步骤：
  1. 启动系统 → 手动触发一次日终更新 → 手动制造一次异常（断网拉数据）

预期：
  - logs/app.log 包含：启动日志、Provider 拉取日志、Engine 计算日志
  - logs/scheduler.log 包含：定时任务注册日志、日终更新开始/完成日志
  - logs/error.log 包含：断网异常的完整堆栈
  - 三个文件均使用 UTF-8 编码
```

#### TC-1.4 SQLite 建表完整性
```
步骤：
  1. 删除 data/test.db（如果存在）
  2. 启动系统，触发 init_db()
  3. 用 sqlite3 连接 test.db，执行 .tables

预期：
  - 输出包含 9 张表：sector, sector_snapshot, stock, core_score_snapshot,
    trade, position, risk_event, nav_snapshot
  - 每张表的主键、外键、NOT NULL 约束与 schema.sql 完全一致
```

#### TC-1.5 MarketProvider 拉取板块数据
```
步骤：
  1. 调用 MarketProvider.fetch_all_sectors()

预期：
  - 返回 DataFrame，行数 > 100（申万行业 + 概念板块合计）
  - 每行包含：板块代码、板块名称、板块类型
  - 日志输出："MarketProvider: 拉取板块列表成功，共 N 个"
```

#### TC-1.6 MarketProvider 拉取日K & 均线计算
```
输入：sector_code = 'BK0001'（或任意有效板块代码）
      start = 60 天前， end = 今天

步骤：
  1. 调用 MarketProvider.fetch_sector_daily(code, start, end)

预期：
  - 返回 DataFrame，行数 = 实际交易日数（约 40-45 行）
  - 包含列：date, open, high, low, close, volume, amount, ma5, ma10, ma21, ma55
  - 最后一行（最近交易日）的 ma5/ma10/ma21/ma55 均为有效数值（非 NaN）
  - 验证：计算最后一行的 ma5 = 最近 5 日收盘价均值，误差 < 0.01
```

#### TC-1.7 MarketProvider 拉取失败重试
```
前置：模拟网络异常（或断开网络）

步骤：
  1. 调用 MarketProvider.fetch_sector_daily(...)

预期：
  - 自动重试 3 次
  - 每次重试间隔递增（1s / 2s / 4s）
  - 3 次失败后抛出异常
  - logs/error.log 包含 3 次重试失败的完整记录
```

#### TC-1.8 FinancialProvider 拉取财务数据
```
输入：stock_code = '000001'（平安银行）

步骤：
  1. 调用 FinancialProvider.fetch_financials('000001')

预期：
  - 返回 dict，包含以下键：revenue_yoy, profit_yoy, roe, gross_margin
  - 所有值均为 float 类型
  - 利润增速为正数（平安银行是盈利公司）
  - 日志输出拉取成功
```

#### TC-1.9 AnnouncementProvider 拉取公告
```
步骤：
  1. 调用 AnnouncementProvider.fetch_performance_forecast(days=7)

预期：
  - 返回 list，每个元素为 dict
  - 每个 dict 包含：stock_code, stock_name, forecast_type（预增/预减/预亏/预盈）
  - 如果最近 7 天有业绩预告，列表非空
  - 如果最近 7 天无业绩预告，列表为空但不报错
```

#### TC-1.10 NavRepository 读写
```
步骤：
  1. 调用 NavRepository.save_snapshot(date='2026-07-01', total=100000, cash=100000, positions=0, ...)
  2. 调用 NavRepository.get_latest()

预期：
  - 第一次写入返回 id=1
  - get_latest() 返回 total_value=100000, cash=100000, position_pct=0
```

---

## 三、M2: v0.2 — 核心引擎（Week 3-4）

### 3.1 开发任务

| 编号 | 任务 | 预估 | 依赖 | 产出 |
|------|------|:--:|------|------|
| T2.1 | `engine/scanner/trend.py` | 1.5h | M1 | 趋势强度 0-1 评分，含单元测试 |
| T2.2 | `engine/scanner/rel_strength.py` | 1h | M1 | 相对强度 0-1 评分 |
| T2.3 | `engine/scanner/fund_flow.py` | 1.5h | M1 | 资金确认 0-1 评分 |
| T2.4 | `engine/scanner/echelon.py` | 1h | M1 | 梯队完整性 0-1 评分 |
| T2.5 | `engine/scanner/scanner.py` | 2h | T2.1~T2.4 | 流程编排，组装四个维度 |
| T2.6 | `engine/screener/` 五个维度 | 5h | M1 | market_cap/liquidity/ma_structure/vol_health/fundamental |
| T2.7 | `engine/screener/screener.py` | 2h | T2.6 | 流程编排，输出每板块 ≤2 只中军 |
| T2.8 | `engine/theme_selector.py` | 2h | M1 | B-2 主线确认逻辑 |
| T2.9 | `engine/ma_monitor.py` | 2h | M1 | C-2 均线状态 + A/B 级买卖点信号 |
| T2.10 | 全部 Repository 实现 | 3h | M1 | 7 个 Repository 的完整 CRUD |

**M2 总预估：21h（约 2 周，每天 2-3h）**

### 3.2 M2 测试用例

#### TC-2.1 趋势强度 — 完美多头排列
```
输入：MA5=12.0, MA10=11.0, MA21=10.0, MA55=8.0
      (12 > 11 > 10 > 8，四级全满足)

步骤：调用 trend.calc(ma5, ma10, ma21, ma55)

预期：返回 1.0
```

#### TC-2.2 趋势强度 — 部分满足
```
输入：MA5=11.0, MA10=12.0, MA21=10.0, MA55=8.0
      (仅 MA21>MA55 和 MA5<MA10 中的 MA21>55 满足)

步骤：调用 trend.calc(ma5, ma10, ma21, ma55)

预期：返回 0.25（仅 MA21 > MA55 满足）
```

#### TC-2.3 趋势强度 — 完全空头
```
输入：MA5=7.0, MA10=8.0, MA21=9.0, MA55=10.0
      (全部倒挂)

步骤：调用 trend.calc(ma5, ma10, ma21, ma55)

预期：返回 0.0
```

#### TC-2.4 趋势强度 — 边界条件
```
输入：MA5=10.0, MA10=10.0, MA21=10.0, MA55=10.0
      (全部相等)

步骤：调用 trend.calc(ma5, ma10, ma21, ma55)

预期：返回 0.0（相等不算"大于"）
```

#### TC-2.5 趋势强度 — NaN 处理
```
输入：MA5=NaN, MA10=11.0, MA21=10.0, MA55=9.0

步骤：调用 trend.calc(ma5, ma10, ma21, ma55)

预期：抛出 ValueError 或返回 0.0 并记录 WARNING 日志
```

#### TC-2.6 相对强度 — 板块跑赢大盘
```
输入：sector_ret_20d=0.12 (涨12%), hs300_ret_20d=0.03 (涨3%)
      比值 = 4.0

步骤：调用 rel_strength.calc(0.12, 0.03)

预期：返回 1.0（远 > 1.5 阈值，映射到最大值）
```

#### TC-2.7 相对强度 — 板块跑输大盘
```
输入：sector_ret_20d=-0.05, hs300_ret_20d=0.02
      比值 = -2.5

步骤：调用 rel_strength.calc(-0.05, 0.02)

预期：返回 0.0
```

#### TC-2.8 相对强度 — 大盘下跌时的超额
```
输入：sector_ret_20d=-0.02, hs300_ret_20d=-0.10
      板块跌 2%，大盘跌 10%，板块相对抗跌

步骤：调用 rel_strength.calc(-0.02, -0.10)

预期：返回 > 0.5（超额为正，属于相对强势）
```

#### TC-2.9 资金确认 — 双满足
```
输入：fund_flow_5d=2.5 (近5日净流入2.5亿), volume_ratio=1.3 (成交占比/市值占比)

步骤：调用 fund_flow.calc(net_inflow_5d=2.5, volume_ratio=1.3)

预期：返回 1.0（两项都满足：净流入>0 且 占比比>1.0）
```

#### TC-2.10 资金确认 — 仅一项满足
```
输入：fund_flow_5d=-0.5, volume_ratio=1.3

步骤：调用 fund_flow.calc(net_inflow_5d=-0.5, volume_ratio=1.3)

预期：返回 0.5（仅成交占比满足）
```

#### TC-2.11 梯队完整性 — 双满足
```
输入：limit_up_cnt=5（近5日5只涨停）, has_large_cap=True（存在>100亿标的）

步骤：调用 echelon.calc(limit_up_cnt=5, has_large_cap=True)

预期：返回 1.0
```

#### TC-2.12 梯队完整性 — 无涨停
```
输入：limit_up_cnt=0, has_large_cap=True

步骤：调用 echelon.calc(limit_up_cnt=0, has_large_cap=True)

预期：返回 0.5（仅大市值存在满足）
```

#### TC-2.13 MarketScanner 端到端扫描
```
前置：MarketProvider 能正常拉取数据
      测试日期为最近一个交易日

步骤：
  1. scanner = MarketScanner(market_provider, weights, threshold=0.6)
  2. results = scanner.scan_all(date)

预期：
  - results 是 list，长度 >= 0
  - 每个 ScanResult 包含：sector_code, sector_name,
    trend_score, rel_strength, fund_score, echelon_score, total_score
  - 所有 score 值在 0.0 ~ 1.0 之间
  - total_score = trend*0.35 + rel_strength*0.25 + fund*0.25 + echelon*0.15
  - 所有结果的 total_score >= 0.6
  - 结果按 total_score 降序排列
  - 日志输出扫描的板块总数和候选数
```

#### TC-2.14 市值规模维度评分
```
输入：流通市值 250 亿（在 100-500 区间内）

步骤：调用 market_cap.calc(250)

预期：返回 1.0
```

```
输入：流通市值 80 亿（<100）

步骤：调用 market_cap.calc(80)

预期：返回 0.6
```

```
输入：流通市值 30 亿（<50）

步骤：调用 market_cap.calc(30)

预期：返回 0.2
```

#### TC-2.15 均线结构维度评分
```
输入：MA5=50, MA10=45, MA21=40, MA55=35（全部多头排列）

步骤：调用 ma_structure.calc(ma5, ma10, ma21, ma55)

预期：返回 1.0
```

#### TC-2.16 量价健康度 — 健康
```
输入：up_day_avg_vol=1200万, down_day_avg_vol=600万（上涨放量）
      最近回调量 = 400万, 前期高峰量 = 1200万（缩量至33%）

步骤：调用 vol_health.calc(up_avg, down_avg, pullback_vol, peak_vol)

预期：返回 1.0（两项都满足：涨量/跌量 > 1.5，且回调缩量 < 50%）
```

#### TC-2.17 CoreScreener 端到端筛选
```
前置：MarketProvider + FinancialProvider 正常
      已有一个确认主线板块，板块内有 20 只成分股
      测试日期为最近交易日

步骤：
  1. screener = CoreScreener(market, financial, weights, threshold=0.65, top_n=2)
  2. results = screener.screen(sector_code='BK0001', date=today)

预期：
  - results 长度 <= 2
  - 每个 CoreScoreResult 含五维评分 + total_score
  - 所有 total_score >= 0.65
  - 结果按 total_score 降序
  - 如果板块内有 >2 只合格标的，只取前 2
```

#### TC-2.18 ThemeSelector 主线确认
```
输入：候选列表中有 3 个板块：
  - 板块 A: scan_score=0.85, 连续跑赢3周, 有产业逻辑, 非天量, PE分位60%
  - 板块 B: scan_score=0.75, 连续跑赢2周, 纯题材, 非天量, PE分位75%
  - 板块 C: scan_score=0.70, 连续跑赢1周, 有产业逻辑, 已天量, PE分位95%

步骤：调用 ThemeSelector.confirm(candidates)

预期：
  - 板块 A: 4 分 → 确认主线（≥3 分）
  - 板块 B: 2 分 → 观察主线（2-2.99 分）
  - 板块 C: 1 分 → 排除（<2 分）
```

#### TC-2.19 MAMonitor 买卖点信号
```
前置：一只中军标的：
  - MA10 = 50.0, 当前价 = 50.8（距 MA10 偏差 1.6%）
  - 当日成交量 = 20 日均量的 45%
  - K 线收小阳线

步骤：调用 MAMonitor.check(stock_code, price, ma10, vol_ratio, candle_type)

预期：返回 SignalType.A_BUY（距 MA10 < 3% + 缩量 + 小阳线）
```

```
前置：价格距 MA10 偏差 6%，板块共振启动

预期：返回 SignalType.B_BUY
```

```
前置：价格距 MA10 偏差 12%

预期：返回 None（太远，不买）
```

```
前置：收盘价 48.0，MA10=50.0（跌破 MA10）

预期：返回 SignalType.REDUCE
```

```

---

## 四、M3: v0.3 — 流程编排（Week 5-6）

### 4.1 开发任务

| 编号 | 任务 | 预估 | 依赖 | 产出 |
|------|------|:--:|------|------|
| T3.1 | `workflow/base.py` | 1.5h | M2 | BaseWorkflow 基类（日志/耗时/异常） |
| T3.2 | `workflow/weekly_workflow.py` | 3h | T3.1 | 5 步流程编排 + 每步日志 |
| T3.3 | `workflow/daily_workflow.py` | 3h | T3.1 | 日终 5 步流程 |
| T3.4 | `workflow/monthly_workflow.py` | 2h | T3.1 | 月报生成流程 |
| T3.5 | `engine/theme_monitor.py` | 2h | M2 | B-3 退潮预警四信号 |
| T3.6 | `scheduler/jobs.py` | 1.5h | T3.2~T3.4 | 定时任务注册（只调 Workflow） |
| T3.7 | 手动触发 API | 1.5h | M2 | `POST /api/workflow/scan` + `/eod` |
| T3.8 | `TradeLogger` + `TradeRepository` | 2h | M2 | F-1 交易录入 + 存储 |

**M3 总预估：16.5h（约 2 周）**

### 4.2 M3 测试用例

#### TC-3.1 Workflow 基类 — 正常执行
```
步骤：
  1. 继承 BaseWorkflow 实现一个 MockWorkflow
  2. MockWorkflow.execute() 中执行简单操作
  3. 调用 MockWorkflow.run()

预期：
  - logs/app.log 包含：开始 / 完成 / 耗时
  - 不包含异常记录
  - 返回正常
```

#### TC-3.2 Workflow 基类 — 异常执行
```
步骤：
  1. MockWorkflow.execute() 中 raise ValueError("test error")
  2. 调用 MockWorkflow.run()

预期：
  - logs/app.log 包含：开始
  - logs/error.log 包含：完整堆栈 + "test error"
  - logs/app.log 包含：完成（即使异常也记录 finally）
  - ValueError 被重新抛出（re-raise）
```

#### TC-3.3 WeeklyWorkflow 端到端
```
前置：MarketProvider 正常，Scanner/Screener/ThemeSelector 可用

步骤：
  1. workflow = WeeklyWorkflow(market, scanner, selector, screener, ...)
  2. workflow.run()

预期：
  - 日志输出 5 个 Step 顺序执行
  - Step 1: "更新全市场板块数据" — 拉取成功日志
  - Step 2: "扫描板块" — 输出候选数量
  - Step 3: "确认主线" — 输出确认/观察/排除数量
  - Step 4: "筛选中军" — 输出中军候选数量
  - Step 5: "保存快照" — 数据写入 SQLite
  - 完成后日志："完成。确认主线 N 个，中军候选 M 只"
  - sector_snapshot 和 core_score_snapshot 表有新数据
```

#### TC-3.4 DailyWorkflow 端到端
```
前置：有 2 只持仓标的 + 3 只候选池标的

步骤：
  1. workflow = DailyWorkflow(...)
  2. workflow.run()

预期：
  - 更新了 5 只标的的当日行情
  - MAMonitor 输出了每只标的的均线状态和信号
  - ThemeMonitor 检查了持有标的所属板块的退潮状态
  - RiskController 检查了风控状态
  - nav_snapshot 有新记录
```

#### TC-3.5 Scheduler 与 Workflow 解耦
```
步骤：
  1. 检查 scheduler/jobs.py 源码

预期：
  - register_jobs 函数只接收 Workflow 对象，不直接引用任何 Engine 模块
  - 函数体内只有 scheduler.add_job(xxx_workflow.run, trigger=...)
  - 不包含任何业务逻辑、计算逻辑、数据访问逻辑
```

#### TC-3.6 退潮预警 — 触发减仓
```
前置：持有标的所属板块 X：
  - 连续 2 天跑输沪深 300
  - 近 5 日涨停家数 = 1
  - 成交额正常
  - 中军无放量长阴

步骤：调用 ThemeMonitor.check(sector_code, date)

预期：
  - alert_level = 1（减仓，因为跑输+涨停稀少 ≥ 2 项触发）
  - alert_triggers 包含："连续跑输"、"涨停家数不足"
```

#### TC-3.7 退潮预警 — 触发退出
```
前置：板块 X：
  - 连续 3 天跑输
  - 涨停家数 = 0
  - 成交额较 20 日均量萎缩 50%
  - 中军放量长阴

步骤：调用 ThemeMonitor.check(sector_code, date)

预期：
  - alert_level = 2（退出，4 项全部触发 ≥ 3 项）
```

#### TC-3.8 手动触发 API
```
步骤：
  1. POST /api/workflow/scan

预期：
  - HTTP 200
  - response: {"success": true, "data": {"confirmed_themes": N, "core_candidates": M}}
  - logs/app.log 包含完整的 WeeklyWorkflow 执行日志
  - 与 Scheduler 自动触发执行相同的流程
```

#### TC-3.9 TradeLogger 录入一笔交易
```
步骤：
  1. POST /api/trade/log
      body: {
        "stock_code": "000001",
        "direction": "LONG",
        "open_date": "2026-07-01",
        "open_price": 12.50,
        "open_reason": "A_MA10_BOUNCE",
        "open_ma10": 12.30,
        "position_pct": 20.0
      }

预期：
  - HTTP 200, success=true
  - trade 表新增一条记录，trade_no 格式为 T-20260701-001
  - rule_compliant=1（默认合规）
  - 日志记录录入成功
```

---

## 五、M4: v0.4 — 风控仓位（Week 7-8）

### 5.1 开发任务

| 编号 | 任务 | 预估 | 依赖 | 产出 |
|------|------|:--:|------|------|
| T4.1 | `engine/position_manager.py` | 3h | M2 | 仓位计算逻辑，A/B 级不同建仓比例 |
| T4.2 | `engine/order_executor.py` | 2h | T4.1 | 生成交易指令（限价/市价） |
| T4.3 | `engine/risk_controller.py` | 3h | M2 | 三级熔断完整逻辑 |
| T4.4 | `engine/dashboard.py` | 2h | T4.1~T4.3 | 仪表盘数据聚合（净值/仓位/信号/熔断） |
| T4.5 | `PositionRepository` + `RiskRepository` | 1.5h | M2 | 持仓和风控事件持久化 |
| T4.6 | 价格轮询止损 | 2h | T4.3 | APScheduler 每 5 分钟轮询 + 熔断触发 |
| T4.7 | `journal/monthly_report.py` | 2.5h | M2 | F-2 月度统计 + 归因 |

**M4 总预估：16h（约 2 周）**

### 5.2 M4 测试用例

#### TC-4.1 建仓指令 — A 级买点
```
前置：总净值 100,000，当前无持仓
      信号 = SignalType.A_BUY，股票 = '000001', MA10 = 50.0

步骤：调用 PositionManager.calc_order(signal='A_BUY', code='000001', current_pct=0, ma10=50)

预期：
  - 返回 TradeOrder(direction='BUY', target_pct=15.0, price_type='LIMIT', limit_price=50.25)
  - A 级首次建仓 = 目标仓位 30% × 50% = 15%（A级首次建仓比例 50%）
  - 限价 = MA10 × 1.005 = 50.25
```

#### TC-4.2 建仓指令 — B 级买点
```
前置：同上，信号 = SignalType.B_BUY

预期：
  - target_pct = 30% × 30% = 9.0%（B级首次建仓比例 30%）
  - price_type = 'LIMIT'，limit_price = 当前价（不设偏离）
```

#### TC-4.3 仓位上限 — 触及总仓位上限
```
前置：总净值 100,000，当前总仓位 = 65%
      买入后目标仓位 = 65% + 15% = 80% > 70%

步骤：调用 PositionManager.calc_order(...)

预期：
  - target_pct 被裁剪到 70% - 65% = 5%
  - 日志 WARNING："总仓位将触及上限 70%，建仓比例从 15% 调整为 5%"
```

#### TC-4.4 仓位上限 — 触及单票上限
```
前置：当前 '000001' 持仓 25%，信号要求加仓至 35%（> 30% 上限）

预期：
  - target_pct 被裁剪到 30% - 25% = 5%
  - 日志 WARNING
```

#### TC-4.5 减仓指令 — MA10 破位
```
前置：当前持有 '000001' 仓位 25%，触发 REDUCE 信号

预期：
  - 返回 TradeOrder(direction='SELL', target_pct=12.5)
  - 减仓 = 当前 25% × 50% = 12.5%，即卖出 12.5%
```

#### TC-4.6 清仓指令 — MA21 破位
```
前置：当前仓位 25%，触发 EXIT 信号

预期：
  - 返回 TradeOrder(direction='SELL', target_pct=25.0, price_type='MARKET')
  - 清仓全部 25%
  - 价格类型 = MARKET（保命优先，不设限价）
```

#### TC-4.7 清仓指令 — 板块退潮
```
前置：持仓所属板块退潮预警 level=2（退出），当前仓位 20%

预期：
  - 返回 TradeOrder(direction='SELL', target_pct=20.0)
  - 价格类型 = LIMIT（不是紧急止损，可以挂限价单）
```

#### TC-4.8 L1 熔断 — 个股 -8% 止损
```
前置：持仓 '000001'，成本价 50.0，当前价 46.0（浮亏 -8%）

步骤：调用 RiskController.check_stock(pnl_pct=-0.08, ...)

预期：
  - 返回 FuseLevel.STOCK_STOP
  - logs/error.log 记录：L1 熔断触发 - 000001 亏损 8.00%
  - risk_event 表有新记录
```

#### TC-4.9 L1 熔断 — 未触发
```
前置：浮亏 -5%

步骤：调用 RiskController.check_stock(pnl_pct=-0.05, ...)

预期：返回 FuseLevel.NORMAL
```

#### TC-4.10 L2 熔断 — 日内回撤 3%
```
前置：当日净值从 100,000 降至 96,800（日内 -3.2%）

步骤：调用 RiskController.check_daily(daily_pnl_pct=-0.032, consecutive_stops=0)

预期：返回 FuseLevel.DAILY_BAN
```

#### TC-4.11 L2 熔断 — 连续止损
```
前置：当日无大回撤（-0.5%），但连续 2 笔交易都触发了止损

步骤：调用 RiskController.check_daily(daily_pnl_pct=-0.005, consecutive_stops=2)

预期：返回 FuseLevel.DAILY_BAN
```

#### TC-4.12 L3 熔断 — 月回撤 10%
```
前置：本月净值从月初 105,000 降至 93,000（-11.4%）

步骤：调用 RiskController.check_monthly(monthly_pnl_pct=-0.114)

预期：返回 FuseLevel.MONTHLY_BAN
```

#### TC-4.13 Dashboard 数据聚合
```
前置：持仓 2 只，总仓位 52%，熔断状态 NORMAL

步骤：调用 Dashboard.get_summary()

预期返回：
{
  "total_nav": 112350.0,
  "daily_return": 0.0123,
  "weekly_return": 0.0215,
  "monthly_return": 0.0487,
  "max_drawdown": -0.068,
  "fuse_level": "NORMAL",
  "position_pct": 52.0,
  "cash": 53200.0,
  "holdings": [
    {"code": "000001", "name": "平安银行", "signal": "HOLD", "pnl_pct": 5.2, "ma10_status": "ABOVE", "sector_alert": 0},
    {"code": "600519", "name": "贵州茅台", "signal": "A_BUY",  "pnl_pct": 1.8, "ma10_status": "NEAR",  "sector_alert": 0}
  ]
}
```

#### TC-4.14 MonthlyReport 归因统计
```
前置：本月共完成 8 笔交易（6 赢 2 亏），无违规操作

步骤：调用 MonthlyReport.generate(year=2026, month=7)

预期返回：
  - trade_count = 8
  - win_rate = 75.0%
  - avg_win_loss_ratio = 盈亏比，> 1.0
  - max_single_win_pct / max_single_loss_pct
  - violation_count = 0
  - by_sector: 按板块归因的收益贡献
  - by_signal: 按 A/B 买点归因的收益对比
  - 总结一句话自动生成
```

---

## 六、M5: v1.0 — Web 交付（Week 9-10）

### 6.1 开发任务

| 编号 | 任务 | 预估 | 依赖 | 产出 |
|------|------|:--:|------|------|
| T5.1 | `web/schemas.py` | 0.5h | — | `APIResponse` 统一模型 |
| T5.2 | `web/router.py` — 页面路由 | 2h | M4 | 6 个页面路由 + 10 个数据 API |
| T5.3 | `web/templates/base.html` | 1.5h | T5.2 | 基础模板（导航、熔断状态指示器） |
| T5.4 | `web/templates/dashboard.html` | 3h | T5.3 | 主仪表盘（净值卡片 + 持仓表 + Chart.js 曲线） |
| T5.5 | `web/templates/scanner.html` | 2.5h | T5.3 | 主线扫描 + 中军候选池 |
| T5.6 | `web/templates/positions.html` | 1.5h | T5.3 | 持仓详情 + 信号 + 风控 |
| T5.7 | `web/templates/journal.html` | 2h | T5.3 | 交易日志列表 + 录入表单 |
| T5.8 | `web/templates/report.html` | 1.5h | T5.3 | 月度报告页 |
| T5.9 | `web/static/` 样式 + 交互 | 2h | T5.3~T5.8 | Chart.js 净值曲线 + HTMX 局部刷新 |
| T5.10 | 端到端联调 + Bug 修复 | 4h | 全部 | 全流程正常 + 异常路径覆盖 |

**M5 总预估：20.5h（约 2 周）**

### 6.2 M5 测试用例

#### TC-5.1 APIResponse 正常返回
```
步骤：GET /api/dashboard

预期：
{
  "success": true,
  "data": { ... },
  "message": "ok",
  "timestamp": "2026-07-15T09:30:00"
}
```

#### TC-5.2 APIResponse 异常返回
```
步骤：模拟 Dashboard 数据聚合异常，GET /api/dashboard

预期：
{
  "success": false,
  "data": null,
  "message": "Dashboard 数据聚合失败: ...",
  "timestamp": "..."
}
HTTP 状态码仍为 200（异常信息在 body 中表达，前端统一处理）
```

#### TC-5.3 Dashboard 页面加载
```
步骤：浏览器访问 http://localhost:8000/

预期：
  - 页面标题："趋势中军交易系统"
  - 显示四个净值卡片（总净值/今日/本周/本月）
  - 显示熔断状态指示器（绿色圆点 + "正常"）
  - 显示仓位百分比 + 可用现金
  - 净值曲线图（Chart.js 折线图，包含近 3 个月数据）
  - 持仓表：每行一只标的，含信号/浮盈/MA10状态/板块预警
  - 如果熔断状态为 DAILY_BAN，导航栏显示红色警告横幅
```

#### TC-5.4 Scanner 页面 — 显示主线
```
步骤：访问 /scanner

预期：
  - 显示最新一期扫描的更新时间
  - "确认主线"区域：显示 1-3 个板块卡片，含总分、四个维度分、中军候选、退潮状态
  - "观察主线"区域：显示候选板块
  - "退潮预警"区域：仅在有退潮板块时显示
  - 点击"手动扫描"按钮可触发一次周度扫描（HTMX 局部更新，不刷新整页）
```

#### TC-5.5 Scanner 页面 — 手动触发扫描
```
步骤：在 /scanner 页面点击"手动扫描"按钮

预期：
  - 按钮变为加载状态（灰色 + 旋转图标）
  - 扫描完成后，页面局部刷新
  - 显示新的扫描结果
  - 页面顶部出现短暂提示："扫描完成，确认主线 2 个"
  - 如果扫描失败，显示红色错误提示
```

#### TC-5.6 Positions 页面
```
步骤：访问 /positions

预期：
  - 每只持仓标的显示：
    - 代码 + 名称
    - 持仓占比 + 成本价 + 现价
    - 浮动盈亏（金额 + 百分比，绿色正/红色负）
    - 当前信号（HOLD/A_BUY/REDUCE/EXIT）
    - MA10 状态（ABOVE/BELOW/NEAR，颜色指示）
    - 所属板块退潮预警等级
  - 底部显示总仓位 + 可用现金
  - 如果风控处于 DAILY_BAN / WEEKLY_BAN / MONTHLY_BAN，开仓按钮被禁用并显示原因
```

#### TC-5.7 Journal 页面 — 交易列表
```
步骤：访问 /journal

预期：
  - 表格列：交易编号 / 标的 / 开仓日 / 平仓日 / 盈亏金额 / 盈亏% / 合规
  - 合规列：✅（合规）/ ⚠️（有偏差）
  - 可按月筛选
  - 点击交易编号可跳转到详情
```

#### TC-5.8 Journal 页面 — 录入新交易
```
步骤：在 /journal 页面点击"录入交易"

预期：
  - 弹出表单，字段：
    - 标的代码（必填）
    - 开仓日期（必填，日期选择器）
    - 开仓价格（必填，数字）
    - 开仓理由（下拉：A_MA10_BOUNCE / B_SECTOR_BREAK / OTHER）
    - 开仓时 MA10（必填）
    - 仓位占比%（必填，1-100）
  - 提交成功后：列表页自动刷新，新交易出现在顶部
  - 提交失败：表单内显示错误信息
```

#### TC-5.9 Journal 页面 — 平仓录入
```
步骤：对一笔未平仓的交易，点击"平仓"

预期：
  - 弹出表单：
    - 平仓日期
    - 平仓价格
    - 平仓原因（下拉：TAKE_PROFIT / MA10_BREAK / MA21_BREAK / STOP_LOSS / SECTOR_EXIT）
    - 复盘备注（文本框）
    - "是否合规"复选框，默认勾选
  - 提交后：自动计算盈亏，交易状态变为"已平仓"
```

#### TC-5.10 Report 页面
```
步骤：访问 /report?month=2026-07

预期：
  - 月度概览卡片：交易笔数 / 胜率 / 月收益率 / 最大回撤
  - 按板块的收益贡献柱状图（Chart.js）
  - 按买点类型（A/B）的对比表
  - 违规操作次数（如果 > 0，红色高亮）
  - 一句话自动总结（"本月在半导体板块贡献了 60% 收益，A 级买点胜率 75%，无违规操作"）
```

#### TC-5.11 全流程端到端
```
步骤：
  1. 启动系统 → 自动拉取全市场数据
  2. 手动触发周度扫描 → Scanner 页面显示 2 条确认主线
  3. 查看 Scanner 页面的中军候选 → 选择 000001
  4. 在 Positions 页面看到该标的有 A_BUY 信号
  5. 人工在券商 App 买入 → 在 Journal 页面录入
  6. 3 天后 → 日终更新检测到 MA10 破位 → Dashboard 显示 REDUCE 信号
  7. 人工卖出 → Journal 页面平仓录入 → 查看 Report 页面统计

预期：
  - 全程无系统报错
  - 每步都有对应日志
  - 数据在 SQLite 中完整可查
```

#### TC-5.12 异常路径 — 数据源不可用
```
前置：模拟 akshare 接口全部超时

步骤：
  1. 触发周度扫描

预期：
  - Workflow 捕获异常，记录到 error.log
  - Dashboard 不崩溃，上一次的扫描结果仍然可见
  - 前端显示："数据更新失败，使用 2026-07-01 的快照数据"
  - Web 服务不挂
```

#### TC-5.13 异常路径 — SQLite 写入失败
```
前置：模拟磁盘满

步骤：
  1. 触发日终更新

预期：
  - 日志记录 ERROR
  - Dashboard 提示："数据持久化失败，请检查磁盘空间"
  - 内存中的计算结果不丢失（暂存到日志中）
```

---

## 七、测试环境与数据

### 7.1 测试数据策略

| 层级 | 数据来源 | 用途 |
|------|---------|------|
| **单元测试** | 手工构造的 DataFrame/dict | 验证每个评分维度、边界条件 |
| **集成测试** | 固定日期的 akshare 快照（如 2026-06-30） | 验证 Engine 端到端输出一致性 |
| **端到端测试** | 实时 akshare + 模拟持仓 | 验证 Workflow 和 Web 全流程 |

### 7.2 测试执行命令

```bash
# 单元测试（每个引擎维度独立跑）
python -m pytest tests/test_scanner/ -v
python -m pytest tests/test_screener/ -v
python -m pytest tests/test_risk.py -v

# 集成测试（需要网络 + akshare）
python -m pytest tests/ -m integration -v

# 全量测试
python -m pytest tests/ -v --cov=. --cov-report=html
```

---

## 八、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|:--:|------|------|
| akshare API 接口变更 | 中 | 高 | Provider 层隔离了数据源，只改 Provider 不改 Engine |
| 板块数据历史不足（新股、新板块） | 中 | 低 | Scanner 中对数据不足的板块返回较低的 trend_score |
| MA55 计算因新股无足够数据返回 NaN | 高 | 中 | Provider 层做 NaN 填充，Engine 层做 NaN 守卫 |
| 节假日/停牌导致数据缺失 | 高 | 低 | Provider 层用前一日数据前向填充 |
| 10 周内无法完成全部开发 | 中 | 中 | M1-M3 即可开始手动使用（终端输出足够），M4-M5 是 Web 增强 |
| 策略参数需要实际交易后才能调优 | 高 | 中 | F-3 参数优化器是季度级别的，V1.0 先用默认参数跑 3 个月 |

---

## 九、交付物清单

| 里程碑 | 交付物 |
|--------|--------|
| **M1** | 可运行的项目骨架、`.env` 配置、日志输出、9 张表建好、行情/财务/公告数据可拉取 |
| **M2** | Scanner/Screener 终端输出正确结果、ThemeSelector 正确分级、MAMonitor 正确信号 |
| **M3** | Weekly/Daily/Monthly Workflow 完整跑通、退潮预警可用、交易记录可写 |
| **M4** | PositionManager 输出正确指令、RiskController 三级熔断全触发、Dashboard 数据正确 |
| **M5** | 6 个 Web 页面可用、Chart.js 图表展示、手工操作 10 分钟/天流程闭合 |
