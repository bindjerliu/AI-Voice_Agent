"""Voice-agent chat endpoint.

Stands in for the real telephony + STT + LLM + TTS pipeline. The caller
speaks (here: types); STT would transcribe to text; this endpoint runs
the agent turn; TTS would speak the reply back in Standard Albanian.
"""
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agent import service
from app.db import get_db

router = APIRouter(prefix="/api/agent", tags=["agent"])


class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    caller_phone: str
    message: str
    history: list[Turn] = []


@router.get("/engine")
def get_engine():
    return {"mode": service.engine_mode()}


@router.post("/chat")
def chat(payload: ChatRequest, conn: sqlite3.Connection = Depends(get_db)):
    history = [{"role": t.role, "content": t.content} for t in payload.history]
    return service.run_turn(conn, payload.caller_phone, history, payload.message)
