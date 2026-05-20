"""EYE-D backend FastAPI 진입점.
앱 설정 + 라우터 등록 + 공통 엔드포인트(/health, /admin/*) + 프론트엔드 정적 서빙."""
from contextlib import asynccontextmanager
import os
import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path

from app.db.conn import init_pool, close_pool, get_pool
from app.services.token_governor import governor
from app.routers import security as security_router
from app.routers import retail as retail_router
from app.routers import art as art_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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
    title="EYE-D Backend (PS Center)",
    description="엣지 게이트웨이 → 백엔드 수신/관리 API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — 한 번만 등록 (이전 중복 코드 정리, 2026-05-19)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",   # 개발 단계 React
        "*",                                                # 개발 편의용. 운영 시 제거 권장
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 도메인별 라우터 등록 — Retail 은 반드시 catch-all 보다 *위* 에 있어야 함
app.include_router(security_router.router)
app.include_router(retail_router.router)   # 2026-05-19 추가: Smart Retail
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


# ============================================================
# 프론트엔드 자동 빌드 + 정적 파일 서빙 (원격 1fd2332 도입)
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_dir = os.path.join(BASE_DIR, "frontend")
frontend_dist = os.path.join(frontend_dir, "dist")

# 서버 실행 시 자동으로 프론트엔드 빌드 수행
if os.path.isdir(frontend_dir):
    print("[startup] Building frontend automatically...")
    try:
        subprocess.run(["npm", "install"], cwd=frontend_dir,
                       check=True, shell=os.name == "nt")
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir,
                       check=True, shell=os.name == "nt")
        print("[startup] Frontend build completed.")
    except Exception as e:
        print(f"[startup] Frontend build failed: {e}")

if os.path.isdir(frontend_dist):
    # 정적 파일 마운트 (js, css 등)
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(frontend_dist, "assets")),
        name="assets",
    )

    # SPA 라우팅 catch-all — API/health 경로는 제외
    @app.get("/{catchall:path}", include_in_schema=False)
    async def serve_react_app(catchall: str):
        if catchall.startswith("api/") or catchall == "health":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        file_path = os.path.join(frontend_dist, catchall)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return JSONResponse({"detail": "Not Found"}, status_code=404)
else:
    @app.get("/")
    def read_root():
        return {
            "message": "EYE-D Backend is running.",
            "ui_status": "Frontend build not found. "
                         "Please run 'npm install && npm run build' in the frontend folder.",
        }
