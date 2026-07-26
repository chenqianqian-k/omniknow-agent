import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
SESSION_DB_PATH = MEMORY_DIR / "sessions.db"


def get_current_time() -> str:
    """返回当前时间字符串。"""
    return datetime.now().isoformat(
        timespec="seconds"
    )


def get_connection() -> sqlite3.Connection:
    """创建会话信息数据库连接。"""
    MEMORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(SESSION_DB_PATH)
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """创建会话信息表。"""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_session(
    thread_id: str,
    first_query: str,
) -> None:
    """保存新会话，或者更新已有会话的最后使用时间。"""
    current_time = get_current_time()

    clean_query = " ".join(
        first_query.strip().split()
    )

    title = clean_query[:30] or "新对话"

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (
                thread_id,
                title,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(thread_id)
            DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (
                thread_id,
                title,
                current_time,
                current_time,
            ),
        )


def list_sessions() -> list[dict]:
    """按照最后使用时间查询历史会话。"""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                thread_id,
                title,
                created_at,
                updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [
        {
            "thread_id": row["thread_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_session(thread_id: str) -> bool:
    """删除指定会话的列表信息。"""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM sessions
            WHERE thread_id = ?
            """,
            (thread_id,),
        )

    return cursor.rowcount > 0


initialize_database()