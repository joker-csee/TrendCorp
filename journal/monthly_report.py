# journal/monthly_report.py — F-2 月度绩效归因
import logging
from datetime import date


class MonthlyReport:
    """F-2: 月度绩效统计 + 按板块/买点归因。"""

    def __init__(self, trade_repo, nav_repo, sector_repo=None,
                 stock_repo=None):
        self.trade_repo = trade_repo
        self.nav_repo = nav_repo
        self.sector_repo = sector_repo
        self.stock_repo = stock_repo
        self.logger = logging.getLogger("app.monthly_report")

    def generate(self, year: int = None, month: int = None) -> dict:
        if year is None:
            year = date.today().year
        if month is None:
            month = date.today().month

        prefix = f"{year}-{month:02d}"
        trades = self._get_month_trades(year, month)

        # 基础统计
        closed = [t for t in trades if t.get("close_date")]
        wins = [t for t in closed if (t.get("pnl_pct") or 0) > 0]
        losses = [t for t in closed if (t.get("pnl_pct") or 0) <= 0]
        returns = [t.get("pnl_pct") or 0 for t in closed]

        # P0-3: max_single_win / max_single_loss / avg_win_loss_ratio
        max_win = max((t.get("pnl_pct") or 0) for t in closed) if closed else 0
        max_loss = min((t.get("pnl_pct") or 0) for t in closed) if closed else 0

        avg_win = (
            sum(t.get("pnl_pct") or 0 for t in wins) / len(wins)
            if wins else 0
        )
        avg_loss = (
            abs(sum(t.get("pnl_pct") or 0 for t in losses) / len(losses))
            if losses else 0
        )
        win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

        # P0-3: 按板块归因
        by_sector = self._attribution_by_sector(closed)

        # P0-3: 按买点类型归因
        by_signal = self._attribution_by_signal(closed)

        # 净值
        nav_history = self.nav_repo.get_history(31)
        monthly_ret = None
        if len(nav_history) >= 2:
            first = nav_history[0]["total_value"]
            last = nav_history[-1]["total_value"]
            if first > 0:
                monthly_ret = round((last - first) / first, 4)

        # 违规
        violations = sum(
            1 for t in trades if t.get("rule_compliant") == 0
        )

        report = {
            "year": year, "month": month,
            "trade_count": len(closed),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "avg_return": round(sum(returns) / len(returns) * 100, 2) if returns else 0,
            "max_single_win_pct": round(max_win * 100, 2),
            "max_single_loss_pct": round(max_loss * 100, 2),
            "avg_win_loss_ratio": win_loss_ratio,
            "by_sector": by_sector,
            "by_signal": by_signal,
            "monthly_return": round((monthly_ret or 0) * 100, 2),
            "violation_count": violations,
            "summary": self._summarize(
                len(closed), len(wins), returns, monthly_ret, violations,
                by_sector, win_loss_ratio,
            ),
        }

        self.logger.info(
            "月度报告 %d-%02d: %d笔 胜率%.1f%% 月收益%+.2f%% 违规%d次",
            year, month, report["trade_count"], report["win_rate"],
            report["monthly_return"], violations,
        )
        return report

    def _get_month_trades(self, year, month):
        prefix = f"{year}-{month:02d}"
        try:
            all_trades = self.trade_repo.get_all(limit=500)
            return [
                t for t in all_trades
                if (t.get("open_date") or "").startswith(prefix)
            ]
        except Exception:
            return []

    def _attribution_by_sector(self, closed) -> list[dict]:
        """P0-3: 按板块归因。"""
        by_sec = {}
        for t in closed:
            sid = t.get("sector_id")
            key = str(sid) if sid else "unknown"
            by_sec.setdefault(key, {"sector_id": sid, "count": 0, "pnl_sum": 0.0})
            by_sec[key]["count"] += 1
            by_sec[key]["pnl_sum"] += (t.get("pnl_pct") or 0) * 100
        return sorted(by_sec.values(), key=lambda x: x["pnl_sum"], reverse=True)

    def _attribution_by_signal(self, closed) -> dict:
        """P0-3: 按买点类型归因。"""
        by_sig = {}
        for t in closed:
            reason = t.get("open_reason", "unknown")
            key = "A级" if "A_MA10" in reason else "B级" if "B_SECTOR" in reason else reason
            by_sig.setdefault(key, {"count": 0, "pnl_sum": 0.0, "wins": 0})
            by_sig[key]["count"] += 1
            by_sig[key]["pnl_sum"] += (t.get("pnl_pct") or 0) * 100
            if (t.get("pnl_pct") or 0) > 0:
                by_sig[key]["wins"] += 1
        for v in by_sig.values():
            v["avg_return"] = round(v["pnl_sum"] / v["count"], 2) if v["count"] else 0
            v["win_rate"] = round(v["wins"] / v["count"] * 100, 1) if v["count"] else 0
        return by_sig

    @staticmethod
    def _summarize(cnt, win_cnt, returns, monthly_ret, violations,
                   by_sector, win_loss_ratio) -> str:
        parts = []
        if cnt == 0:
            parts.append("本月无交易")
        else:
            wr = round(win_cnt / cnt * 100, 1) if cnt > 0 else 0
            parts.append(f"{cnt}笔交易, 胜率{wr}%")
        if monthly_ret is not None:
            parts.append(f"月收益{round(monthly_ret * 100, 1):+.1f}%")
        if win_loss_ratio:
            parts.append(f"盈亏比{win_loss_ratio}")
        if violations > 0:
            parts.append(f"违规{violations}次")
        else:
            parts.append("无违规操作")
        if by_sector:
            top = by_sector[0]
            parts.append(f"最佳板块贡献 {top['pnl_sum']:+.1f}%")
        return "; ".join(parts)
