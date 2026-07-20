# repositories/position_repository.py — position CRUD
import sqlite3
from contextlib import contextmanager


class PositionRepository:
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

    def upsert(self, stock_id: int, trade_id: int, avg_cost: float,
               shares: int = 0, position_pct: float = 0.0,
               ma10: float = None, ma21: float = None,
               ma10_status: str = None, sector_alert: int = 0) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO position (stock_id, trade_id, avg_cost, shares,
                   position_pct, ma10, ma21, ma10_status, sector_alert)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(stock_id) DO UPDATE SET
                       avg_cost=excluded.avg_cost,
                       shares=excluded.shares,
                       position_pct=excluded.position_pct,
                       ma10=excluded.ma10, ma21=excluded.ma21,
                       ma10_status=excluded.ma10_status,
                       sector_alert=excluded.sector_alert
                   RETURNING id""",
                (stock_id, trade_id, avg_cost, shares, position_pct,
                 ma10, ma21, ma10_status, sector_alert),
            )
            return cur.fetchone()["id"]

    def get_all(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM position").fetchall()
            return [dict(r) for r in rows]

    def delete(self, stock_id: int):
        with self._conn() as c:
            c.execute("DELETE FROM position WHERE stock_id=?", (stock_id,))
