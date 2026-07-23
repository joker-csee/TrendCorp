# repositories/trade_repository.py — trade CRUD
import sqlite3
from contextlib import contextmanager


class TradeRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_by_id(self, trade_id: int) -> dict | None:
        """P2-2: 按主键查询。"""
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM trade WHERE id = ?", (trade_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_max_seq_today(self, prefix: str) -> int:
        """返回当日最大 trade_no 序号（用于防碰撞生成）。"""
        with self._conn() as c:
            row = c.execute(
                "SELECT MAX(trade_no) FROM trade WHERE trade_no LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
            val = row[0]
            if val:
                try:
                    return int(val.rsplit("-", 1)[-1])
                except (ValueError, IndexError):
                    pass
            return 0

    def insert(self, trade_no: str, stock_id: int, sector_id: int = None,
               open_date: str = "", open_price: float = 0.0,
               open_reason: str = "", open_ma10: float = None,
               open_position: float = 0.0) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO trade (trade_no, stock_id, sector_id,
                   open_date, open_price, open_reason, open_ma10, open_position)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (trade_no, stock_id, sector_id,
                 open_date, open_price, open_reason, open_ma10, open_position),
            )
            return cur.lastrowid

    def update_close(self, trade_id: int, close_date: str, close_price: float,
                     close_reason: str, pnl_amount: float = None,
                     pnl_pct: float = None, rule_compliant: int = 1,
                     lesson: str = None):
        with self._conn() as c:
            c.execute(
                """UPDATE trade SET close_date=?, close_price=?,
                   close_reason=?, pnl_amount=?, pnl_pct=?,
                   rule_compliant=?, lesson=?
                   WHERE id=?""",
                (close_date, close_price, close_reason,
                 pnl_amount, pnl_pct, rule_compliant, lesson, trade_id),
            )

    def get_open_trades(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM trade WHERE close_date IS NULL"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM trade ORDER BY open_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_monthly_stats(self, year: int, month: int) -> dict:
        with self._conn() as c:
            prefix = f"{year}-{month:02d}"
            rows = c.execute(
                """SELECT * FROM trade
                   WHERE open_date LIKE ? AND close_date IS NOT NULL""",
                (f"{prefix}%",),
            ).fetchall()
            trades = [dict(r) for r in rows]
        if not trades:
            return {"count": 0, "win_rate": 0, "avg_return": 0}
        wins = [t for t in trades if (t.get("pnl_pct") or 0) > 0]
        returns = [(t.get("pnl_pct") or 0) for t in trades]
        return {
            "count": len(trades),
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0,
            "avg_return": round(sum(returns) / len(returns), 4),
        }
