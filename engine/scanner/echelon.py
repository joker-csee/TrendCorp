# engine/scanner/echelon.py — 梯队完整性评分


def calc_echelon_score(limit_up_cnt: int, has_large_cap: bool) -> float:
    """涨停家数 + 大市值存在性。

    limit_up_cnt >= 3 得 0.5 分，has_large_cap=True 得 0.5 分。
    两项都满足 → 1.0；仅一项 → 0.5；零项 → 0.0。
    """
    if limit_up_cnt is None:
        limit_up_cnt = 0
    score = 0.0
    if limit_up_cnt >= 3:
        score += 0.5
    if has_large_cap:
        score += 0.5
    return score
