# engine/scanner/trend.py — 趋势强度评分（MA 排列）
import logging
import math


def calc_trend_score(ma5: float, ma10: float, ma21: float, ma55: float) -> float:
    """MA5 > MA10 > MA21 > MA55，每满足一级 +0.25。MA5 > MA55 长期确认 +0.25。

    返回 0-1 的浮点数。NaN 输入记录 WARNING 并返回 0.0。
    """
    logger = logging.getLogger("app.scanner")

    vals = {"ma5": ma5, "ma10": ma10, "ma21": ma21, "ma55": ma55}
    nan_fields = [
        k for k, v in vals.items()
        if v is not None and isinstance(v, float) and math.isnan(v)
    ]
    if nan_fields:
        logger.warning(
            "趋势强度输入包含 NaN: %s，返回 0.0", nan_fields
        )
        return 0.0

    def _gt(a, b):
        if a is None or b is None:
            return False
        if math.isnan(a) or math.isnan(b):
            return False
        return a > b

    score = 0.0
    if _gt(ma5, ma10):
        score += 0.25
    if _gt(ma10, ma21):
        score += 0.25
    if _gt(ma21, ma55):
        score += 0.25
    if _gt(ma5, ma55):
        score += 0.25
    return score
