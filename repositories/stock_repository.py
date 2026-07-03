# repositories/stock_repository.py — stock
import sqlite3
from contextlib import contextmanager


class StockRepository:
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

    def upsert_stock(
        self, code: str, name: str, sector_id: int = None, market_cap: float = None
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO stock (code, name, sector_id, market_cap)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET
                       name=excluded.name,
                       sector_id=COALESCE(excluded.sector_id, stock.sector_id),
                       market_cap=COALESCE(excluded.market_cap, stock.market_cap)
                   RETURNING id""",
                (code, name, sector_id, market_cap),
            )
            return cur.fetchone()["id"]

    def get_by_code(self, code: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM stock WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None
