# M3 代码评审报告

> 评审日期：2026-07-20
> 评审范围：commit `64927c4` "M3: 流程编排交付 — Workflow/Scheduler/TradeLogger/API 入口"
> 评审依据：PROJECT_PLAN.md 第五章 M3 测试用例 TC-3.1 ~ TC-3.12
> 方法：逐行代码审查 + 逐 TC 追踪 + 数据库 schema 验证

---

## 评审摘要

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **P0** | 3 | 阻断性缺陷 — DailyWorkflow 核心逻辑错误，运行时必崩溃或静默失效 |
| **P1** | 5 | 高优缺陷 — 数据完整性、日志 TC 对齐、代码重复 |
| **P2** | 4 | 中优建议 — API 缺失、查找效率、可测试性 |

**总体评价**：M3 的架构设计方向正确 — Workflow 继承 BaseWorkflow、Scheduler 仅调用 Workflow、TradeLogger 分离录入逻辑。但 DailyWorkflow 中存在 **3 个 P0 缺陷**，使其在当前状态下无法正确运行。WeeklyWorkflow 和 Scheduler 实现正确。建议 P0+P1 修复后判定 M3 门禁。

---

## P0 — 阻断性缺陷

### P0-1: `DailyWorkflow` Step 1 将 DB 内部 ID 当作股票代码传入

**文件**: [workflow/daily_workflow.py:44-46](workflow/daily_workflow.py)

```python
for pos in positions:
    result = self.ma_monitor.check(
        stock_code=str(pos.get("stock_id", "")),  # ← BUG
        snap_date=today,
    )
```

**问题**: `pos` 来自 `position_repo.get_all()`，返回 `position` 表的数据。`position.stock_id` 是外键，指向 `stock.id`（DB 内部整数主键，如 1, 2, 3...）。代码将其 `str()` 化后当作股票代码（如 "000001"）传入 `ma_monitor.check()`。

**后果**: `ma_monitor.check()` → `fetch_stock_daily("5", ...)` 会用 "5" 去 akshare 查询，返回错误数据或抛出异常。MAMonitor 的均线信号计算全部基于错误数据。

**数据库验证**:
```
position.stock_id: INTEGER (没有 UNIQUE 约束) — 外键指向 stock.id
stock.code:        TEXT UNIQUE — 实际的股票代码如 "000001"
```

**建议修复**:
```python
# 需要先通过 stock 表将 stock_id 解析为 stock_code
stock = self.stock_repo.get_by_id(pos["stock_id"])
stock_code = stock["code"] if stock else None
if stock_code:
    result = self.ma_monitor.check(stock_code=stock_code, snap_date=today)
```

**注意**: `StockRepository` 当前没有 `get_by_id()` 方法，需同步添加（见 P2-1）。

**TC 影响**: TC-3.4 完全失败（均线信号基于错误数据）

---

### P0-2: `DailyWorkflow` Step 3（退潮预警）永远不执行

**文件**: [workflow/daily_workflow.py:68-69](workflow/daily_workflow.py)

```python
sector_ids = {h.get("sector_id") for h in holdings if h.get("sector_id")}
for sid in sector_ids:  # ← sector_ids 永远为空集合
```

**问题**: `holdings` 由 `position_repo.get_all()` 的返回值构成，而 `position` 表（经 `PRAGMA table_info` 确认）**没有 `sector_id` 列**。因此 `h.get("sector_id")` 对所有持仓返回 `None`，`sector_ids` 始终为空集合，for 循环体从不执行。

**后果**: DailyWorkflow 的 Step 3 "板块退潮预警" 完全静默失效。不会检测任何板块退潮信号，不会触发减仓/退出建议。

**建议修复**: 通过 `stock` 表 JOIN 获取板块信息：
```python
sector_ids = set()
for h in holdings:
    sid = h.get("stock_id")  # 从 position 取 stock_id
    if sid:
        stock = self.stock_repo.get_by_id(sid)
        if stock and stock.get("sector_id"):
            sector_ids.add(stock["sector_id"])
```

**TC 影响**: TC-3.4 Step 3 完全失效；TC-3.6/3.7 退潮预警无法通过 DailyWorkflow 触发

---

### P0-3: `PositionRepository.upsert` ON CONFLICT 目标列无 UNIQUE 约束

**文件**: [repositories/position_repository.py:29-32](repositories/position_repository.py)

```sql
INSERT INTO position (...) VALUES (...)
ON CONFLICT(stock_id) DO UPDATE SET ...
```

**问题**: 经实际数据库验证，`position.stock_id` 列上 **没有任何索引或 UNIQUE 约束**。SQLite 的 `ON CONFLICT(stock_id)` 要求 `stock_id` 有 UNIQUE 约束才能触发 UPDATE 分支。当前状态下，每次 `upsert` 都执行 INSERT（添加新行），从不 UPDATE。

**后果**:
- 同一个 stock_id 可能在 position 表中有多行记录
- `get_all()` 返回重复数据
- DailyWorkflow 的持仓处理会产生重复信号
- `delete(stock_id)` 会删除所有匹配行（包括错误累积的重复行）

**验证命令输出**:
```
Position indexes: []  ← stock_id 上无任何索引
```

**建议修复**: 在 `schema.sql` 中为 `stock_id` 添加 UNIQUE 约束：
```sql
ALTER TABLE position ADD UNIQUE(stock_id);
```
或在 CREATE TABLE 时直接定义 `stock_id INTEGER UNIQUE REFERENCES stock(id)`。

**TC 影响**: TC-3.4（DailyWorkflow 端到端）数据完整性不通过

---

## P1 — 高优缺陷

### P1-1: TC-3.1 / TC-3.2 预期日志文件与实际行为不匹配

**文件**: [workflow/base.py:14-16](workflow/base.py)

```python
self.logger = logging.getLogger(f"scheduler.{self.__class__.__name__}")
```

**问题**: BaseWorkflow 使用 `scheduler.*` 命名空间的 logger。由于 M1 P1-2 修复的日志分流规则（scheduler.* → scheduler.log），所有 Workflow 日志（开始/完成/耗时/异常）都写入 `scheduler.log` 而非 `app.log`。

**TC-3.1 要求**: "logs/app.log 包含：开始 / 完成 / 耗时"
**TC-3.2 要求**: "logs/app.log 包含：开始" + "logs/app.log 包含：完成"

实际行为（符合分流规则，但与 TC 文档矛盾）:
- 开始/完成/耗时 → **scheduler.log**（因为 logger name 以 "scheduler." 开头）
- 异常 → **scheduler.log + error.log**（ERROR 级别聚合）

**评估**: 当前实现的行为是**合理的**（Workflow 日志确实应该放在 scheduler.log），但 TC-3.1/3.2 的判定文案需要更新。建议统一 PROJECT_PLAN.md 中 TC-3.1/3.2 的预期文件为 `scheduler.log`。

---

### P1-2: `TradeLogger._gen_trade_no()` 使用随机数作为序号

**文件**: [journal/trade_logger.py:88-92](journal/trade_logger.py)

```python
@staticmethod
def _gen_trade_no() -> str:
    today = date.today().strftime("%Y%m%d")
    import random
    seq = random.randint(100, 999)
    return f"T-{today}-{seq}"
```

**问题**: 使用 `random.randint(100, 999)` 生成交易序号。在同一日期内理论上有 `1 - (899P_n / 899^n)` 的碰撞概率（生日悖论），录入 30 笔以上交易时碰撞概率 > 30%。

**建议修复**: 使用 DB 序列或 `trade_repo.get_all` 计数：
```python
# 方案 A: 从 DB 查询当日最大序号 + 1
# 方案 B: 使用毫秒时间戳后 3 位
```

**TC 影响**: TC-3.9 可能因 trade_no 冲突失败

---

### P1-3: `WeeklyWorkflow.execute()` 的 Step 1 与 `_init_sectors()` 逻辑重复

**文件**: [workflow/weekly_workflow.py:39-51](workflow/weekly_workflow.py) 与 [main.py:36-51](main.py)

两处代码完全相同：拉取 `fetch_all_sectors()` → 遍历 rows → `upsert_sector()`。任何一种逻辑修改需要同步两处。

**建议修复**: 提取公共函数，或让 WeeklyWorkflow 直接调用 `_init_sectors`（需解决模块依赖）。

---

### P1-4: `DailyWorkflow` 净值计算未考虑现金变动

**文件**: [workflow/daily_workflow.py:96-98](workflow/daily_workflow.py)

```python
cash = max(0, prev_total - positions_value)
total_value = cash + positions_value
```

**问题**: 公式 `cash = prev_total - positions_value` 等于 `total_value = prev_total`，即**总净值不变**。这假设了持仓市值的变化正好被现金吸收，但在真实场景中：
- 买入时：现金减少，持仓增加，总净值不变（正确）
- 持仓涨跌时：持仓市值变化，现金不变，总净值应变化（**当前公式忽略了涨跌**）

当前公式下 `daily_ret` 永远为 0（除非计算精度误差），使得净值追踪失效。

**正确公式**:
```python
# 从 nav_snapshot 读取上次的 cash，计算本次
prev_cash = latest_nav["cash"] if latest_nav else self.initial_capital
total_value = prev_cash + positions_value  # 现金不变，持仓浮动
```

**注意**: 完整实现需要跟踪买入/卖出导致的现金流变化，M3 阶段可先简化处理。

---

### P1-5: `ThemeMonitor` 第 4 项触发条件（中军放量长阴）仍未实现

**文件**: [engine/theme_monitor.py:31-32](engine/theme_monitor.py)

```python
# 4. 中军放量长阴
# (M2 阶段不依赖中军持仓列表，M3 Workflow 中补充)
```

**问题**: 注释承诺的"M3 Workflow 中补充"并未在 M3 实现。DailyWorkflow 本应该向 check() 传入中军标的列表以检查第 4 项触发，但未做。

**TC 影响**: TC-3.6/3.7 的退潮预警仅能检测 3/4 项条件，存在漏判风险

---

## P2 — 中优建议

### P2-1: `StockRepository` 缺少 `get_by_id()` 方法

**依赖链**: P0-1 的修复需要在 `StockRepository` 上调用 `get_by_id()`，但当前仅有 `get_by_code()` 和 `get_by_sector()`。

**建议**: 添加：
```python
def get_by_id(self, stock_id: int) -> dict | None:
    with self._conn() as c:
        row = c.execute("SELECT * FROM stock WHERE id = ?", (stock_id,)).fetchone()
        return dict(row) if row else None
```

---

### P2-2: `TradeLogger.log_close()` 全表扫描查找交易记录

**文件**: [journal/trade_logger.py:57-63](journal/trade_logger.py)

```python
trades = self.trade_repo.get_all(limit=100)  # 加载最多 100 条
trade = None
for t in trades:
    if t["id"] == trade_id:
        trade = t
        break
```

**问题**: 加载最多 100 条交易到内存，再线性查找一条。应该使用 `trade_repo.get_by_id(trade_id)`。

**建议**: 在 `TradeRepository` 中添加 `get_by_id()` 方法直接按主键查询。

---

### P2-3: M3 缺少 Web API 入口（T3.7 用例）

**计划要求** (T3.7): "手动触发 API — `POST /api/workflow/scan` + `/eod`"
**实际实现**: CLI 入口（`--weekly`、`--daily`、`--monthly`）

CLI 方式在 M3 阶段可接受（M5 才有 FastAPI 交付），但应标注 `FIXME(M5): 替换为 FastAPI POST 端点`。

---

### P2-4: `main.py` 中 `_setup_m3_context()` 代码冗余

**文件**: [main.py:155-209](main.py)

55 行代码用于构造 M3 依赖注入上下文，每次调用都新建所有对象。与 `initialize()` 有大量重复（Provider + Repository 创建）。

**建议**: 拆分出公共的 `_create_providers()` 和 `_create_repositories()` 工厂函数。

---

## 逐 TC 通过性判定

| 测试用例 | 判定 | 阻断项 |
|:--------:|:----:|--------|
| **TC-3.1** Workflow 基类—正常 | ⚠️ | P1-1：日志在 scheduler.log 而非 app.log |
| **TC-3.2** Workflow 基类—异常 | ⚠️ | P1-1：同上，但异常传播+finally 正确 |
| **TC-3.3** WeeklyWorkflow 端到端 | ✅ | 5 步顺序正确，日志完整（P1-3 代码重复但不影响功能） |
| **TC-3.4** DailyWorkflow 端到端 | ❌ | P0-1：stock_id≠stock_code；P0-2：退潮预警不执行；P0-3：position 重复行；P1-4：净值计算错误 |
| **TC-3.5** Scheduler 解耦 | ✅ | register_jobs 只接收 Workflow，无 Engine 引用 |
| **TC-3.6** 退潮预警—减仓 | ⚠️ | P0-2：DailyWorkflow 无法触发；P1-5：第 4 条件缺失 |
| **TC-3.7** 退潮预警—退出 | ⚠️ | 同上 |
| **TC-3.8** 手动触发 API | ⚠️ | P2-3：CLI 替代 HTTP API |
| **TC-3.9** TradeLogger 录入 | ⚠️ | P1-2：trade_no 可能碰撞 |
| **TC-3.10** Workflow 调用链—Weekly | ✅ | 步骤顺序 1→2→3→4→5 正确 |
| **TC-3.11** Workflow 调用链—Daily | ❌ | P0-1：mock 验证会暴露 stock_id≠code |
| **TC-3.12** 步骤失败不静默 | ✅ | BaseWorkflow.run() 的 raise 正确传播异常 |

**M3 门禁状态**: ❌ **不通过**（3 条 TC 不通过，5 条条件通过，仅 4 条完全通过）

---

## M3 任务完成度

| 编号 | 任务 | 状态 | 备注 |
|:----:|------|:--:|------|
| T3.1 | workflow/base.py | ✅ | 日志/耗时/异常/re-raise 正确 |
| T3.2 | workflow/weekly_workflow.py | ✅ | 5 步完整（P1-3 代码重复） |
| T3.3 | workflow/daily_workflow.py | ❌ | P0-1/0-2/0-3 + P1-4 四重缺陷 |
| T3.4 | workflow/monthly_workflow.py | ✅ | 可工作（返回值未持久化但够用） |
| T3.5 | engine/theme_monitor.py | ⚠️ | M2 已实现，P1-5 第 4 条件未补充 |
| T3.6 | scheduler/jobs.py | ✅ | 完全解耦，符合 TC-3.5 |
| T3.7 | 手动触发 API | ⚠️ | CLI 而非 HTTP（P2-3） |
| T3.8 | TradeLogger | ⚠️ | 功能正确但 P1-2+P2-2 |

---

## 架构亮点

1. **BaseWorkflow 设计优秀** — 日志/异常/re-raise/finally 模式干净，子类只需实现 execute()
2. **Scheduler 解耦彻底** — register_jobs() 只接收 Workflow.run，零 Engine 引用
3. **依赖注入贯穿始终** — Provider/Engine/Repo 全部通过构造函数注入，Mock 友好
4. **CLI 入口统一** — `--weekly`/`--daily`/`--monthly` 覆盖所有 Workflow 手动触发
5. **WeeklyWorkflow 持久化完整** — 五步均有 try/except 保护，单板块失败不影响其余

---

## 后续行动建议

1. **立即**：修复 P0-1（stock_id→stock_code）、P0-2（退潮预警连接）、P0-3（position UNIQUE 约束）
2. **M3 收尾**：修复 P1-1~P1-5
3. **P2 可延至 M4**：Repository 方法补充、代码去重
4. **M4 启动条件**：TC-3.1~TC-3.12 中 ≥ 9 条通过（P0 全部清零）

---

> 评审人：Claude (自动化代码审查)
> 下一节点：P0+P1 修复后复审
