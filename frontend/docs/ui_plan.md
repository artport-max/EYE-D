# EYE-D Control Center UI 연동 계획 (Integration Plan)

본 문서는 새로 추가된 `frontend` (Vite + React 기반 프론트엔드) 폴더를 기존 FastAPI 백엔드(`server/app/main.py`)와 통합하기 위한 단계별 계획을 정의합니다.

## 1. 개발 환경 연동 (Development)
개발 단계에서는 UI 서버(Vite, Port: 3000)와 API 서버(FastAPI, Port: 8000)가 분리되어 구동되므로, 원활한 API 호출을 위한 설정이 필요합니다.

### 방법 A: FastAPI CORS 설정 추가 (권장)
백엔드(`server/app/main.py`)에서 프론트엔드의 접근을 허용합니다.
```python
from fastapi.middleware.cors import CORSMiddleware

# app 인스턴스 생성 직후
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 방법 B: Vite Proxy 설정
UI 프로젝트의 `vite.config.ts`에서 API 요청을 백엔드로 우회시킵니다.
```typescript
// frontend/vite.config.ts
export default defineConfig({
  // ... existing config ...
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    }
  }
});
```

---

## 2. 프로덕션 배포 연동 (Production)
운영 환경에서는 별도의 Node.js 서버 없이 FastAPI가 직접 UI의 빌드 결과물(정적 파일)을 제공(Serve)하도록 설정합니다.

### 2.1 프론트엔드 빌드
```bash
cd frontend
npm install
npm run build
```
- 빌드 완료 후 `dist` 폴더 안에 `index.html` 및 `assets/` 디렉토리가 생성됩니다.

### 2.2 FastAPI 정적 서빙 및 Catch-all 라우팅 추가
`server/app/main.py`의 가장 하단(모든 API 라우터 등록이 끝난 후)에 다음 코드를 추가합니다.
```python
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
```

---

## 3. 폴더 구조 개선 완료
기존 `server/app/eye-d-control-center` 경로에 있던 UI 코드를 서버, 엣지와 독립적인 프로젝트 루트 레벨의 `frontend/` 경로로 성공적으로 이동 및 분리 완료하였습니다.
