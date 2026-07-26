import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"

LONG_TERM_MEMORY_DB_PATH = (
    MEMORY_DIR / "long_term_memory.db"
)


def get_current_time() -> str:
    """返回当前时间字符串。"""
    return datetime.now().isoformat(
        timespec="seconds"
    )


def get_connection() -> sqlite3.Connection:
    """连接长期记忆数据库。"""
    MEMORY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(LONG_TERM_MEMORY_DB_PATH)
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """创建长期记忆表。"""
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                user_id TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, memory_key)
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


def save_memory(
    user_id: str,
    memory_key: str,
    memory_value: str,
) -> dict:
    """保存或更新一条用户长期记忆。"""
    clean_user_id = user_id.strip()
    clean_memory_key = memory_key.strip()
    clean_memory_value = memory_value.strip()

    if not clean_user_id:
        raise ValueError("user_id不能为空")

    if not clean_memory_key:
        raise ValueError("memory_key不能为空")

    if not clean_memory_value:
        raise ValueError("memory_value不能为空")

    current_time = get_current_time()
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO user_memories (
                user_id,
                memory_key,
                memory_value,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, memory_key)
            DO UPDATE SET
                memory_value = excluded.memory_value,
                updated_at = excluded.updated_at
            """,
            (
                clean_user_id,
                clean_memory_key,
                clean_memory_value,
                current_time,
                current_time,
            ),
        )

        connection.commit()

    finally:
        connection.close()

    return {
        "user_id": clean_user_id,
        "memory_key": clean_memory_key,
        "memory_value": clean_memory_value,
        "updated_at": current_time,
    }


def get_memories(user_id: str) -> list[dict]:
    """查询指定用户的全部长期记忆。"""
    clean_user_id = user_id.strip()

    if not clean_user_id:
        raise ValueError("user_id不能为空")

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                user_id,
                memory_key,
                memory_value,
                created_at,
                updated_at
            FROM user_memories
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (clean_user_id,),
        ).fetchall()

    finally:
        connection.close()

    return [
        {
            "user_id": row["user_id"],
            "memory_key": row["memory_key"],
            "memory_value": row["memory_value"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_memory(
    user_id: str,
    memory_key: str,
) -> bool:
    """删除指定用户的一条长期记忆。"""
    clean_user_id = user_id.strip()
    clean_memory_key = memory_key.strip()

    if not clean_user_id:
        raise ValueError("user_id不能为空")

    if not clean_memory_key:
        raise ValueError("memory_key不能为空")

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM user_memories
            WHERE user_id = ?
              AND memory_key = ?
            """,
            (
                clean_user_id,
                clean_memory_key,
            ),
        )

        connection.commit()
        deleted = cursor.rowcount > 0

    finally:
        connection.close()

    return deleted


initialize_database()