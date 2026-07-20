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
        """四项持续性验证，每项 1 分，满分 4 分。"""
        score = 0.0
        r = scan_result

        # 连续跑赢 ≥ 3 周（用相对强度 > 0.7 近似）
        if (getattr(r, 'rel_strength', None) or 0) >= 0.7:
            score += 1.0

        # 有可辨识的产业逻辑（用趋势强度 > 0.5 近似）
        if (getattr(r, 'trend_score', None) or 0) >= 0.5:
            score += 1.0

        # 非天量（volume_ratio < 2.5，None 视为正常）
        vr = getattr(r, 'volume_ratio', None) or 1.0
        if vr < 2.5:
            score += 1.0

        # PE 分位 < 90%（用梯队完整性 > 0 近似）
        if (getattr(r, 'echelon_score', None) or 0) >= 0.5:
            score += 1.0

        return round(score, 1)
