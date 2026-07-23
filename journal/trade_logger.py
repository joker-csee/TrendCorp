# journal/trade_logger.py — F-1 交易日志
import logging
from datetime import date

from repositories.trade_repository import TradeRepository
from repositories.stock_repository import StockRepository
from repositories.sector_repository import SectorRepository


class TradeLogger:
    """F-1: 交易录入 + 平仓更新 + 合规检查。"""

    def __init__(self, trade_repo: TradeRepository,
                 stock_repo: StockRepository,
                 sector_repo: SectorRepository = None):
        self.trade_repo = trade_repo
        self.stock_repo = stock_repo
        self.sector_repo = sector_repo
        self.logger = logging.getLogger("app.trade_logger")

    def log_open(self, stock_code: str, open_price: float,
                 open_reason: str, open_ma10: float = None,
                 position_pct: float = 0.0,
                 sector_code: str = None) -> dict:
        """录入开仓交易。返回 {trade_no, trade_id}。"""
        # 确保 stock 入库
        stock_id = self.stock_repo.upsert_stock(
            code=stock_code, name=stock_code
        )
        sector_id = None
        if sector_code and self.sector_repo:
            sec = self.sector_repo.get_by_code(sector_code)
            if sec:
                sector_id = sec["id"]

        trade_no = self._gen_trade_no()
        trade_id = self.trade_repo.insert(
            trade_no=trade_no,
            stock_id=stock_id,
            sector_id=sector_id,
            open_date=str(date.today()),
            open_price=open_price,
            open_reason=open_reason,
            open_ma10=open_ma10,
            open_position=position_pct,
        )
        self.logger.info(
            "交易录入: %s %s @ %.2f (%s) 仓位%.0f%%",
            trade_no, stock_code, open_price, open_reason, position_pct,
        )
        return {"trade_no": trade_no, "trade_id": trade_id}

    def log_close(self, trade_id: int, close_price: float,
                  close_reason: str, rule_compliant: bool = True,
                  lesson: str = None):
        """录入平仓。自动计算盈亏。"""
        # 获取原交易记录
        trades = self.trade_repo.get_all(limit=100)
        trade = None
        for t in trades:
            if t["id"] == trade_id:
                trade = t
                break
        if not trade:
            raise ValueError(f"交易记录不存在: id={trade_id}")

        open_price = trade["open_price"]
        pnl_pct = (close_price - open_price) / open_price
        pnl_amount = close_price - open_price  # 简化的每股盈亏

        self.trade_repo.update_close(
            trade_id=trade_id,
            close_date=str(date.today()),
            close_price=close_price,
            close_reason=close_reason,
            pnl_amount=round(pnl_amount, 4),
            pnl_pct=round(pnl_pct, 4),
            rule_compliant=1 if rule_compliant else 0,
            lesson=lesson,
        )
        self.logger.info(
            "交易平仓: #%d %s → %.2f (%+.2f%%) 合规=%s",
            trade_id, trade["trade_no"],
            close_price, pnl_pct * 100, rule_compliant,
        )

    @staticmethod
    def _gen_trade_no() -> str:
        today = date.today().strftime("%Y%m%d")
        import random
        seq = random.randint(100, 999)
        return f"T-{today}-{seq}"
