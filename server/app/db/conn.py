import os
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    """앱 시작 시 1번 호출. 연결 풀을 만들어 둔다."""
    global _pool
    if _pool is None:
        dsn = os.getenv(
            "DATABASE_URL",
            "postgresql://eyed:eyed_dev_pw@localhost:5433/eyed",
        )
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    assert _pool is not None     
    
    # 자동으로 schema 마이그레이션 (similarity 컬럼 추가)
    async with _pool.acquire() as conn:
        await conn.execute("ALTER TABLE detections ADD COLUMN IF NOT EXISTS similarity REAL;")
        
    return _pool


async def close_pool() -> None:
    """앱 종료 시 1번 호출."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """이미 초기화된 풀을 가져온다."""
    if _pool is None:
        raise RuntimeError("DB pool not initialized. init_pool() 먼저 호출.")
    return _pool