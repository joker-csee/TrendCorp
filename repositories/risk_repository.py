# repositories/risk_repository.py — risk_event CRUD
import sqlite3
from contextlib import contextmanager


class RiskRepository:
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

    def log(self, event_time: str, event_type: str, event_level: str,
            detail: str = None, action_taken: str = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO risk_event (event_time, event_type, event_level,
                   detail, action_taken)
                   VALUES (?,?,?,?,?)""",
                (event_time, event_type, event_level, detail, action_taken),
            )
            return cur.lastrowid

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM risk_event ORDER BY event_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
