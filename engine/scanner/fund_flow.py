# engine/scanner/fund_flow.py — 资金确认评分


def calc_fund_score(net_inflow_5d: float, volume_ratio: float) -> float:
    """资金净流入 + 成交额占比确认。

    net_inflow_5d > 0 得 0.5 分，volume_ratio >= 1 得 0.5 分。
    两项都满足 → 1.0；仅一项 → 0.5；零项 → 0.0。
    """
    score = 0.0
    if net_inflow_5d is not None and net_inflow_5d > 0:
        score += 0.5
    if volume_ratio is not None and volume_ratio >= 1.0:
        score += 0.5
    return score
