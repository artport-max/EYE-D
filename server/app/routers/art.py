"""arttrace 확장 슬롯 — Phase B(6월 이후) 시작 시 채워질 라우터.
현재는 모든 엔드포인트가 501 Not Implemented 응답."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/art", tags=["art"])


@router.post("/interpretations")
async def create_interpretation():
    """관객 상태 해석 (Aesthetic Agent 호출 예정)."""
    raise HTTPException(status_code=501, detail="Not implemented (Phase B)")


@router.post("/generations/text")
async def generate_text():
    """텍스트 생성 (Text Agent 호출 예정)."""
    raise HTTPException(status_code=501, detail="Not implemented (Phase B)")


@router.post("/generations/audio")
async def generate_audio():
    """오디오 생성 (Sound Agent 호출 예정)."""
    raise HTTPException(status_code=501, detail="Not implemented (Phase B)")