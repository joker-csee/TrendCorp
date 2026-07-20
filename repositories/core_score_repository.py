# repositories/core_score_repository.py — core_score_snapshot CRUD
import sqlite3
from contextlib import contextmanager


class CoreScoreRepository:
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

    def save_snapshot(self, stock_id: int, snap_date: str, **scores):
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR REPLACE INTO core_score_snapshot
                   (stock_id, snap_date, market_cap_score, liquidity_score,
                    ma_structure_score, vol_health_score, fundamental_score,
                    total_score, price, ma5, ma10, ma21, ma55,
                    ma_deviation, vol_ratio_20, signal)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (stock_id, snap_date,
                 scores.get("market_cap_score"),
                 scores.get("liquidity_score"),
                 scores.get("ma_structure_score"),
                 scores.get("vol_health_score"),
                 scores.get("fundamental_score"),
                 scores.get("total_score"),
                 scores.get("price"), scores.get("ma5"),
                 scores.get("ma10"), scores.get("ma21"), scores.get("ma55"),
                 scores.get("ma_deviation"), scores.get("vol_ratio_20"),
                 scores.get("signal")),
            )
            return cur.lastrowid

    def get_latest_for_stock(self, stock_id: int) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                """SELECT * FROM core_score_snapshot
                   WHERE stock_id = ?
                   ORDER BY snap_date DESC LIMIT 1""",
                (stock_id,),
            ).fetchone()
            return dict(row) if row else None
