import sqlite3
from typing import Optional


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
