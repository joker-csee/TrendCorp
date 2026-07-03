# repositories/nav_repository.py — nav_snapshot
import sqlite3
from contextlib import contextmanager


class NavRepository:
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

    def save_snapshot(
        self,
        snap_date: str,
        total_value: float,
        cash: float,
        positions_value: float,
        daily_return: float = 0.0,
        weekly_return: float = 0.0,
        monthly_return: float = 0.0,
        max_drawdown: float = 0.0,
        position_pct: float = 0.0,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR REPLACE INTO nav_snapshot
                   (snap_date, total_value, cash, positions_value,
                    daily_return, weekly_return, monthly_return,
                    max_drawdown, position_pct)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (snap_date, total_value, cash, positions_value,
                 daily_return, weekly_return, monthly_return,
                 max_drawdown, position_pct),
            )
            return cur.lastrowid

    def get_latest(self) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM nav_snapshot ORDER BY snap_date DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def get_history(self, days: int = 90) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM nav_snapshot
                   WHERE snap_date >= date('now', ? || ' days')
                   ORDER BY snap_date ASC""",
                (f"-{days}",),
            ).fetchall()
            return [dict(r) for r in rows]
