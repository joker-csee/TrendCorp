# engine/screener/fundamental.py — 基本面质量维度 (C-1)
def calc_fundamental_score(revenue_yoy: float, profit_yoy: float) -> float:
    """营收回正 + 利润回正评分。各 0.5 分。"""
    if revenue_yoy is None and profit_yoy is None:
        return 0.0
    score = 0.0
    if revenue_yoy is not None and revenue_yoy > 0:
        score += 0.5
    if profit_yoy is not None and profit_yoy > 0:
        score += 0.5
    return score
