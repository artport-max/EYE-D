"""kote backend FastAPI 진입점.
앱 설정 + 라우터 등록 + 공통 엔드포인트(/health, /admin/*)만 담당."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

from app.db.conn import init_pool, close_pool, get_pool
from app.services.token_governor import governor
from app.routers import security as security_router
from app.routers import art as art_router

load_dotenv()  # .env 파일을 환경변수로 로드


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시
    await init_pool()
    print("[startup] DB pool ready")
    yield
    # 앱 종료 시
    await close_pool()
    print("[shutdown] DB pool closed")


app = FastAPI(
    title="kote backend",
    description="엣지 게이트웨이 → 백엔드 수신/관리 API",
    version="0.1.0",
    lifespan=lifespan,
)

# 도메인별 라우터 등록
app.include_router(security_router.router)
app.include_router(art_router.router)


@app.get("/health", tags=["admin"])
async def health() -> dict:
    """서버와 DB가 모두 살아 있는지 확인."""
    pool = get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT 1")
    return {"status": "ok", "db": val}


@app.get("/admin/tokens", tags=["admin"])
async def token_stats():
    """현재 토큰 사용 통계 (운영자/디버그용)."""
    return governor.stats()