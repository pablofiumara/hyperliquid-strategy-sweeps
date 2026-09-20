import os

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://hl:hl@db:5432/hl"
)

_pool = None


def pool():
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            1, 10, DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
        )
    return _pool


def query(sql, args=None, one=False):
    conn = pool().getconn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
            return (rows[0] if rows else None) if one else rows
    finally:
        pool().putconn(conn)


def execute(sql, args=None):
    conn = pool().getconn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
    finally:
        pool().putconn(conn)
