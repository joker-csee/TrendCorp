# engine/scanner/rel_strength.py — 相对强度评分（vs 沪深300）


def calc_rel_strength(sector_ret_20d: float, hs300_ret_20d: float) -> float:
    """近 20 日板块涨幅 / 沪深 300 涨幅，映射到 0-1。

    板块跑赢大盘 50% 以上 → 1.0；板块涨幅不及大盘一半 → 0.0。
    大盘下跌但板块跌得更少 → 正向超额也得分。
    """
    if sector_ret_20d is None or hs300_ret_20d is None:
        return 0.0

    # 使用比值法：板块收益 / 指数收益，映射到 0-1
    if abs(hs300_ret_20d) < 0.001:
        # 指数几乎没动，板块涨就是超额
        return 1.0 if sector_ret_20d > 0.01 else 0.5 if sector_ret_20d > -0.01 else 0.0
    ratio = sector_ret_20d / hs300_ret_20d if hs300_ret_20d != 0 else 0.0
    if ratio >= 1.5:
        return 1.0
    if ratio <= 0.0:
        return 0.0
    return max(0.0, min(1.0, (ratio - 0.0) / 1.5))
