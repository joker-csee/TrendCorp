# engine/scanner/trend.py — 趋势强度评分（MA 排列）
import math


def calc_trend_score(ma5: float, ma10: float, ma21: float, ma55: float) -> float:
    """MA5 > MA10 > MA21 > MA55，每满足一级 +0.25。

    返回 0-1 的浮点数。NaN 视为不满足。
    """
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
    if _gt(ma5, ma55):       # 长期趋势方向确认
        score += 0.25
    return score
