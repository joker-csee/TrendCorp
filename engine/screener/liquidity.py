# engine/screener/liquidity.py — 流动性维度 (C-1)
def calc_liquidity_score(rank_in_sector: int) -> float:
    """成交额在板块内排名评分：前5 → 1.0；6-10 → 0.5；>10 → 0.1。"""
    if rank_in_sector is None:
        return 0.1
    if rank_in_sector <= 5:
        return 1.0
    if rank_in_sector <= 10:
        return 0.5
    return 0.1
