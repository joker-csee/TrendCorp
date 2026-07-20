# engine/screener/market_cap.py — 市值规模维度 (C-1)
def calc_market_cap_score(market_cap: float) -> float:
    """流通市值评分：100-500 亿最优 → 1.0；50-100 或 500-1000 → 0.6；其余 → 0.2。"""
    if market_cap is None:
        return 0.2
    if 100 <= market_cap <= 500:
        return 1.0
    if 50 <= market_cap < 100 or 500 < market_cap <= 1000:
        return 0.6
    return 0.2
