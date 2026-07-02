# 架构评审回复记录

> 评审来源：`SYSTEM_ARCHITECTURE_REVIEW.md`
> 回复日期：2026-07-02
> 原则：逐条评审，明确采纳/拒绝，给出理由，不回避批评

---

## 总体回应

评审意见质量很高。评审人准确理解了项目定位（单用户、本地、个人长期维护），在此基础上提出的改进建议都精准指向了 **"未来三年持续迭代时，什么东西会最先变成维护噩梦"** 这个核心问题。

评分 8.8/10 公允。以下逐条回复。

---

# A 级建议（建议立即修改）

---

## A-1 Engine 模块按评分维度拆分为子目录

> 评审建议：将 `market_scanner.py` 拆分为 `scanner/trend.py`、`scanner/strength.py`、`scanner/fund.py`、`scanner/echelon.py`、`scanner/scanner.py`

**决策：采纳。**

**理由**：

评审人指出了我设计中的一个盲区——我对"避免过度设计"理解过于机械，把"简单"等同于"文件少"。但真正的问题不是文件数量，而是**单个文件的变更原因是否唯一**。

当前 `market_scanner.py` 承担了四个维度的计算逻辑。未来任何一维的公式调整（比如趋势强度从"统计 MA 排列"改成"计算 MA 斜率"），都需要修改这个文件——四个维度的修改全部耦合在同一个文件里。这就是"变更原因不唯一"的典型反模式。

评审人建议的拆分方向正确：每个维度一个文件，`scanner.py` 只做流程编排。这样：
- 修改趋势强度公式 → 只改 `trend.py`，不影响其他维度
- 增加新的评分维度 → 加一个新文件，不改现有文件
- 单元测试可以按维度独立编写

**同样适用于 `core_screener.py`**：五维评分模型也应拆分为 `screener/` 子目录。

**修改计划**：

```
engine/
├── scanner/                  # 原 market_scanner.py 拆分
│   ├── __init__.py
│   ├── trend.py              # B-1 趋势强度评分
│   ├── rel_strength.py       # B-1 相对强度评分
│   ├── fund_flow.py          # B-1 资金确认评分
│   ├── echelon.py            # B-1 梯队完整性评分
│   └── scanner.py            # B-1 流程编排（组装四个维度）
│
├── screener/                 # 原 core_screener.py 拆分
│   ├── __init__.py
│   ├── market_cap.py         # C-1 市值规模维度
│   ├── liquidity.py          # C-1 流动性维度
│   ├── ma_structure.py       # C-1 均线结构维度
│   ├── vol_health.py         # C-1 量价健康度维度
│   ├── fundamental.py        # C-1 基本面质量维度
│   └── screener.py           # C-1 流程编排
│
├── theme_selector.py         # B-2 主线确认器（保持不变，逻辑简单）
├── theme_monitor.py          # B-3 主线退潮预警器（保持不变）
├── ma_monitor.py             # C-2 均线状态监控器（保持不变）
├── position_manager.py       # D-1 仓位管理器（保持不变）
├── order_executor.py         # D-2 订单执行器（保持不变）
├── risk_controller.py        # E-1 三级熔断器（保持不变）
└── dashboard.py              # E-2 仪表盘数据聚合（保持不变）
```

---

## A-2 Repository 按领域拆分

> 评审建议：将 `repository.py` 拆分为 `trade_repository.py`、`position_repository.py`、`sector_repository.py`、`snapshot_repository.py`

**决策：采纳。**

**理由**：

评审人指出"避免演化成几千行的大文件"——这个预判是对的。当前 9 张表，每张表的 CRUD + 查询方法 → 如果全放在一个文件，200 行起步，随功能增加轻松突破 1000 行。

按领域拆分后：
- 每个 Repository 文件只负责一张或一组相关表
- 修改某张表的查询逻辑 → 只影响对应的 Repository 文件
- 和 A-1 的 Engine 拆分形成呼应——Engine 不直接操作 SQL，而是通过对应的 Repository

**修改计划**：

```
data/
├── fetcher.py                # akshare 封装（不变）
├── schema.sql                # 建表语句（不变）
└── repositories/             # 原 repository.py 拆分
    ├── __init__.py
    ├── sector_repository.py          # sector + sector_snapshot
    ├── stock_repository.py           # stock
    ├── core_score_repository.py      # core_score_snapshot
    ├── trade_repository.py           # trade
    ├── position_repository.py        # position
    ├── risk_repository.py            # risk_event
    └── nav_repository.py             # nav_snapshot
```

---

## A-3 增加日志系统

> 评审建议：增加 `logs/app.log`、`logs/scheduler.log`、`logs/error.log`

**决策：采纳。**

**理由**：

这是我的一个明确遗漏。评审人说得对——"个人项目长期维护时，日志的重要性远高于复杂架构。"

对于这个系统，日志的价值体现在几个关键场景：
- **周日 18:00 的定时扫描有没有跑？** 如果某周没跑，你下周才发现，中间一周你用的是过期信号。
- **akshare 数据拉取失败的原因是什么？** 是网络问题、接口限流、还是 akshare API 变了？
- **复盘时想回溯**"3 个月前那笔亏损交易发生前，系统给的是什么信号？"——没有日志，只能靠记忆。

**我是如何在原设计中遗漏这个的**：因为设计时脑中跑的是"一切都正常运行"的路径。日志系统不在"正常路径"里，但它恰恰是系统出问题时唯一能依赖的东西。

**修改计划**：

使用 Python 标准库 `logging`（不引入第三方库），按 `config.py` 中的路径配置：

```
logs/
├── app.log           # INFO 及以上，记录所有 Engine 执行、数据更新、信号生成
├── scheduler.log     # 定时任务启动/完成/异常，独立文件便于排查
├── error.log         # ERROR 及以上，集中所有异常 + 完整堆栈
```

配置原则：
- 日志格式统一：`[时间] [级别] [模块] 消息`
- `app.log` 按 30 天滚动（个人项目不需要按天滚动）
- 不记录行情数据本身（那在 SQLite 里），只记录"数据拉取成功/失败，N 条"
- 不引入 loguru 等第三方库——`logging` 标准库足够

---

# B 级建议（建议本阶段完成）

---

## B-1 增加 Workflow 编排层

> 评审建议：增加 `workflow/weekly_workflow.py`、`daily_workflow.py`、`monthly_workflow.py`，将流程编排从 Scheduler 中分离出来

**决策：采纳。**

**理由**：

这是本次评审中架构层面最有价值的建议。

当前设计的问题：Scheduler（"什么时候做"）和 Engine 调用顺序（"按什么顺序做"）混在一起。短期没问题，但未来会出现两个痛点：

1. **手动触发和定时触发需要执行相同的流程**——如果编排逻辑写在 Scheduler 里，手动触发时需要复制一遍。
2. **流程步骤增加时**——比如未来可能想在"扫描板块"之后、"确认主线"之前，加一个"人工确认"步骤——如果编排在 Scheduler 里，需要改 Scheduler 的 cron 配置和步骤顺序，两个关注点搅在一起。

Workflow 层解决的就是**"编排逻辑与调度逻辑的分离"**：
- Scheduler 只管：现在是不是周日 18:00？是 → 触发 `weekly_workflow.run()`
- Workflow 只管：跑扫描 → 跑确认 → 跑筛选 → 存库 → 发提醒
- Engine 只管：每个步骤怎么算

**修改计划**：

```
workflow/
├── __init__.py
├── base.py               # Workflow 基类（日志记录开始/结束/耗时/异常）
├── weekly_workflow.py    # 周日：更新数据 → 扫描板块 → 确认主线 → 筛选中军 → 存库
├── daily_workflow.py     # 日终：更新行情 → 检查均线 → 退潮预警 → 生成信号
└── monthly_workflow.py   # 月末：生成月报 → 归档快照
```

Scheduler 简化为：

```python
scheduler.add_job(weekly_workflow.run,   trigger='cron', day_of_week='sun', hour=18)
scheduler.add_job(daily_workflow.run,    trigger='cron', day_of_week='mon-fri', hour=15, minute=30)
scheduler.add_job(monthly_workflow.run,  trigger='cron', day='last', hour=16)
```

手动触发时（通过 API）：Router 直接调用 `weekly_workflow.run()`，不经过 Scheduler。

---

## B-2 DataFetcher 拆分为 Provider

> 评审建议：拆分为 `market_provider.py`、`financial_provider.py`、`announcement_provider.py`

**决策：采纳。**

**理由**：

当前一个 `DataFetcher` 类混合了行情、财务、公告三类数据源。三类数据有本质区别：

| 数据类 | 更新频率 | 数据源 | 失败处理 |
|--------|---------|--------|---------|
| 行情 | 每日 | akshare 东方财富接口 | 可用前一日数据降级 |
| 财务 | 每季 | akshare 财报接口 | 无法降级，需告警 |
| 公告 | 实时 | 巨潮/东方财富公告 | 拉不到就跳过当天 |

放在一个类里意味着所有方法的错误处理逻辑必须兼容这三种场景，导致代码越来越臃肿。

拆分后，每个 Provider 可以有自己的重试策略、降级逻辑和日志输出。未来如果 akshare 的行情接口变了，只改 `market_provider.py`，不影响财务和公告的拉取。

**修改计划**：

```
data/
├── schema.sql
└── providers/
    ├── __init__.py
    ├── base.py                 # Provider 基类（统一日志、重试）
    ├── market_provider.py      # 板块/个股日K、均线、资金流、成交额
    ├── financial_provider.py   # 营收增速、净利润增速、ROE、毛利率
    └── announcement_provider.py # 业绩预告、重大合同、分析师覆盖
```

引擎层不再直接 import akshare——所有数据访问通过 Provider。

---

## B-3 API 返回结构统一

> 评审建议：统一 `{ "success": true, "data": {}, "message": "" }` 格式

**决策：采纳。**

**理由**：

没什么争议，标准做法。原设计中 API 路由只列了路径和返回内容描述，没有定义统一的 Response 结构——这是一个实实在在的遗漏。

统一格式后：
- 前端 HTMX 的错误处理只需写一次
- 前端可以统一处理"success=false"的情况（弹错误提示、禁用操作按钮等）
- API 文档（FastAPI 自动生成）更清晰

**修改计划**：

```python
# web/schemas.py
from pydantic import BaseModel
from typing import Any

class APIResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str = ""
    timestamp: str  # ISO 8601

# 使用示例
@router.get("/api/dashboard/summary", response_model=APIResponse)
async def dashboard_summary():
    try:
        data = dashboard_service.get_summary()
        return APIResponse(success=True, data=data, message="ok")
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return APIResponse(success=False, message=str(e))
```

---

## B-4 环境配置独立为 .env

> 评审建议：增加 `.env` 文件保存数据库路径、日志路径等

**决策：采纳。**

**理由**：

理由充分。"换一台电脑不用改代码"这个场景在个人项目中确实存在——换笔记本、重装系统、或者只是想换个数据存放目录。

`.env` 方案是 Python 生态最小的环境配置方案（`python-dotenv`），无需额外基础设施。

**修改计划**：

```
TrendCorp/
├── .env.example             # 提交到 git，列出所有配置项和默认值
├── .env                     # 不提交 git（加入 .gitignore）
```

`.env.example` 内容：

```bash
# 数据库路径
DATABASE_PATH=data/trend_corp.db

# 日志路径
LOG_DIR=logs
LOG_LEVEL=INFO

# 初始本金（元）
INITIAL_CAPITAL=100000

# 数据缓存目录（akshare 下载的临时文件）
DATA_CACHE_DIR=data/cache
```

`config.py` 改为从 `.env` 读取，同时保留代码中的硬编码默认值（`.env` 不存在时用默认值启动）。

---

# C 级建议（可以以后再做）

---

## C-1 Service Layer

> 评审建议：在 Router 和 Engine 之间增加 Service 层

**决策：暂不采纳，观察演进。**

**理由**：

评审人也标注了必要性仅 ★★☆☆☆。当前 Router → Engine 的直接调用已经够用。当出现以下信号时再引入 Service 层：
- 同一个业务逻辑被多个 Router 重复调用
- 需要在一个请求中编排多个 Engine 的调用结果
- 需要对 Engine 输出做缓存或转换

目前都不满足。同意"等系统复杂后再考虑"。

---

## C-2 Domain Model

> 评审建议：提取 Trade/Portfolio/Sector/Stock 领域模型

**决策：暂不采纳。**

**理由**：

评审人自己也指出"数据库已经承担了领域模型职责"。对于个人项目，引入独立的 Domain Model 层意味着每张表要写对应的 Python 类、序列化/反序列化逻辑——增加大量样板代码，但当前阶段没有实际收益。SQLite 的行 → Python dict/dataclass 已经足够。

---

## C-3 Cache

**决策：暂不采纳。** 同意评审人判断——几千条数据对 SQLite 不是瓶颈。等出现"Dashboard 加载超过 2 秒"再来处理。

---

## C-4 State Machine

**决策：暂不采纳。** 同意——Scheduler + FuseLevel 枚举已经足够表达系统状态。

---

## 四、不建议引入的内容（全部同意）

| 技术 | 评审建议 | 我的态度 |
|------|---------|---------|
| Redis | 不需要 | ✅ 同意。单用户 + 单进程，Python dict 缓存足够 |
| PostgreSQL | SQLite 足够 | ✅ 同意。单机几万条数据，SQLite 绰绰有余 |
| Docker | 不需要 | ✅ 同意。目标用户不需要 Docker，`python main.py` 就行 |
| RabbitMQ / Kafka | 不需要 | ✅ 同意。没有多进程/多服务通信需求 |
| 微服务 | 不需要 | ✅ 同意。反模式，单进程是最优架构 |
| DDD / CQRS / Event Bus | 不需要 | ✅ 同意。这些解决的是团队协作和复杂业务问题，个人项目不需要 |

---

# 修订后的项目结构

```
TrendCorp/
├── main.py
├── config.py
├── .env.example
├── .env                           # gitignore
├── requirements.txt
│
├── data/
│   ├── schema.sql
│   └── providers/
│       ├── base.py
│       ├── market_provider.py
│       ├── financial_provider.py
│       └── announcement_provider.py
│
├── engine/
│   ├── scanner/                   # ← A-1 拆分
│   │   ├── trend.py
│   │   ├── rel_strength.py
│   │   ├── fund_flow.py
│   │   ├── echelon.py
│   │   └── scanner.py
│   ├── screener/                  # ← A-1 拆分
│   │   ├── market_cap.py
│   │   ├── liquidity.py
│   │   ├── ma_structure.py
│   │   ├── vol_health.py
│   │   ├── fundamental.py
│   │   └── screener.py
│   ├── theme_selector.py
│   ├── theme_monitor.py
│   ├── ma_monitor.py
│   ├── position_manager.py
│   ├── order_executor.py
│   ├── risk_controller.py
│   └── dashboard.py
│
├── repositories/                  # ← A-2 拆分
│   ├── sector_repository.py
│   ├── stock_repository.py
│   ├── core_score_repository.py
│   ├── trade_repository.py
│   ├── position_repository.py
│   ├── risk_repository.py
│   └── nav_repository.py
│
├── workflow/                      # ← B-1 新增
│   ├── base.py
│   ├── weekly_workflow.py
│   ├── daily_workflow.py
│   └── monthly_workflow.py
│
├── journal/
│   ├── trade_logger.py
│   ├── monthly_report.py
│   └── param_tuner.py
│
├── scheduler/
│   └── jobs.py
│
├── web/
│   ├── router.py
│   ├── schemas.py                 # ← B-3 新增（APIResponse）
│   ├── templates/                 # 6 个 Jinja2 模板
│   └── static/
│       ├── style.css
│       └── app.js
│
├── logs/                          # ← A-3 新增
│   ├── .gitkeep
│   ├── app.log
│   ├── scheduler.log
│   └── error.log
│
└── tests/
    ├── test_scanner/
    ├── test_screener/
    └── test_risk.py
```

---

# 实施优先级

| 优先级 | 修改项 | 改动量 | 是否阻塞 V0.1 |
|--------|--------|--------|:----:|
| 🔴 立即 | A-1 Engine 拆分 | 中（拆分两个子目录） | 否，但建议 V0.1 之前做 |
| 🔴 立即 | A-2 Repository 拆分 | 中（创建 7 个文件） | 否 |
| 🔴 立即 | A-3 日志系统 | 小（logging 标准库） | **是**——没日志没法调试 |
| 🟡 V0.2 | B-1 Workflow 层 | 中（3 个 workflow 文件） | 否 |
| 🟡 V0.2 | B-2 Provider 拆分 | 中（3 个 provider 文件） | 否 |
| 🟢 V0.3 | B-3 API 统一 | 小（一个 schema 类） | 否 |
| 🟢 V0.3 | B-4 .env 配置 | 小（python-dotenv） | 否 |
| ⏸️ 观察 | C-1~C-4 | — | 否 |

---

# 结语

评审人准确地抓住了原设计中"从 V1 演进到 V3 时最容易出问题"的三个点：**单文件膨胀（A-1/A-2）、不可观测性（A-3）、流程耦合（B-1）**。这些都不是 V1 能不能跑起来的问题——V1 原设计照跑不误。但它们是未来"加一个功能要改三个文件、出错了不知道从哪查、流程一复杂 Scheduler 代码就失控"的根因。

全部 A 级和 B 级建议都已采纳。修订后的项目结构已更新到上方。感谢评审。
