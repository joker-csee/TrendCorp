下面这份评审记录，我是按照**架构评审（Architecture Review）**的形式整理的，而不是代码 Review。评审原则以项目定位为前提：

> **定位：单用户、本地部署、长期个人维护、持续演进，不追求企业级架构。**

------

# 软件架构评审记录

**项目名称：** 趋势中军交易系统
**评审对象：** `SYSTEM_ARCHITECTURE.md`
**评审日期：** 2026-07-02
**评审角色：** 软件系统架构评审

------

# 一、总体结论

本架构已经能够作为个人交易系统 V1 的开发蓝图。

整体采用了"简单优先（Keep It Simple）"的设计理念，技术选型克制，模块边界清晰，没有为了追求所谓"企业级架构"而引入不必要的复杂度。

对于本项目"个人使用、长期维护、持续演进"这一目标而言，目前架构整体合理。

**总体评价：8.8 / 10**

------

# 二、架构优点

## 1、技术选型合理（★★★★★）

技术栈符合项目定位。

优点：

- Python 生态成熟
- FastAPI 足够轻量
- SQLite 满足长期单机数据存储
- APScheduler 满足定时任务
- HTMX + Jinja2 避免前后端分离复杂度

不存在明显的过度设计。

------

## 2、整体分层清晰（★★★★★）

当前系统已经形成完整的软件分层：

```text
Web
    │
Router
    │
Engine
    │
Repository
    │
SQLite
```

调度系统（Scheduler）与业务系统基本解耦。

整体结构容易理解。

------

## 3、模块职责明确（★★★★★）

Engine 层基本按照业务能力拆分：

- 主线扫描
- 主线确认
- 中军筛选
- 仓位管理
- 风控
- Dashboard

符合单一职责原则。

------

## 4、数据库设计优秀（★★★★★）

数据库采用 Snapshot 思路保存历史状态。

优点：

- 可回溯
- 可复盘
- 支持后续统计分析
- 支持参数优化

相比只保存当前状态的数据结构更加合理。

------

## 5、配置集中管理（★★★★★）

所有策略参数集中于 config.py。

优点：

- 参数统一
- 修改方便
- 后续支持 API 修改

避免魔法数字散落在代码中。

------

# 三、需要改进的问题

以下建议按照重要程度排序。

------

# A级（建议立即修改）

这些问题会直接影响未来维护成本。

------

## A-1 Engine 模块建议进一步拆分

### 当前情况

例如：

```text
engine/
    market_scanner.py
```

随着策略增加：

未来可能同时承担：

- MA计算
- 相对强度
- 资金评分
- 成交额评分
- 排名
- 综合评分

容易演化成大型模块。

### 建议

按评分维度拆分：

```text
engine/

scanner/

    trend.py

    strength.py

    fund.py

    echelon.py

    scanner.py
```

其中：

scanner.py

仅负责组织整个扫描流程。

### 必要性

★★★★★（最高）

原因：

这是未来最容易导致维护困难的问题。

------

## A-2 Repository 按领域拆分

### 当前情况

目前：

```text
repository.py
```

负责所有数据库访问。

未来：

Trade

Position

Snapshot

Sector

都会不断增加。

### 建议

拆成：

```text
repositories/

trade_repository.py

position_repository.py

sector_repository.py

snapshot_repository.py
```

### 必要性

★★★★★

原因：

避免 Repository 演化成几千行的大文件。

------

## A-3 增加日志系统

### 当前情况

目前没有明确日志设计。

### 建议

至少增加：

```text
logs/

app.log

scheduler.log

error.log
```

记录：

- Scheduler 是否执行
- 数据更新情况
- API异常
- SQLite异常

### 必要性

★★★★★

原因：

个人项目长期维护时，日志的重要性远高于复杂架构。

------

# B级（建议本阶段完成）

收益较高，但不会影响当前开发。

------

## B-1 增加 Workflow 层

### 当前情况

Scheduler 直接调用各 Engine。

例如：

```text
Scheduler

↓

MarketScanner

↓

ThemeSelector
```

### 建议

增加：

```text
workflow/

weekly_workflow.py

daily_workflow.py

monthly_workflow.py
```

例如：

```text
WeeklyWorkflow

↓

更新数据

↓

扫描板块

↓

确认主线

↓

筛选中军

↓

保存数据库

↓

生成提醒
```

Workflow 负责：

"今天要做哪些事情"

Engine 负责：

"每件事情如何计算"

### 必要性

★★★★☆

原因：

随着流程增加，可维护性会明显提升。

------

## B-2 DataFetcher 拆分 Provider

建议：

```text
providers/

market_provider.py

financial_provider.py

announcement_provider.py
```

以后数据源变化时，只修改对应 Provider。

### 必要性

★★★★☆

------

## B-3 API 返回结构统一

建议统一：

```json
{
    "success": true,
    "data": {},
    "message": ""
}
```

便于：

- HTMX
- Dashboard
- 错误处理

### 必要性

★★★★☆

------

## B-4 环境配置独立

建议增加：

```text
.env
```

保存：

- 数据库路径
- 日志路径
- 邮件配置

减少迁移电脑时修改代码。

### 必要性

★★★★☆

------

# C级（可以以后再做）

目前收益有限。

------

## C-1 Service Layer

当前：

```text
Router

↓

Engine
```

对于个人项目完全可以接受。

等系统复杂后再考虑。

### 必要性

★★☆☆☆

------

## C-2 Domain Model

例如：

```text
Trade

Portfolio

Sector

Stock
```

目前数据库已经承担了领域模型职责。

暂不需要增加复杂度。

### 必要性

★★☆☆☆

------

## C-3 Cache

SQLite + 数千条数据不是性能瓶颈。

暂时无需增加缓存。

### 必要性

★☆☆☆☆

------

## C-4 State Machine

当前 Scheduler 已经能够表达系统状态。

无需额外增加状态机。

### 必要性

★☆☆☆☆

------

# 四、不建议引入的内容

根据本项目定位，以下技术暂不建议考虑：

| 技术       | 建议        |
| ---------- | ----------- |
| Redis      | 不需要      |
| PostgreSQL | SQLite 足够 |
| Docker     | 不需要      |
| RabbitMQ   | 不需要      |
| Kafka      | 不需要      |
| 微服务     | 不需要      |
| DDD        | 不需要      |
| CQRS       | 不需要      |
| Event Bus  | 不需要      |

原因：

这些方案主要解决企业级部署、多人协作、高并发等问题，与本项目目标不匹配。

------

# 五、最终建议优先级

| 优先级 | 建议                              | 必要性   |
| ------ | --------------------------------- | -------- |
| ⭐⭐⭐⭐⭐  | Engine 拆小模块                   | 必须     |
| ⭐⭐⭐⭐⭐  | Repository 拆分                   | 必须     |
| ⭐⭐⭐⭐⭐  | 增加日志系统                      | 必须     |
| ⭐⭐⭐⭐☆  | 增加 Workflow 层                  | 强烈建议 |
| ⭐⭐⭐⭐☆  | DataFetcher 拆 Provider           | 建议     |
| ⭐⭐⭐⭐☆  | API 返回统一                      | 建议     |
| ⭐⭐⭐☆☆  | `.env` 配置                       | 建议     |
| ⭐⭐☆☆☆  | Service Layer                     | 可选     |
| ⭐⭐☆☆☆  | Domain Model                      | 可选     |
| ⭐☆☆☆☆  | Cache                             | 暂不需要 |
| ⭐☆☆☆☆  | State Machine                     | 暂不需要 |
| ☆☆☆☆☆  | Redis / Kafka / Docker / 微服务等 | 不建议   |

------

# 六、评审结论

本系统的软件架构设计与项目目标高度一致，坚持了"简单、可维护、持续演进"的原则，没有引入超出需求的企业级架构，整体设计合理，可作为 V1 开发基础。

后续演进建议以**控制模块规模**和**提升可维护性**为主，而不是增加新的技术栈。优先完成 **Engine 模块拆分、Repository 拆分、日志系统**以及 **Workflow 编排层**，即可支撑未来数年的持续迭代。在当前阶段，不建议引入微服务、消息队列、缓存中间件或复杂领域驱动设计，以保持系统的简单性和开发效率。