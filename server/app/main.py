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

from fastapi.middleware.cors import CORSMiddleware

# 개발 환경 UI 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# FastAPI 앱(main.py)의 위치는 server/app/main.py 이므로
# 프로젝트 루트의 frontend/dist 를 가리키기 위해 두 단계 위로 올라갑니다.
ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))

if os.path.exists(ui_dir):
    # 1. 빌드된 에셋(js, css, 이미지 등) 마운트
    app.mount("/assets", StaticFiles(directory=os.path.join(ui_dir, "assets")), name="assets")

    # 2. React Router (SPA) 지원용 Catch-all 라우터
    # 기존 API 라우트에 걸리지 않는 모든 요청을 index.html로 반환
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_ui(full_path: str):
        return FileResponse(os.path.join(ui_dir, "index.html"))