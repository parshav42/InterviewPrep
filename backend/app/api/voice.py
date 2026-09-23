from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.dependencies import current_user
from app.db.models.user import User
from app.services.voice_service import DeterministicSpeechProvider, DeterministicTextToSpeechProvider

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: Annotated[User, Depends(current_user)] = None) -> dict[str, str]:
    _ = user
    return {"text": DeterministicSpeechProvider().transcribe_audio(await audio.read(), audio.content_type or "application/octet-stream")}


@router.post("/synthesize")
async def synthesize(text: str, user: Annotated[User, Depends(current_user)]) -> Response:
    _ = user
    return Response(DeterministicTextToSpeechProvider().generate_speech(text), media_type="audio/wav")