import json
import sqlite3
from typing import Optional


def create_session(
    conn: sqlite3.Connection, session_id: str, user_label: str
) -> dict:
    conn.execute(
        """
        INSERT INTO agent_sessions(session_id, user_label)
        VALUES (?, ?)
        """,
        (session_id, user_label),
    )
    return get_session(conn, session_id)


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM agent_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_messages(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM agent_messages
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_message(
    conn: sqlite3.Connection,
    session_id: str,
    role: str,
    content: str,
) -> None:
    content_json = json.dumps({"content": content}, ensure_ascii=False, separators=(",", ":"))
    conn.execute(
        """
        INSERT INTO agent_messages(session_id, role, content_json)
        VALUES (?, ?, ?)
        """,
        (session_id, role, content_json),
    )


def update_summary(conn: sqlite3.Connection, session_id: str, summary: str) -> None:
    conn.execute(
        """
        UPDATE agent_sessions
        SET summary = ?, updated_at = CURRENT_TIMESTAMP
        WHERE session_id = ?
        """,
        (summary, session_id),
    )


def touch_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "UPDATE agent_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (session_id,),
    )


def save_audit_event(
    conn: sqlite3.Connection,
    session_id: Optional[str],
    action: str,
    detail: dict,
) -> None:
    detail_json = json.dumps(detail, ensure_ascii=False, separators=(",", ":"))
    conn.execute(
        """
        INSERT INTO agent_audit_events(session_id, action, detail_json)
        VALUES (?, ?, ?)
        """,
        (session_id, action, detail_json),
    )


def list_audit_events(
    conn: sqlite3.Connection,
    session_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> list[dict]:
    if session_id:
        rows = conn.execute(
            """
            SELECT * FROM agent_audit_events
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (session_id, page_size, (page - 1) * page_size),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM agent_audit_events
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, (page - 1) * page_size),
        ).fetchall()
    return [dict(row) for row in rows]
