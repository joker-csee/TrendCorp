# engine/scanner/rel_strength.py — 相对强度评分（vs 沪深300）


def calc_rel_strength(sector_ret_20d: float, hs300_ret_20d: float) -> float:
    """近 20 日板块 vs 沪深 300 相对强度，映射到 0-1。

    P2-5 修复：当大盘和板块同跌时使用差值法（超额收益），
    避免比值法对"板块跌得少=有超额"奖励不足。
    """
    if sector_ret_20d is None or hs300_ret_20d is None:
        return 0.0

    excess = sector_ret_20d - hs300_ret_20d

    # 差值法：板块超额 8%+ → 1.0；超额 < -5% → 0.0
    if excess >= 0.08:
        return 1.0
    if excess <= -0.05:
        return 0.0
    # 线性映射：超额 -5%~+8% → 0.0~1.0
    return max(0.0, min(1.0, (excess + 0.05) / 0.13))
