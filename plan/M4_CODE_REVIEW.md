# M4 代码评审报告

> 评审日期：2026-07-20
> 评审范围：commit `180406f` "M4: 风控仓位交付 — PositionManager/RiskController/OrderExecutor/MonthlyReport"
> 评审依据：PROJECT_PLAN.md 第六章 M4 测试用例 TC-4.1 ~ TC-4.14 + BRT-01~08
> 方法：逐行代码审查 + 逐 TC 数值代入验证 + 跨模块依赖检查

---

## 评审摘要

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **P0** | 3 | 阻断性缺陷 — 熔断事件不持久化；Dashboard 熔断状态未接入；月度报告缺少多个必需字段 |
| **P1** | 4 | 高优缺陷 — T4.6 轮询止损缺失；板块退潮价格类型不对；BRT-05 仅委托不执行 |
| **P2** | 3 | 中优建议 — CLI 入口缺口；日志级别偏差；PositionManager 不支持加仓场景 |

**总体评价**：PositionManager、RiskController、OrderExecutor 的数值计算**全部正确**（9 个 TC 数值代入验证通过）。M4 的核心缺陷集中在 **跨模块集成缺失** — 熔断事件不写入 DB、Dashboard 不读取风控状态、月度报告不完整。三个 Engine 模块在孤立状态下正确，但未通过 Repository 层与系统其余部分连接。

---

## P0 — 阻断性缺陷

### P0-1: `RiskController` 完全不写入 `risk_event` 表

**文件**: [engine/risk_controller.py](engine/risk_controller.py)

**验证**: `grep RiskRepository risk_controller.py` → **No matches found**

**问题**: RiskController 的 `check_stock()`、`check_daily()`、`check_monthly()` 仅记录日志并返回 `FuseLevel` 枚举值，但 **从未调用 `RiskRepository.log()` 写入 `risk_event` 表**。该类甚至没有持有 `RiskRepository` 的引用。

**TC 影响**:
- TC-4.8: 要求 "risk_event 表有新记录" → **不通过**
- TC-4.10/4.11/4.12: 同样依赖 DB 记录追踪熔断历史

**建议修复**:
```python
class RiskController:
    def __init__(self, ..., risk_repo: RiskRepository = None):
        self.risk_repo = risk_repo
    
    def _log_event(self, event_type, level, detail):
        if self.risk_repo:
            self.risk_repo.log(
                event_time=datetime.now().isoformat(),
                event_type=event_type,
                event_level=level,
                detail=detail,
            )
```

---

### P0-2: Dashboard 的 `fuse_level` 仍硬编码为 `"NORMAL"`

**文件**: [engine/dashboard.py:59, 98](engine/dashboard.py)

```python
fuse_level="NORMAL",  # 两处均为硬编码
```

**问题**: Round 1 M2 评审的 P2-2 标注了 `FIXME(M4)`，但 M4 交付的 `RiskController` 和 `RiskRepository` 均未集成到 Dashboard。无论风控实际触发什么级别，Dashboard 永远显示 "NORMAL"。

**实际上 M4 已有全部所需组件**：`RiskRepository`（M2）+ `RiskController`（M4），只需在 `build_dashboard()` 中调用 `RiskRepository.get_recent(limit=1)` 并解析最新事件级别。

**TC 影响**: TC-4.13 的 `fuse_level` 字段永远为 `"NORMAL"` → **不通过**

---

### P0-3: `MonthlyReport` 缺少多个计划必需字段

**文件**: [journal/monthly_report.py](journal/monthly_report.py)

**验证**: `grep "max_single\|by_sector\|by_signal\|win_loss" monthly_report.py` → **No matches found**

| 计划字段 (TC-4.14) | 实现状态 |
|:---|---:|
| `trade_count` | ✅ |
| `win_rate` | ✅ |
| `monthly_return` | ✅ |
| `violation_count` | ✅ |
| `max_single_win_pct` | ❌ 缺失 |
| `max_single_loss_pct` | ❌ 缺失 |
| `avg_win_loss_ratio` | ❌ 缺失 |
| `by_sector` (按板块归因) | ❌ 缺失 |
| `by_signal` (按 A/B 买点对比) | ❌ 缺失 |
| `summary` (一句话自动总结) | ⚠️ 有基础版 |

**TC 影响**: TC-4.14 不通过 — 报告不完整

---

## P1 — 高优缺陷

### P1-1: T4.6 价格轮询止损未实现

**计划要求**: "APScheduler 每 5 分钟轮询 + 熔断触发"
**实际状态**: `scheduler/jobs.py` 仍只有 weekly/daily/monthly 三个 cron，无盘中轮询任务

RiskController 的 `check_stock()` 逻辑已实现，但没有调度器触发它。M4 无法在真实场景中检测个股止损。

**建议**: 在 `scheduler/jobs.py` 中添加 `interval` 任务，或在 M5 通过 WebSocket/API 触发。

---

### P1-2: TC-4.7 板块退潮应使用 LIMIT 但代码统一为 MARKET

**文件**: [engine/position_manager.py:134-140](engine/position_manager.py)

```python
elif signal in ("EXIT", "STOP_LOSS"):
    return TradeOrder(..., price_type="MARKET")
```

**问题**: `calc_sell()` 将 EXIT 和 STOP_LOSS 统一为 MARKET。但 TC-4.7 明确要求板块退潮引起的退出使用 **LIMIT**（"不是紧急止损，可以挂限价单"）。当前代码无法区分"MA21 破位退出"和"板块退潮退出"。

**建议**: 新增 `SECTOR_EXIT` 信号类型，price_type 设为 LIMIT。

---

### P1-3: BRT-05 熔断禁止开仓仅靠调用方自觉

**文件**: [engine/position_manager.py:56](engine/position_manager.py)

```python
# BRT-05: 熔断时禁止开仓（由调用方在调用前检查）
```

`PositionManager.calc_buy()` 自身不调用 `is_blocked()`，完全依赖 Workflow 调用方在调用前做风控检查。如果 DailyWorkflow 忘记检查，熔断期间仍可生成建仓指令。

**建议**: 在 `calc_buy()` 中接收一个可选的 `fuse_level` 参数并内部检查：
```python
def calc_buy(self, signal, ..., fuse_level=None):
    if fuse_level and self.risk_ctrl.is_blocked(fuse_level):
        return None
```

---

### P1-4: DailyWorkflow 未集成 RiskController 和 PositionManager

**文件**: [workflow/daily_workflow.py](workflow/daily_workflow.py) — M3 文件，M4 未更新

DailyWorkflow 的 Step 2（均线信号）检测到 REDUCE/EXIT 信号后，没有调用 `PositionManager.calc_sell()` 生成实际交易指令。Step 4（净值快照）也未读取 RiskController 的熔断状态。

---

## P2 — 中优建议

### P2-1: `main.py` 缺少 Position/Risk 相关的 CLI 测试入口

`--weekly`/`--daily`/`--monthly` 已覆盖 Workflow，但没有类似 `--risk-check` 的命令来手动测试 RiskController。

---

### P2-2: `calc_buy()` 仓位裁剪日志用 INFO 而非 WARNING

TC-4.3 预期："日志 WARNING：'总仓位将触及上限 70%，建仓比例从 15% 调整为 5%'"
**实际**: 使用 `logger.info()`。偏差影响不大但 TC 文档不一致。

---

### P2-3: MonthlyReport 接受 `sector_repo` 但从未使用

构造函数接收了 `sector_repo` 参数但 `generate()` 方法中从未被调用（按板块归因功能缺失）。徒增依赖。

---

## 逐 TC 通过性判定（数值验证 + 集成检查）

| 测试用例 | 数值计算 | 集成/持久化 | 最终 |
|:--------:|:------:|:---------:|:----:|
| TC-4.1 A级买点 | ✅ pct=15%, limit=50.25 | — | ✅ |
| TC-4.2 B级买点 | ✅ pct=9% | — | ✅ |
| TC-4.3 总仓上限裁剪 | ✅ 65%+15%→5% | — | ✅ |
| TC-4.4 单票上限裁剪 | ✅ room_single clip | — | ✅ |
| TC-4.5 减仓 MA10 | ✅ 25%→12.5% | — | ✅ |
| TC-4.6 清仓 MA21 | ✅ 25% MARKET | — | ✅ |
| TC-4.7 清仓退潮 | ❌ 统一 MARKET | — | ❌ P1-2 |
| TC-4.8 L1 -8%止损 | ✅ STOCK_STOP | ❌ P0-1 | ❌ |
| TC-4.9 L1 未触发 | ✅ NORMAL | — | ✅ |
| TC-4.10 L2 日回撤 | ✅ DAILY_BAN | ❌ P0-1 | ❌ |
| TC-4.11 L2 连续止损 | ✅ DAILY_BAN | ❌ P0-1 | ❌ |
| TC-4.12 L3 月回撤 | ✅ MONTHLY_BAN | ❌ P0-1 | ❌ |
| TC-4.13 Dashboard | — | ❌ P0-2 | ❌ |
| TC-4.14 月度报告 | ✅ 基础统计 | ❌ P0-3 | ❌ |
| BRT-01~08 | ✅ | ⚠️ P1-3 | ⚠️ |

**M4 门禁状态**: ❌ **不通过**（7 条 TC 不通过，8 条通过/条件通过）

---

## M4 任务完成度

| 编号 | 任务 | 状态 | 备注 |
|:----:|------|:--:|------|
| T4.1 | PositionManager | ✅ | 数值全部正确，裁剪逻辑完备 |
| T4.2 | OrderExecutor | ✅ | 生成格式化指令 |
| T4.3 | RiskController | ⚠️ | 数值正确，但不写 DB（P0-1） |
| T4.4 | Dashboard 数据聚合 | ❌ | fuse_level 未接入（P0-2） |
| T4.5 | Position/Risk Repository | ✅ | M2 已实现 |
| T4.6 | 价格轮询止损 | ❌ | P1-1 |
| T4.7 | MonthlyReport | ⚠️ | 基本可用，缺多个必需字段（P0-3） |

---

## 架构亮点

1. **PositionManager 裁剪逻辑完备** — 四层裁剪（total/single/sector/cash）顺序正确，每层有日志
2. **RiskController 数值回归正确** — 全部 6 个 TC 的数值代入验证通过（首次交付即零计算 bug）
3. **BRT-06 止损优先** — check_stock() 中浮亏判定在 MA 判定之前，符合"止损优先于均线信号"
4. **OrderExecutor 格式清晰** — 输出结构化 dict + 人类可读字符串，便于 M5 Web 集成

---

## 后续行动建议

1. **立即**：P0-1 RiskController 集成 RiskRepository；P0-2 Dashboard 读取 risk_event；P0-3 补充 MonthlyReport
2. **M4 收尾**：P1-1 ~ P1-4
3. **M5 启动条件**：P0 全部清零 + TC 通过率 ≥ 10/14

---

> 评审人：Claude (自动化代码审查)
> 下一节点：P0+P1 修复后复审
