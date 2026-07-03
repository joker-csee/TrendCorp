# repositories/sector_repository.py — sector + sector_snapshot
import sqlite3
from contextlib import contextmanager


class SectorRepository:
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

    def upsert_sector(self, code: str, name: str, sec_type: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO sector (code, name, type)
                   VALUES (?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET name=excluded.name
                   RETURNING id""",
                (code, name, sec_type),
            )
            return cur.fetchone()["id"]

    def get_by_code(self, code: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM sector WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_active(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM sector WHERE is_active = 1"
            ).fetchall()
            return [dict(r) for r in rows]

    def save_snapshot(
        self,
        sector_id: int, snap_date: str,
        trend_score: float, rel_strength: float,
        fund_score: float, echelon_score: float, total_score: float,
        ma5: float = None, ma10: float = None,
        ma21: float = None, ma55: float = None,
        ret_20d: float = None, hs300_ret_20d: float = None,
        fund_flow_5d: float = None, limit_up_cnt: int = None,
        volume_ratio: float = None,
        is_confirmed: int = 0, confirm_reason: str = None,
        alert_level: int = 0, alert_triggers: str = None,
    ) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR REPLACE INTO sector_snapshot
                   (sector_id, snap_date, trend_score, rel_strength,
                    fund_score, echelon_score, total_score,
                    ma5, ma10, ma21, ma55,
                    ret_20d, hs300_ret_20d, fund_flow_5d,
                    limit_up_cnt, volume_ratio,
                    is_confirmed, confirm_reason,
                    alert_level, alert_triggers)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sector_id, snap_date, trend_score, rel_strength,
                 fund_score, echelon_score, total_score,
                 ma5, ma10, ma21, ma55,
                 ret_20d, hs300_ret_20d, fund_flow_5d,
                 limit_up_cnt, volume_ratio,
                 is_confirmed, confirm_reason,
                 alert_level, alert_triggers),
            )
            return cur.lastrowid

    def get_latest_snapshot(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT ss.*, s.name as sector_name
                   FROM sector_snapshot ss
                   JOIN sector s ON ss.sector_id = s.id
                   WHERE ss.snap_date = (
                       SELECT MAX(snap_date) FROM sector_snapshot
                   )
                   ORDER BY ss.total_score DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_history(self, sector_id: int, months: int = 3) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM sector_snapshot
                   WHERE sector_id = ?
                     AND snap_date >= date('now', ? || ' months')
                   ORDER BY snap_date DESC""",
                (sector_id, f"-{months}"),
            ).fetchall()
            return [dict(r) for r in rows]
