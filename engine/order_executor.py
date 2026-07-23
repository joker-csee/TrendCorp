# engine/order_executor.py — D-2 订单执行器
import logging


class OrderExecutor:
    """D-2 订单执行器：生成人类可读的交易指令。

    M4 阶段输出文本指令供人工在券商 App 执行，M5 阶段可扩展为 API 下单。
    """

    def __init__(self):
        self.logger = logging.getLogger("app.order_executor")

    def execute(self, order, total_nav: float = 100_000.0) -> dict:
        """将 TradeOrder 转换为可执行的文本指令。"""
        amount = total_nav * order.target_pct
        return {
            "stock_code": order.stock_code,
            "direction": order.direction.value,
            "target_pct": round(order.target_pct * 100, 1),
            "amount": round(amount, 0),
            "price_type": order.price_type,
            "limit_price": order.limit_price,
            "instruction": self._format(order, amount, total_nav),
        }

    @staticmethod
    def _format(order, amount, total_nav) -> str:
        pct_str = f"{order.target_pct * 100:.1f}%"
        amt_str = f"${amount:,.0f}"
        if order.direction.value == "BUY":
            price_hint = (
                f"限价 ${order.limit_price}" if order.limit_price
                else "市价"
            )
            return (f"[买入] {order.stock_code} | 仓位 {pct_str} "
                    f"({amt_str} / ${total_nav:,.0f}) | {price_hint}")
        else:
            return (f"[卖出] {order.stock_code} | 仓位 {pct_str} "
                    f"({amt_str}) | {order.price_type}")
