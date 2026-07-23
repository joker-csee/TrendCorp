# M5 代码评审报告

> 评审日期：2026-07-23
> 评审范围：commit `028d575` "M5: Web 交付 — FastAPI 6页面 + Chart.js + 统一 APIResponse"
> 评审依据：PROJECT_PLAN.md 第九章 M5 测试用例 TC-5.1 ~ TC-5.13 + UAT-01~08
> 方法：逐行代码审查 + HTMX/JSON 交互路径分析 + 静态模板完整性检查

---

## 评审摘要

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **P0** | 4 | 阻断性缺陷 — HTMX/JSON 渲染断裂；Dashboard 持仓永不填充；缺关键 API 端点 |
| **P1** | 6 | 高优缺陷 — 页面功能缺失、全局错误处理缺失、模板静态占位 |
| **P2** | 4 | 中优建议 — JS 健壮性、代码组织、样式细节 |

**总体评价**：M5 的 FastAPI + Jinja2 + HTMX + Chart.js 技术栈选型正确，13 个 API 端点和 5 个 HTML 页面结构完整。但存在一个**贯穿性架构断裂**——所有数据 API 返回 JSON 格式，而 HTMX 的 `hx-get`/`hx-post` 直接将 JSON 文本渲染到 HTML 元素中，导致扫描/持仓/风控/报告页面显示原始 JSON 字符串而非格式化内容。此外，Dashboard 的持仓表（`#holdings-table`）在 Javascript 中无填充逻辑，永远显示"加载中…"。

---

## P0 — 阻断性缺陷

### P0-1: HTMX 数据端点返回 JSON 但未渲染为 HTML（4 个页面受影响）

**影响范围**:

| 页面 | HTMX 调用 | 目标元素 | 实际效果 |
|------|----------|---------|---------|
| `/scanner` | `GET /api/scanner/latest` | `#snapshot-table` | 表格显示原始 JSON |
| `/scanner` | `POST /api/workflow/scan` | `#scan-result` | 按钮区域显示 JSON |
| `/positions` | `GET /api/positions` | `#pos-table` | 表格显示 JSON |
| `/positions` | `GET /api/risk/status` | `#risk-events` | 表格显示 JSON |
| `/report` | `GET /api/report` | `#report-content` | 显示 JSON |

**问题**: HTMX 的 `hx-get` 期望服务器返回 **HTML 片段**（用于交换到目标 DOM 元素）。但所有 `/api/*` 端点返回的是 `APIResponse` JSON（`{success: true, data: [...]}`）。HTMX 会将这个 JSON 字符串原样插入 DOM，用户在页面上看到原始 JSON 文本。

**建议修复方案**（二选一）:
- **方案 A（服务端渲染）**: 为每个需要 HTMX 的页面创建对应的 HTML 片段模板，API 返回 `TemplateResponse` 渲染的 HTML
- **方案 B（客户端渲染）**: 在 `app.js` 中增加 JSON→HTML 的客户端渲染函数，使用 `hx-trigger` 的 `htmx:afterRequest` 事件拦截并渲染

**TC 影响**: TC-5.4 / 5.5 / 5.6 / 5.10 → 不通过

---

### P0-2: Dashboard 持仓表（`#holdings-table`）永不填充

**文件**: [web/static/app.js:7-33](web/static/app.js) — `fetchDashboard()` 函数

**代码分析**:
```javascript
// fetchDashboard() 只更新了:
//   nav-total, nav-daily, nav-weekly, nav-monthly, nav-pos, nav-cash
//   #fuse-indicator (熔断状态)
//   #signals-table (主线信号表)
// 但 #holdings-table 没有任何代码填充！
```

Dashboard 页面的 `#holdings-table` 从页面加载起就一直显示 `<tr><td colspan="6">加载中...</td></tr>`。`/api/positions` 端点存在且返回持仓数据，但 `fetchDashboard()` 从未调用它。

**TC 影响**: TC-5.3 持仓表项不通过

---

### P0-3: 缺 `/api/workflow/eod` 日终触发端点

**计划要求** (TC-3.8): "POST /api/workflow/scan + `/eod`"
**实际**: 只有 `POST /api/workflow/scan`，没有 `/api/workflow/eod`

日终 Workflow 只能通过 CLI `--daily` 触发，Web 用户无法触发日终更新。

---

### P0-4: 缺全局异常处理器 — 未预期异常返回非标准格式

**文件**: [web/router.py](web/router.py)

**问题**: 每个 API 端点都有 try/except，但如果异常发生在框架层（如请求体解析、路由匹配），FastAPI 返回默认 500 格式 `{"detail": "..."}` 而非 `APIResponse` 格式 `{"success": false, "message": "..."}`。TC-5.2 要求"HTTP 状态码仍为 200（异常信息在 body 中表达"），但 FastAPI 默认对未捕获异常返回 500。

**建议修复**:
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content=APIResponse.fail(message=str(exc)).model_dump(),
    )
```

---

## P1 — 高优缺陷

### P1-1: Journal 交易列表为静态占位

**文件**: [web/templates/journal.html:23](web/templates/journal.html)

```html
<tr><td colspan="5">M5 Web 阶段通过 /api/trade/log 录入</td></tr>
```

`<tbody>` 中没有 HTMX 动态加载或 JS 填充逻辑。交易日志页面永远显示这条静态消息，不会展示实际交易记录。`TradeRepository.get_all()` 已有数据但从未被前端调用。

---

### P1-2: 缺平仓 API 端点和 UI

**计划要求** (TC-5.9): 平仓表单（平仓日期/价格/原因/复盘/合规复选框）
**实际**: 完全没有平仓相关 API（无 `PUT /api/trade/close` 或类似端点），journal.html 也无平仓表单。

---

### P1-3: Positions 页面缺"开仓按钮"且表格字段不全

**计划要求** (TC-5.6): 每只持仓显示 "代码+名称 / 持仓占比+成本价+现价 / 浮动盈亏(金额+百分比) / 当前信号(A_BUY/HOLD/REDUCE/EXIT) / MA10 状态 / 板块退潮预警等级"
**实际**: 表格只有 `ID/成本/占比/MA10/MA21/预警` 6 列，缺代码、名称、现价、浮盈、信号等关键字段。且无"开仓按钮被禁用"逻辑。

---

### P1-4: 无 Chart.js 实例销毁 — 重复加载会叠加 Canvas

**文件**: [web/static/app.js:35-48](web/static/app.js)

```javascript
new Chart(document.getElementById('navChart'), { ... });
```

每次调用 `fetchNavHistory()`（如 HTMX 局部刷新导航后 DOMContentLoaded 重复触发）都会创建新 Chart 实例，旧 Canvas 上的 Chart 不被销毁，导致内存泄漏。

**建议**: 创建前检查并销毁已有实例：
```javascript
const canvas = document.getElementById('navChart');
Chart.getChart(canvas)?.destroy();
new Chart(canvas, { ... });
```

---

### P1-5: `serve()` 中 `from apscheduler.schedulers.background` 可能导致模块缺失

`apscheduler` 在 `requirements.txt` 中正确声明，但 `BackgroundScheduler` 的位置在 `apscheduler.schedulers.background`（注意 `schedulers` 而非 `scheduler`）。如果包版本有变化可能找不到。

---

### P1-6: `/api/workflow/scan` 结果未返回扫描统计

**计划要求** (TC-5.4): "扫描完成后，页面局部刷新，显示新的扫描结果"
**当前**: `api_workflow_scan` 返回 `APIResponse.ok(message="周度扫描完成")`，无 `data` 字段。前端无法知道扫描了多少板块、确认了几条主线。`#scan-result` 只会显示 JSON `{"success": true, "data": null, "message": "周度扫描完成"}`。

---

## P2 — 中优建议

### P2-1: `serve()` 函数过大（~100 行）

main.py 的 `serve()` 函数同时包含配置、日志、DB 初始化、组件创建、FastAPI 构建、Scheduler 注册。建议拆分为 `_build_app()` 工厂函数。

---

### P2-2: 5 个原始 JSON API 无调用方消费

`/api/scanner/latest`、`/api/positions`、`/api/risk/status`、`/api/report`、`/api/nav/history` 这 5 个 API 返回正确 JSON，但前端没有正确的消费者（要么 HTMX 渲染断裂如 P0-1，要么无 JS 调用如 P0-2）。API 层本身正确但前后端未对接。

---

### P2-3: Router 使用 `request.app.state.*` 访问组件

这种模式耦合了路由到应用状态。M4 的 PositionManager、RiskController 未通过 `create_engines()` 注入到 `app.state`（如 `position_mgr`、`risk_ctrl`），若路由需要调用它们会找不到。

---

### P2-4: `app.state.risk_repo` 在 `serve()` line 142 手动注入

```python
engines["risk_ctrl"].risk_repo = repos["risk_repo"]
```

这是在 `create_engines()` 之后的手动修补。应该在 `create_engines()` 工厂中直接注入，避免组件在创建时状态不完整。

---

## 逐 TC 通过性判定

| 测试用例 | 判定 | 阻断项 |
|:--------:|:----:|--------|
| **TC-5.1** APIResponse 正常 | ✅ | 格式正确 |
| **TC-5.2** APIResponse 异常 | ⚠️ | P0-4：未预期异常返回非标准格式 |
| **TC-5.3** Dashboard 页面 | ❌ | P0-2：持仓表不填充 |
| **TC-5.4** Scanner 显示主线 | ❌ | P0-1：JSON 渲染断裂 |
| **TC-5.5** Scanner 手动触发 | ❌ | P0-1：JSON 渲染断裂 + P1-6：无扫描统计 |
| **TC-5.6** Positions 页面 | ❌ | P0-1：JSON 渲染 + P1-3：字段不全 |
| **TC-5.7** Journal 交易列表 | ❌ | P1-1：静态占位 |
| **TC-5.8** Journal 录入交易 | ⚠️ | 表单正确但 JSON 渲染至 HTML |
| **TC-5.9** Journal 平仓录入 | ❌ | P1-2：完全缺失 |
| **TC-5.10** Report 页面 | ❌ | P0-1：JSON 渲染断裂 |
| **TC-5.11** 全流程端到端 | — | 网络环境不可测 |
| **TC-5.12** 数据源不可用 | ✅ | `/api/dashboard` 有 try/except RuntimeError |
| **TC-5.13** SQLite 写入失败 | — | 环境不可测 |
| **UAT-01~08** | ❌ | 全部因 P0-1/P0-2 受阻 |

**M5 门禁状态**: ❌ **不通过**（8 条 TC 不通过，2 条条件通过，仅 3 条完全通过）

---

## M5 任务完成度

| 编号 | 任务 | 状态 | 备注 |
|:----:|------|:--:|------|
| T5.1 | schemas.py | ✅ | APIResponse 模型完整 |
| T5.2 | router.py | ✅ | 6 页面 + 10 API 全部定义 |
| T5.3 | base.html | ✅ | 导航、熔断指示器 |
| T5.4 | dashboard.html | ⚠️ | 结构正确，P0-2 持仓不填充 |
| T5.5 | scanner.html | ⚠️ | 结构正确，P0-1 渲染断裂 |
| T5.6 | positions.html | ⚠️ | 字段不全 + P0-1 |
| T5.7 | journal.html | ⚠️ | 表单正确，P1-1 列表静态 |
| T5.8 | report.html | ⚠️ | P0-1 渲染断裂 |
| T5.9 | static/ 样式+交互 | ⚠️ | Chart.js 正常，HTMX 接线断裂 |
| T5.10 | 端到端联调 | ❌ | 未调通 |

---

## 架构亮点

1. **APIResponse 统一格式** — `ok()`/`fail()` 工厂方法干净，时间戳自动生成
2. **Chart.js 净值曲线** — 正确绘制 90 天历史，配色专业
3. **风控状态指示器** — 三色（绿/橙/红）CSS class 切换正确
4. **HTMX 局部刷新** — `every 60s` 自动刷新持仓、`hx-trigger="load"` 初始加载模式正确
5. **页面分离清晰** — 5 个模板各司其职，base.html 提供公共导航

---

## 后续行动建议

1. **立即**: P0-1 修复（JSON→HTML 渲染）— 推荐方案 A（服务端模板片段），影响面最大
2. **M5 收尾**: P0-2（填充持仓表）+ P0-3（补 `/api/workflow/eod`）+ P0-4（全局异常处理）
3. **P1 补充**: 平仓 API、Journal 动态列表、Positions 字段完善
4. **端到端验证**: 修复后在真实网络环境跑 TC-5.11 全流程

---

> 评审人：Claude (自动化代码审查)
> 下一节点：P0+P1 修复后复审
