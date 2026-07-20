# M1 代码评审报告

> 评审日期：2026-07-04
> 评审范围：M1 v0.1 数据底座（commit `241a094`）
> 评审依据：PROJECT_PLAN.md 第三章 M1 测试用例 TC-1.1 ~ TC-1.10
> 评审方法：逐文件代码审查 + 逐测试用例对照 + 运行日志分析

---

## 评审摘要

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **P0** | 3 | 阻断性缺陷 — 数据管线可能被污染，必须在 M2 前修复 |
| **P1** | 5 | 高优缺陷 — 导致 3 条 TC 不通过，日志/重试/异常行为不符合规格 |
| **P2** | 6 | 中优建议 — 健壮性、一致性、可测试性问题 |

**总体评价：M1 骨架结构良好，但 3 个 P0 缺陷使当前代码无法通过 M1 门禁。建议全部 P0+P1 修复后再进入 M2。**

---

## P0 — 阻断性缺陷

### P0-1: `MarketProvider.fetch_all_sectors()` 申万行业 API 选型错误

**文件**: [data/providers/market_provider.py:18](data/providers/market_provider.py)

```python
sw = ak.index_stock_cons_csindex(symbol="000811")
sw = sw.rename(columns={"成分券代码": "code", "成分券名称": "name"})
sw["type"] = "sw_industry"
```

**问题**: `ak.index_stock_cons_csindex(symbol="000811")` 获取的是 **中证 800 指数的成分股列表**（个股），而非申万行业分类（板块）。列名 `成分券代码`/`成分券名称` 可佐证：这些是个股代码和个股名称，不是板块代码和板块名称。

**实际影响**:
- `_init_sectors()` 将个股当作"板块"写入了 `sector` 表，污染整个数据底座
- 运行日志显示仅获取了 50 条（可能是分页截断或 API 实现差异），而非预期的 800 只成分股
- 下游 Scanner 扫描这些"假板块"时，`fetch_sector_daily()` 会失败（见 P0-2）
- TC-1.5 要求返回 "> 100 个板块"，当前运行结果仅 50 个

**建议修复方案**:
```python
# 替换为申万行业分类 API，例如：
sw = ak.index_industry_sw()  # 或其他申万行业分类接口
```

或至少使用 `ak.stock_board_industry_name_em()` 获取东方财富行业板块。

**TC 影响**: TC-1.5 不通过（行数 < 100，数据类型错误）

---

### P0-2: `fetch_sector_daily()` 仅支持概念板块代码

**文件**: [data/providers/market_provider.py:47-50](data/providers/market_provider.py)

```python
def _do_fetch_sector_daily(self, code: str, start: date, end: date) -> pd.DataFrame:
    df = ak.stock_board_concept_hist_em(
        symbol=code, period="daily", ...
```

**问题**: `ak.stock_board_concept_hist_em()` 仅接受概念板块代码（格式如 `BK0001`）。申万行业板块代码格式不同，调用会直接失败。P0-1 修复后会引入更多非概念板块代码，此接口无法覆盖。

**实际影响**: 若 Scanner 对任意非概念板块调用此方法，将抛出异常导致扫描中断。

**建议修复方案**: 根据 `sector.type` 字段分发到不同 API — 概念板块用 `stock_board_concept_hist_em`，行业板块用对应行业指数 API（如 `ak.index_industry_sw_hist` 或东方财富行业指数接口）。

**TC 影响**: TC-1.6 对非概念板块不通过

---

### P0-3: `fetch_all_sectors()` 中概念板块拉取未使用重试机制

**文件**: [data/providers/market_provider.py:17-32](data/providers/market_provider.py)

```python
try:
    gn = ak.stock_board_concept_name_em()  # 直接调用，无 retry
    ...
except Exception as e:
    self.logger.warning(f"概念板块拉取失败: {e}")
```

**问题**: 该类继承了 `BaseProvider`，其核心价值就是 `fetch_with_retry()` 带指数退避重试。但 `fetch_all_sectors()` 直接调用底层 akshare API，绕过了重试机制。**实际运行日志证实了该问题**：

```
[WARNING] [MarketProvider] 概念板块拉取失败: ... ProxyError ...
[INFO] [MarketProvider] 板块列表拉取成功，共 50 个
```

概念板块因代理问题一次性失败后直接放弃，没有进行任何重试。只有申万行业那支（错误地）返回了 50 条数据。

**实际影响**: 在弱网环境下，概念板块（约 200+ 个）会频繁丢失，导致 Scanner 只扫描到错误的"板块"。TC-1.5 要求返回 > 100 个板块无法稳定满足。

**建议修复方案**: 将 `ak.stock_board_concept_name_em()` 调用包裹在 `self.fetch_with_retry()` 中，或将 `fetch_all_sectors()` 重构为使用 `fetch_with_retry` 的子调用。

**TC 影响**: TC-1.5、TC-1.7 不通过

---

## P1 — 高优缺陷

### P1-1: 缺少 .env 缺失时的 WARNING 日志（TC-1.2 不通过）

**文件**: [config.py:7](config.py)

```python
load_dotenv()  # 如果 .env 不存在，返回 False，但完全不检查
```

**问题**: TC-1.2 明确要求 "日志中有一条 WARNING：'未找到 .env 文件，使用默认配置'"。当前实现仅依赖 `os.getenv()` 的默认值机制（即 `.env` 不存在时走硬编码默认），但**从未记录任何 WARNING**。

**实际影响**: 用户误删 `.env` 后系统静默切换到默认值，无法感知配置来源已变。TC-1.2 判定不通过。

**建议修复方案**: 在 `load_dotenv()` 之后检查返回值，或在 `AppConfig.__post_init__` 中增加 `.env` 文件存在性检查：
```python
if not load_dotenv():
    logging.getLogger("config").warning("未找到 .env 文件，使用默认配置")
```

---

### P1-2: app.log 与 scheduler.log 内容完全重复（TC-1.3 不通过）

**文件**: [config.py:14-59](config.py)

```python
root = logging.getLogger()
# ...
app_handler = logging.FileHandler(...)     # INFO+
sched_handler = logging.FileHandler(...)   # INFO+
# 两个 handler 都绑定在 root logger 上，没有任何 logger name 过滤
```

**问题**: TC-1.3 明确规定了三个文件的职责分工：
- `app.log`：启动日志、Provider 拉取日志、Engine 计算日志
- `scheduler.log`：定时任务注册日志、日终更新开始/完成日志
- `error.log`：异常堆栈

当前实现中，`app_handler` 和 `sched_handler` 都是 `INFO` 级别 + 相同的 `formatter`，且都绑定在 `root` logger 上。**所有 INFO+ 消息会原样同时写入 app.log 和 scheduler.log**，两个文件内容完全重复。

`error.log` 的 ERROR 级别过滤是正确的（仅 error.log 收到 ERROR 消息），但 app.log 和 scheduler.log 之间没有任何隔离。

**实际影响**: scheduler 的定时任务日志会污染 app.log，app 的业务日志也会污染 scheduler.log。TC-1.3 判定不通过。

**建议修复方案**: 使用 logger hierarchy 分离：
- `logging.getLogger("app")` → app.log
- `logging.getLogger("scheduler")` → scheduler.log

或在 handler 上添加 `Filter` 按 logger name 过滤。

---

### P1-3: `FinancialProvider` 所有 API 调用失败时不抛异常

**文件**: [data/providers/financial_provider.py:14-57](data/providers/financial_provider.py)

```python
def _do_fetch_financials(self, code: str) -> dict:
    result = {"revenue_yoy": None, "profit_yoy": None, "roe": None, "gross_margin": None}
    try:
        ...
    except Exception as e:
        self.logger.warning(...)
    # 如果两个 try 块都失败，返回 {全 None} 的 dict，不抛异常
    return result
```

**问题**: 当 `fetch_with_retry` 三次重试全部失败后，`_do_fetch_financials` 返回全 None 字典。`fetch_with_retry` 不会对这个结果有任何反应（它只处理异常，不检查 None 值）。

**实际影响**: Scanner/Screener 会在不知情的情况下使用 None 作为评分输入，导致 NaN 评分。问题被"静默"传播到决策层。没有明确的错误信号让 Workflow 知道数据不可靠。

**建议修复方案**: 当所有关键字段（至少 `revenue_yoy` 和 `roe`）为 None 时，`_do_fetch_financials` 应抛出 `RuntimeError`，让 `fetch_with_retry` 捕获并记录完整堆栈。

---

### P1-4: `AnnouncementProvider` 日期构造逻辑脆弱 + 静默吞异常

**文件**: [data/providers/announcement_provider.py:22-24](data/providers/announcement_provider.py)

```python
df = ak.stock_yjyg_em(date="".join(
    str(date.today()).split("-")[:3]
).replace("-", ""))
```

**问题 A — 过度复杂的日期构造**:
1. `str(date.today())` → `"2026-07-04"`
2. `.split("-")` → `["2026", "07", "04"]`
3. `[:3]` → `["2026", "07", "04"]`（永远等于自身，无意义切片）
4. `"".join(...)` → `"20260704"`
5. `.replace("-", "")` → `"20260704"`（已经无连字符，无意义 replace）

等效于 `date.today().strftime("%Y%m%d")`。当前实现有大量无用操作，且在非标准 `date.isoformat()` 实现下可能行为不一致。

**问题 B — 静默返回空列表**:
```python
except Exception as e:
    self.logger.warning(f"业绩预告拉取失败: {e}")
    return []
```

所有异常被静默吞掉并返回空列表。调用方无法区分"最近无预告"和"API 拉取失败"。

**建议修复方案**:
```python
df = ak.stock_yjyg_em(date=date.today().strftime("%Y%m%d"))
```
异常处理应区分"API 失败"（应 re-raise）和"数据为空"（可返回 `[]`）。

---

### P1-5: `AnnouncementProvider` 公告日期解析吞异常

**文件**: [data/providers/announcement_provider.py:33-34](data/providers/announcement_provider.py)

```python
try:
    notice_date = pd.Timestamp(row.get("公告日期"))
    ...
except Exception:
    continue  # 静默跳过，无日志
```

**问题**: 如果某些行的日期字段格式异常，该条公告被**静默丢弃**。无日志、无计数、无任何提示。调用方拿到 0 条结果时无法判断是真的 0 条还是全部被跳过了。

**建议修复方案**: 至少记录一条 DEBUG 日志说明跳过的原因和行号。

---

## P2 — 中优建议

### P2-1: 计划文档内部不一致 — 声称 9 张表，实际列出 8 张

**文件**: [plan/PROJECT_PLAN.md:148-149](plan/PROJECT_PLAN.md)

> "输出包含 9 张表：sector, sector_snapshot, stock, core_score_snapshot, trade, position, risk_event, nav_snapshot"

**问题**: 文字声称 9 张，但枚举的列表只有 **8 张**。`schema.sql` 正确实现了这 8 张表。纯属计划文档的计数错误，不影响实现。

**建议**: 在 PROJECT_PLAN.md 中将 "9 张表" 修正为 "8 张表"，或补充缺失的第 9 张表定义。

---

### P2-2: `_init_db()` 绕过 Repository 层直接操作 SQLite

**文件**: [main.py:16-28](main.py)

```python
def _init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    with open(schema_path, encoding="utf-8") as f:
        conn.executescript(f.read())
```

**问题**: PROJECT_PLAN_REVIEW_RESPONSE.md 的 P2-1 建议明确要求 "Repository 从 M2 提前到 M1，避免开发早期形成直接操作 SQLite 的习惯"。Repository 层已经实现，但 `_init_db()` 仍绕过它，直接使用 `sqlite3.connect()` + `executescript()`。

这不影响功能，但与架构约定的"数据访问全部走 Repository"原则不一致。

**建议**: 保持现状可以接受（DDL 天然不适合 Repository 模式），但建议在函数上添加简短注释说明为何绕过 Repository。

---

### P2-3: `StockRepository` 缺少 `get_by_sector()` 方法

**文件**: [repositories/stock_repository.py](repositories/stock_repository.py)

**问题**: PROJECT_PLAN.md 的 Screener 需求明确要求 "在确认主线的板块内，锁定 1-2 只中军标的"，这需要按 `sector_id` 查询个股列表。当前 `StockRepository` 仅有 `upsert_stock` 和 `get_by_code`，缺少 `get_by_sector(sector_id)`。

**建议**: 增加 `get_by_sector(sector_id: int) -> list[dict]` 方法，M2 的 Screener 开发会直接需要它。

---

### P2-4: SQLite 未启用 WAL 模式

**文件**: [repositories/sector_repository.py:11-12](repositories/sector_repository.py)

**问题**: 所有 Repository 的 `_conn()` 方法创建连接后未执行 `PRAGMA journal_mode=WAL`。M3 阶段 APScheduler + Web server 并发写入时会出现 `database is locked` 错误。

**建议**: 在 `_init_db()` 或 Repository 的 `_conn()` 中增加 `PRAGMA journal_mode=WAL`。

---

### P2-5: `fetch_index_daily()` 输出列名不一致

**文件**: [data/providers/market_provider.py:113-124](data/providers/market_provider.py)

```python
def _do_fetch_index_daily(self, index_code, start, end):
    df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    mask = ...
    return df  # 未做列重命名
```

**问题**: `fetch_sector_daily` 和 `fetch_stock_daily` 都对 akshare 返回的列进行了中文→英文重命名，但 `fetch_index_daily` 没有。调用方拿到的列名不一致（可能是中文列名如 `开盘`、`收盘`）。

**建议**: 统一列重命名逻辑，或抽取公共的 `_normalize_columns()` 方法。

---

### P2-6: 测试目录完全为空

**文件**: [tests/](tests/)

```
tests/__init__.py          # 空
tests/test_scanner/        # 空目录
tests/test_screener/       # 空目录
```

**问题**: PROJECT_PLAN.md 列出了 10 个 M1 测试用例（TC-1.1 ~ TC-1.10），但项目中没有任何自动化测试。虽然 M1 开发任务表中没有显式的"编写测试"任务，但所有 TC 的验证目前仅能通过人工检查完成。

**建议**: M1 阶段至少应覆盖 TC-1.1（配置）、TC-1.4（建表）、TC-1.10（Repository 读写），这三者不依赖外部网络，易于编写。

---

## 逐 TC 通过性判定

| 测试用例 | 判定 | 阻断项 |
|:--------:|:----:|--------|
| **TC-1.1** 环境配置加载 | ⚠️ 条件通过 | 功能可用但 P1-1：`.env` 缺失时无 WARNING |
| **TC-1.2** 默认值回退 | ❌ 不通过 | P1-1：缺少 WARNING 日志 |
| **TC-1.3** 日志三文件输出 | ❌ 不通过 | P1-2：app.log / scheduler.log 内容重复 |
| **TC-1.4** SQLite 建表完整性 | ⚠️ 条件通过 | 8 张表（非计划的 9 张），但计划自身计数有误 P2-1 |
| **TC-1.5** 板块数据拉取 | ❌ 不通过 | P0-1：API 选型错误；P0-3：概念板未重试 |
| **TC-1.6** 日K + 均线计算 | ❌ 不通过 | P0-2：仅支持概念板块代码 |
| **TC-1.7** 拉取失败重试 | ❌ 不通过 | P0-3：`fetch_all_sectors` 未用 `fetch_with_retry` |
| **TC-1.8** 财务数据拉取 | ⚠️ 条件通过 | P1-3：API 全失败时不抛异常，返回全 None |
| **TC-1.9** 公告数据拉取 | ⚠️ 条件通过 | P1-4、P1-5：日期解析脆弱，静默丢失数据 |
| **TC-1.10** NavRepository 读写 | ✅ 通过 | — |

**M1 门禁状态**: ❌ **不通过**（3 条 TC 明确不通过，4 条条件通过，仅 1 条完全通过）

---

## 依赖风险矩阵

| 风险 | 来源 | 对 M2 的影响 |
|------|------|------------|
| 板块数据被个股数据污染 | P0-1 | Scanner 的 `scan_all()` 输入数据完全错误，扫描结果无意义 |
| 概念板块 API 不稳定 | P0-3 | 每周扫描时如果网络波动，可能只扫到部分板块 |
| 日志无分离 | P1-2 | M3 Scheduler 调试困难，无法快速定位定时任务问题 |
| StockRepository 缺 `get_by_sector` | P2-3 | M2 Screener 开发时需要现场补充，增加联调成本 |

---

## 后续行动建议

1. **立即**（M2 启动前）：修复 P0-1、P0-2、P0-3
2. **M2 第一周内**：修复 P1-1 ~ P1-5
3. **M2 第二周内**：处理 P2-3、P2-4、P2-5
4. **M3 启动条件**：TC-1.1 ~ TC-1.10 全部通过（自动化或人工验证记录）

---

> 评审人：Claude (自动化代码审查)
> 下次评审节点：M2 v0.2 交付后
