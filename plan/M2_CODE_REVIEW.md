# M2 代码评审报告

> 评审日期：2026-07-20
> 评审范围：commit `53e53e1` "M2: 核心引擎交付 — Scanner/Screener/Selector/Monitor + 终端仪表盘"
> 评审依据：PROJECT_PLAN.md 第四章 M2 测试用例 TC-2.1 ~ TC-2.20
> 评审方法：逐行代码审查 + 逐 TC 手工代入追踪 + 实际运行验证

---

## 评审摘要

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **P0** | 2 | 阻断性缺陷 — ThemeSelector 验证逻辑与规格偏离；Dashboard 在数据不可用时崩溃 |
| **P1** | 6 | 高优缺陷 — 算法替代指标与规格不符，TC 预期值偏差 |
| **P2** | 5 | 中优建议 — 代码质量、可维护性 |

**总体评价**：M2 代码结构完整，所有 11 个开发任务均有产出，算法引擎骨架正确。但存在 **对规格文档的偏离**——几条关键计算公式使用了简化近似替代，且与计划中定义的逻辑不完全一致。建议 P0+P1 修复后再判定 M2 门禁通过。

---

## P0 — 阻断性缺陷

### P0-1: `ThemeSelector._calc_confirmation()` 四项验证全部使用间接代理指标

**文件**: [engine/theme_selector.py:41-63](engine/theme_selector.py)

**问题**: PROJECT_PLAN.md B-2 明确定义了主线确认的四项验证逻辑，但代码实现用完全不同的指标替代，且代理关系不成立：

| # | 计划规格 | 代码实现 | 判定 |
|---|---------|---------|:--:|
| 1 | 已连续跑赢大盘 ≥ 3 周 | `rel_strength >= 0.7` | ⚠️ 近似可接受 |
| 2 | 有可辨识的产业逻辑（非纯题材） | `trend_score >= 0.5` | ❌ **趋势强度 ≠ 产业逻辑** |
| 3 | 板块成交额近 5 日均量 / 近 20 日均量 < 2.5 | `volume_ratio < 2.5` | ✅ 一致 |
| 4 | 板块 PE 分位 < 90% | `echelon_score >= 0.5` | ❌ **梯队完整性 ≠ PE 估值分位** |

**具体问题**：

**验证项 2（产业逻辑）** — `trend_score >= 0.5` 不可接受：
- 趋势强度衡量的是 MA 排列的技术指标，与"是否有可辨识的产业逻辑（非纯题材）"完全无关
- 一个纯题材炒作板块（如"龙字辈"概念）也可以有完美的 MA 多头排列
- 一个具备扎实产业逻辑的板块（如半导体设备国产替代）在回调期趋势强度可能很低

**验证项 4（PE 分位）** — `echelon_score >= 0.5` 不可接受：
- 梯队完整性衡量的是板块内涨停家数 + 大市值存在性，与 PE 估值分位无关
- 一个 PE 分位 95% 的极端拥挤板块仍可有活跃涨停梯队（涨停 + 大市值 = echelon_score ≥ 0.5）
- 一个 PE 分位 50% 的合理估值板块可能因为无涨停而 echelon_score = 0

**建议修复方案**:
- 验证项 2：当前环境无直接"产业逻辑"数据源，应在 M2 阶段**明确标注为占位符**，并在注释中说明 M3/M4 需引入外部数据源（如行业研报标签、分析师覆盖数）替代
- 验证项 4：FinancialProvider 已有 API 能力，应增加 PE 分位查询；或至少使用 `scan_result` 的其他指标组合
- 或：在代码注释中明确说明 M2 阶段使用近似指标，并标注为 `FIXME: M3`

**TC 影响**: TC-2.18 判定不通过（无法正确区分板块 A/B/C 的确认结果）

---

### P0-2: `dashboard()` 在数据拉取失败时直接崩溃

**文件**: [main.py:111-134](main.py), [engine/dashboard.py:31-84](engine/dashboard.py)

**问题**: TC-2.20 明确要求 "如果数据未就绪（首次启动尚未拉取），显示明确提示而非报错"。实际运行验证 (`python main.py --dashboard`) 结果：

```
RuntimeError: 所有板块数据源均拉取失败
```

系统在 `_init_sectors()` → `fetch_all_sectors()` 抛出 `RuntimeError` 后直接崩溃，未显示任何 Dashboard 降级输出。

**实际运行验证**:
```bash
$ python main.py --dashboard
# → 约 25 秒重试后直接 traceback 退出
# → 无 Dashboard 框架输出
# → 无 "数据不可用" 提示
```

**建议修复方案**: `build_dashboard()` 应对 `fetch_all_sectors()` 的异常做 catch：
```python
try:
    scan_results = scanner.scan_all(today)
except RuntimeError as e:
    logger.warning("数据拉取失败，生成降级面板: %s", e)
    return DashboardData(date=str(today), ..., themes=[], signals=[])
```

并在 `print_dashboard()` 中已有 "当前无确认主线（数据不足或市场无明确方向）" 分支，可以复用。

**TC 影响**: TC-2.20 不通过

---

## P1 — 高优缺陷

### P1-1: Scanner `_estimate_volume_ratio()` 指标含义与规格不符

**文件**: [engine/scanner/scanner.py:144-153](engine/scanner/scanner.py)

```python
def _estimate_volume_ratio(df, days=5):
    avg5 = df["amount"].tail(5).mean()
    avg20 = df["amount"].tail(20).mean()
    return avg5 / avg20
```

**问题**: 计划 ARCHITECTURE.md B-1 指标 3 定义的资金确认要求：

> "近 20 日板块成交额 / 全市场成交额 ≥ 板块流通市值 / 全市场流通市值"

即：**板块成交额占比 ≥ 板块市值占比**（衡量板块是否获得了超越其市值的资金关注）。

代码实现的是 `avg5_amount / avg20_amount`，即板块自身的近 5 日均量 / 近 20 日均量。这是一个**环比放量指标**，完全不同于规格定义的**市场占比指标**。当前实现只衡量了"该板块最近是否放量"，而非"该板块在全市场中是否获得资金倾斜"。

**建议修复方案**: 
- 需要获取全市场成交额（可从沪深 300 或全 A 成交额估算）
- 需要获取板块流通市值（可从 `sector` 表或 Provider 获取）
- 计算 `(板块成交额/N日 / 全市场成交额/N日) / (板块市值 / 全市场市值)`

**TC 影响**: TC-2.9、TC-2.10 中 `volume_ratio` 的含义被改变

---

### P1-2: Screener `_estimate_rank()` 使用无意义的绝对阈值

**文件**: [engine/screener/screener.py:159-168](engine/screener/screener.py)

```python
def _estimate_rank(code, avg_vol):
    if avg_vol > 1e9:    return 3
    if avg_vol > 5e8:    return 5
    if avg_vol > 1e8:    return 8
    return 12
```

**问题**: 计划 ARCHITECTURE.md C-1 维度 2 要求：

> "近 20 日均成交额在板块内排名前 5 → 1.0；排名 6-10 → 0.5；排名 >10 → 0.1"

这是一个**板块内相对排名**，需要知道同板块其他个股的成交额才能计算。代码使用绝对量阈值（1 亿/5 亿/10 亿），完全丧失了"板块内相对排名"的语义：
- 在大市值板块（如银行），1 亿成交额排名垫底
- 在小市值板块（如林业），1 亿成交额排名第一

**建议修复方案**: `_score_one()` 已经拉取了个股的 `avg_vol`，应在 `screen()` 方法内收集板块所有成分股的成交量，然后计算真实排名：

```python
def screen(self, ...):
    stocks_df = self._get_sector_stocks(sector_code)
    # 第一遍：收集所有成交量排名
    vol_map = {}
    for _, s in stocks_df.iterrows():
        ...  # 计算 avg_vol
        vol_map[code] = avg_vol
    sorted_vols = sorted(vol_map.items(), key=lambda x: x[1], reverse=True)
    rank_map = {code: i+1 for i, (code, _) in enumerate(sorted_vols)}
    # 第二遍：用真实排名评分
```

**TC 影响**: TC-2.17 的 liquidity 维度没有实际验证意义

---

### P1-3: `calc_trend_score()` NaN 输入不抛异常不记录 WARNING（TC-2.5 不通过）

**文件**: [engine/scanner/trend.py:10-15](engine/scanner/trend.py)

```python
def _gt(a, b):
    if a is None or b is None:
        return False
    if math.isnan(a) or math.isnan(b):
        return False      # ← 静默返回 False，无日志
    return a > b
```

**问题**: TC-2.5 要求 "抛出 ValueError 或返回 0.0 并记录 WARNING 日志"。实际代码：
- 没有抛出 ValueError ✓ （策略选择了返回 False）
- 没有记录 WARNING ✗
- 返回 0.5 而非 0.0 ✗ （MA10>MA21 + MA21>MA55 仍然产生非零分数）

**代入验证**（TC-2.5 输入：MA5=NaN, MA10=11, MA21=10, MA55=9）:
- `_gt(NaN, 11)` → `isnan(NaN)`=True → False (不满足)
- `_gt(11, 10)` → True → +0.25
- `_gt(10, 9)` → True → +0.25
- `_gt(NaN, 9)` → False
- Total = **0.5 ≠ 0.0**

**建议修复方案**: 检测到 NaN 输入时记录 WARNING，并返回 0.0：
```python
def calc_trend_score(ma5, ma10, ma21, ma55):
    import logging
    vals = [ma5, ma10, ma21, ma55]
    if any(v is not None and (isinstance(v, float) and math.isnan(v)) for v in vals):
        logging.getLogger("app.scanner").warning("趋势强度输入包含 NaN，返回 0.0")
        return 0.0
    ...
```

**TC 影响**: TC-2.5 不通过

---

### P1-4: `MAMonitor` B 级买点未检查"板块 3 只以上同步放量"

**文件**: [engine/ma_monitor.py:70-73](engine/ma_monitor.py)

```python
# B级买点: 距 MA10 3-8% + 放量
if (ma10 and deviation is not None and 0.03 <= deviation < 0.08
        and vol_ratio > 1.5):
    return SignalType.B_BUY
```

**问题**: 计划 ARCHITECTURE.md C-2 定义 B 级买点需要 **三个条件同时满足**：
1. 板块内 3 只以上同步放量 ← **缺失**
2. 中军涨幅 3-5%
3. 成交量 > 5 日均量的 1.5 倍

代码实现：
- 条件 1：**完全缺失**（`MAMonitor.check()` 只接收单个 `stock_code`，不了解板块内其他股票状态）
- 条件 2：检查 `0.03 <= deviation < 0.08`（价格距 MA10 偏离 3-8%，与实际涨幅不完全等价）
- 条件 3：检查 `vol_ratio > 1.5`（但 `vol_ratio` 是用 20 日均量计算的，不是 5 日均量）

**建议修复方案**: 要么在 M2 阶段明确注释 `# FIXME(M3): 需要 Workflow 传入板块共振状态`，要么在 `MAMonitor.check()` 签名中新增可选参数 `sector_resonance: bool = False`。

**TC 影响**: TC-2.19 B 级买点条件判定不完整

---

### P1-5: Screener `_get_sector_stocks()` 不利用 sector type 路由

**文件**: [engine/screener/screener.py:148-157](engine/screener/screener.py)

```python
def _get_sector_stocks(self, sector_code: str) -> pd.DataFrame:
    try:
        return ak.stock_board_concept_cons_em(symbol=sector_code)  # 先试概念
    except Exception:
        pass
    try:
        return ak.stock_board_industry_cons_em(symbol=sector_code)  # 再试行业
    except Exception:
        pass
    return pd.DataFrame()
```

**问题**: `screen()` 方法接收了 `sector_code` 参数，但没有接收 `sec_type`。调用方 `dashboard.py:63` 传入 `theme.get("sector_code", "")` 但没有传递板块类型。结果是：
- 对行业板块，先无意义地调用概念 API（浪费一次网络请求 + 异常处理开销）
- 静默失败后 fallback 到行业 API

对比 P0-2 修复中 `MarketProvider._do_fetch_sector_daily()` 已经通过 `sec_type` 参数做了正确的 API 路由，`_get_sector_stocks()` 应遵循相同模式。

**建议修复方案**: 
1. `screen()` 签名增加 `sec_type: str` 参数
2. `_get_sector_stocks()` 按 type 路由：concept → `stock_board_concept_cons_em`，industry → `stock_board_industry_cons_em`

---

### P1-6: Dashboard 崩溃前无任何降级输出

**文件**: [main.py:111-134](main.py)

**问题**: 除 P0-2 描述的崩溃外，`dashboard()` 在 `_init_sectors()` 失败后不会执行到 `build_dashboard()`。但实际上 `_init_sectors()` 的错误处理策略是错误的：当 sector 表已有数据时应该跳过板块重拉取，直接进入 Dashboard 显示。

当前逻辑：
```python
existing = nav_repo.get_latest()
if not existing:
    _init_sectors(market, sector_repo)   # ← 崩溃点：即使 sector 表有数据也会被跳过
```

这意味着如果有 NAV 记录但没有 sector 记录（或 sector API 失败），Dashboard 完全无法启动。

**建议修复方案**: 
```python
sectors = sector_repo.get_all_active()
if not sectors:
    _init_sectors(market, sector_repo)
else:
    logger.info("板块数据已存在（%d 个），跳过拉取", len(sectors))
```

---

## P2 — 中优建议

### P2-1: `screener.py` 延迟导入 `akshare` 在文件末尾

**文件**: [engine/screener/screener.py:186](engine/screener/screener.py)

```python
# 延迟导入避免循环
import akshare as ak
```

`ak` 在类方法 `_get_sector_stocks()`（第 150 行）中使用，但导入语句在文件末尾（第 186 行）。这之所以能工作，是因为 `_get_sector_stocks()` 只在 `screen()` 被调用时才执行，而那时模块已完全加载。但这种模式容易在重构时引入 `NameError`。建议将 `import akshare as ak` 移到标准位置（模块顶部），如有循环导入问题应解决根本原因而非延迟导入。

---

### P2-2: `dashboard.py` 中 `fuse_level` 硬编码为 `"NORMAL"`

**文件**: [engine/dashboard.py:82](engine/dashboard.py)

```python
fuse_level="NORMAL",  # ← 永远为 NORMAL，未读取 risk_event 表
```

`RiskRepository` 已实现，`risk_event` 表已建好，但 Dashboard 完全不查风控状态。M2 阶段可以接受（M4 才实现三级熔断），但应标注 `# FIXME(M4): 从 RiskRepository.get_recent() 读取实际熔断状态`。

---

### P2-3: `ThemeSelector._calc_confirmation()` 对 `ScanResult` 使用 `getattr` 而非属性访问

**文件**: [engine/theme_selector.py:47](engine/theme_selector.py)

```python
if (getattr(r, 'rel_strength', None) or 0) >= 0.7:
```

**问题**: `confirm()` 方法将 `scan_result.__dict__` 传入后，`_calc_confirmation` 接收的是 `dict` 还是 `SectorScanResult` 对象取决于调用方。`getattr` 同时支持两种类型，但牺牲了类型安全性和 IDE 支持。直接使用 `r.rel_strength` 配合类型注解更清晰。

---

### P2-4: `_calc_vol_profile()` 中 `pct_change()` 第一个元素为 NaN

**文件**: [engine/screener/screener.py:176](engine/screener/screener.py)

```python
up_mask = df["close"].pct_change() > 0
```

`pct_change()` 的第一个元素为 `NaN`，`NaN > 0` 为 `False`，因此第一行被归入下跌日（不影响上涨日均量）。这不影响正确性，但下跌日均量计算中混入了一个中性日。建议加 `fillna(False)` 或从第二行开始计算。

---

### P2-5: TC-2.2 与 TC-2.8 预期值与代码输出存在偏差

**TC-2.2**: 输入 `(11, 12, 10, 8)`，代码计算：
- ma5(11) > ma10(12) → False
- ma10(12) > ma21(10) → True (+0.25)
- ma21(10) > ma55(8) → True (+0.25)
- ma5(11) > ma55(8) → True (+0.25)
- **实际输出 = 0.75**，计划预期 = 0.25

**根因**: 计划 TC-2.2 编写时似乎只考虑了 3 个级别（MA5>MA10, MA10>MA21, MA21>MA55），但代码实现了 4 个检查（增加了 MA5>MA55 长期趋势确认）。需要确认是代码正确还是计划正确，两者需对齐。

**TC-2.8**: 输入 `sector_ret=-0.02, hs300=-0.10`，代码计算：
- ratio = -0.02 / -0.10 = 0.2
- linear_map = (0.2 - 0.0) / 1.5 = 0.133
- **实际输出 = 0.133**，计划预期 > 0.5

**根因**: 当大盘和板块都下跌时，比值法的映射对"板块跌得少=有超额"的奖励不足。应使用差值法（超额收益）而非比值法：
```
excess = sector_ret_20d - hs300_ret_20d  # -0.02 - (-0.10) = 0.08
# 板块超额 8%，映射到 > 0.5
```

**建议**: 统一确认 TC 预期值或修改代码逻辑，消除文档与实现的偏差。

---

## 逐 TC 通过性判定

| 测试用例 | 判定 | 阻断项 |
|:--------:|:----:|--------|
| **TC-2.1** 趋势—多头排列 | ✅ | — |
| **TC-2.2** 趋势—部分满足 | ❌ | P2-5：代码输出 0.75 ≠ 预期 0.25 |
| **TC-2.3** 趋势—完全空头 | ✅ | — |
| **TC-2.4** 趋势—边界条件 | ✅ | — |
| **TC-2.5** 趋势—NaN 处理 | ❌ | P1-3：无 WARNING + 返回 0.5 ≠ 0.0 |
| **TC-2.6** 相对强度—跑赢 | ✅ | — |
| **TC-2.7** 相对强度—跑输 | ✅ | — |
| **TC-2.8** 相对强度—抗跌超额 | ❌ | P2-5：代码输出 0.133，预期 > 0.5 |
| **TC-2.9** 资金确认—双满足 | ✅ | (但 P1-1：volume_ratio 含义已变) |
| **TC-2.10** 资金确认—单满足 | ✅ | (同上) |
| **TC-2.11** 梯队—双满足 | ✅ | — |
| **TC-2.12** 梯队—无涨停 | ✅ | — |
| **TC-2.13** Scanner 端到端 | ⚠️ | P1-1 volume_ratio 指标错位 |
| **TC-2.14** 市值规模 | ✅ | — |
| **TC-2.15** 均线结构 | ✅ | — |
| **TC-2.16** 量价健康度 | ✅ | — |
| **TC-2.17** Screener 端到端 | ⚠️ | P1-2：liquidity 排名使用假数据 |
| **TC-2.18** 主线确认 | ❌ | P0-1：代理指标与规格不一致 |
| **TC-2.19** 买卖点信号 | ⚠️ | P1-4：B 级买点缺板块共振检查 |
| **TC-2.20** 终端仪表盘 | ❌ | P0-2：数据不可用时崩溃 |

**M2 门禁状态**: ❌ **不通过**（4 条 TC 不通过，3 条条件通过，仅 9 条完全通过）

---

## M2 任务完成度

| 编号 | 任务 | 状态 | 备注 |
|:----:|------|:--:|------|
| T2.1 | scanner/trend.py | ✅ | P1-3 NaN 需修复 |
| T2.2 | scanner/rel_strength.py | ✅ | P2-5 大盘同跌场景需修正 |
| T2.3 | scanner/fund_flow.py | ✅ | — |
| T2.4 | scanner/echelon.py | ✅ | — |
| T2.5 | scanner/scanner.py | ⚠️ | P1-1 volume_ratio 定义偏离 |
| T2.6 | screener/ 五个维度 | ✅ | 全部实现 |
| T2.7 | screener/screener.py | ⚠️ | P1-2/P1-5 需修复 |
| T2.8 | theme_selector.py | ❌ | P0-1 代理指标不可接受 |
| T2.9 | ma_monitor.py | ⚠️ | P1-4 B 级买点缺条件 |
| T2.10 | 其余 Repository | ✅ | core_score/position/risk/trade 全部实现 |
| T2.11 | 终端仪表盘 | ❌ | P0-2 崩溃 / P2-2 熔断硬编码 |

---

## 架构亮点

1. **模块分离清晰** — Scanner/Screener/Selector/Monitor 各司其职，依赖注入（Provider 作为参数传入）设计合理
2. **评分函数无副作用** — 维度评分函数（trend/rel_strength/fund_flow/echelon 等）均为纯函数，易于单元测试
3. **dataclass 类型定义** — `SectorScanResult`、`CoreScoreResult`、`DashboardData` 提供了良好数据结构
4. **提前完成 theme_monitor** — M3 的退潮预警（T3.5）已在 M2 提前实现，进度超前
5. **仪表盘有降级提示** — `print_dashboard()` 对无主线/无信号场景有明确提示文案

---

## 后续行动建议

1. **立即**：修复 P0-1（ThemeSelector 代理指标标注）+ P0-2（Dashboard 异常保护）
2. **M2 收尾**：修复 P1-1 到 P1-6
3. **TC 对齐**：与 PROJECT_PLAN.md 确认 TC-2.2、TC-2.8 的预期值，统一代码或文档
4. **M3 启动条件**：TC-2.1 ~ TC-2.20 中 ≥ 17 条通过（允许 P2-5 类文档对齐问题）

---

> 评审人：Claude (自动化代码审查)
> 下一节点：P0+P1 修复后复审，M3 启动前
