# engine/screener/ma_structure.py — 均线结构维度 (C-1)
import math


def calc_ma_structure_score(ma5: float, ma10: float, ma21: float, ma55: float) -> float:
    """均线多头排列评分。

    MA5 > MA10 > MA21 > MA55 全部满足 → 1.0
    仅前三项（MA5>MA10>MA21）→ 0.6
    仅 MA21 > MA55 → 0.3
    空头 → 0.0
    """
    def _gt(a, b):
        if a is None or b is None:
            return False
        if math.isnan(a) or math.isnan(b):
            return False
        return a > b

    all_multi = _gt(ma5, ma10) and _gt(ma10, ma21) and _gt(ma21, ma55)
    if all_multi:
        return 1.0
    short_multi = _gt(ma5, ma10) and _gt(ma10, ma21)
    if short_multi:
        return 0.6
    if _gt(ma21, ma55):
        return 0.3
    return 0.0
