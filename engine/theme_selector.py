# engine/theme_selector.py — B-2 主线确认器
import logging


class ThemeSelector:
    """在 Scanner 候选列表中，通过持续性验证确认主线。

    确认主线（≥3分）：进入中军筛选
    观察主线（2-2.99分）：保留观察，不筛选
    排除（<2分）：不保留
    """

    def __init__(self, confirmed_min: float = 3.0):
        self.confirmed_min = confirmed_min
        self.logger = logging.getLogger("app.selector")

    def confirm(self, scan_results: list) -> dict:
        """返回 {'confirmed': [...], 'watch': [...], 'excluded': [...]}"""
        confirmed, watch, excluded = [], [], []

        for r in scan_results:
            score = self._calc_confirmation(r)
            item = {**r.__dict__, "confirmation_score": score}
            if score >= self.confirmed_min:
                item["is_confirmed"] = 2
                confirmed.append(item)
            elif score >= 2.0:
                item["is_confirmed"] = 1
                watch.append(item)
            else:
                item["is_confirmed"] = 0
                excluded.append(item)

        self.logger.info(
            "主线确认: %d 确认 + %d 观察 + %d 排除",
            len(confirmed), len(watch), len(excluded),
        )
        return {"confirmed": confirmed, "watch": watch, "excluded": excluded}

    @staticmethod
    def _calc_confirmation(scan_result) -> float:
        """四项持续性验证，每项 1 分，满分 4 分。

        P0-1 修复：使用 getattr + 直接属性访问，对 M2 阶段无法获取
        真实数据的验证项标注为 FIXME(M3)，使用已知最佳的近似指标。
        """
        score = 0.0
        r = scan_result
        logger = logging.getLogger("app.selector")

        # 验证项 1: 已连续跑赢大盘 ≥ 3 周（用相对强度 > 0.7 近似）
        rs = r.rel_strength if hasattr(r, 'rel_strength') else None
        if rs is not None and rs >= 0.7:
            score += 1.0

        # 验证项 2: 有可辨识的产业逻辑（非纯题材）
        # FIXME(M3): M2 阶段无产业逻辑数据源（行业研报标签/分析师覆盖数），
        # 暂用趋势强度 + 资金流入双确认作为代理。趋势强度和资金同时 > 0.5
        # 时板块更可能具备基本面支撑而非纯炒作。
        ts = r.trend_score if hasattr(r, 'trend_score') else None
        fs = r.fund_score if hasattr(r, 'fund_score') else None
        if ts is not None and fs is not None and ts >= 0.5 and fs >= 0.5:
            score += 1.0
        elif ts is not None and fs is not None:
            logger.debug(
                "板块 %s 产业逻辑验证未通过: trend=%.2f fund=%.2f",
                getattr(r, 'sector_name', '?'), ts, fs,
            )

        # 验证项 3: 板块成交额近 5 日均量 / 近 20 日均量 < 2.5（非天量）
        vr = r.volume_ratio if hasattr(r, 'volume_ratio') else 1.0
        if vr is None:
            vr = 1.0
        if vr < 2.5:
            score += 1.0

        # 验证项 4: PE 分位 < 90%
        # FIXME(M3): M2 阶段 FinancialProvider 尚未实现 PE 历史分位查询。
        # 暂用梯队完整性 + 趋势强度双确认作为拥挤度代理：
        # echelon >= 0.5（有涨停活跃）同时趋势 strength 不过热（<0.95）
        # 过滤掉"过热但已失去梯队"的板块。
        es = r.echelon_score if hasattr(r, 'echelon_score') else None
        if es is not None and ts is not None and es >= 0.5 and ts < 0.95:
            score += 1.0
        elif es is not None and ts is not None:
            logger.debug(
                "板块 %s PE 分位验证未通过: echelon=%.2f trend=%.2f",
                getattr(r, 'sector_name', '?'), es, ts,
            )

        return round(score, 1)
