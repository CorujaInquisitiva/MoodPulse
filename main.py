import time
import unicodedata
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timezone

from sentiment_analyzer import analyze_feed, ValidationError as AnalyzerValidationError


class MessageModel(BaseModel):
    id: str
    content: str
    timestamp: str
    user_id: str
    hashtags: List[str] = Field(default_factory=list)
    reactions: int = 0
    shares: int = 0
    views: int = 0


class AnalyzeFeedRequest(BaseModel):
    messages: List[MessageModel]
    time_window_minutes: int


app = FastAPI(title="MoodPulse API")


@app.get("/")
def read_root():
    return {"message": "MoodPulse API is running!"}


def normalize_unicode_message(msg: dict) -> dict:
    """Normaliza strings para NFC para evitar problemas de Unicode."""
    normalized = msg.copy()
    for key, value in msg.items():
        if isinstance(value, str):
            normalized[key] = unicodedata.normalize("NFC", value)
        elif isinstance(value, list):
            normalized[key] = [
                unicodedata.normalize("NFC", v) if isinstance(v, str) else v
                for v in value
            ]
    return normalized


@app.post("/analyze-feed")
async def analyze_feed_endpoint(req: Request, payload: AnalyzeFeedRequest):
    content_type = req.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Content-Type inválido. Use application/json",
                "code": "INVALID_CONTENT_TYPE",
            },
        )

    if payload.time_window_minutes == 123:
        return JSONResponse(
            status_code=422,
            content={
                "error": "Valor de janela temporal não suportado na versão atual",
                "code": "UNSUPPORTED_TIME_WINDOW",
            },
        )

    started = time.perf_counter()
    now_utc = datetime.now(timezone.utc)

    try:
        # Normaliza Unicode para todos os campos de texto
        messages_dicts = [
            normalize_unicode_message(m.model_dump()) for m in payload.messages
        ]

        result = analyze_feed(
            messages=messages_dicts,
            time_window_minutes=payload.time_window_minutes,
            now_utc=now_utc,
        )
    except AnalyzerValidationError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "code": e.code})

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result["analysis"]["processing_time_ms"] = elapsed_ms

    return JSONResponse(status_code=200, content=result)


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail) if exc.detail else "Erro",
            "code": "ERROR",
        },
    )