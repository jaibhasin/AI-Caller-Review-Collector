from fastapi import FastAPI
from app.api import stt, chat
# from app.api.tts_stream import router as tts_ws_router
from app.api.agent_voice import router as agent_voice_router

app = FastAPI()

app.include_router(stt.router, prefix="/stt", tags=["STT"])
app.include_router(chat.router , prefix="/agent", tags=["Chat"])
# app.include_router(tts_ws_router, prefix="/api", tags=["TTS"])
app.include_router(agent_voice_router, prefix="/api", tags=["Agent voice"])
