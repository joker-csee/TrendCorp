# engine/screener/vol_health.py — 量价健康度维度 (C-1)
def calc_vol_health_score(up_avg_vol: float, down_avg_vol: float,
                          pullback_vol: float, peak_vol: float) -> float:
    """量价关系评分。

    上涨放量（涨量/跌量 > 1.5）→ 0.5
    回调缩量（回调量/高峰量 < 0.5）→ 0.5
    """
    if up_avg_vol is None or down_avg_vol is None:
        return 0.0
    score = 0.0
    if down_avg_vol > 0 and up_avg_vol / down_avg_vol >= 1.5:
        score += 0.5
    if peak_vol is not None and peak_vol > 0 and pullback_vol is not None:
        if pullback_vol / peak_vol < 0.5:
            score += 0.5
    return score
