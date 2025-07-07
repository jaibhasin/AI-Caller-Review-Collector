import os, json, base64, aiohttp
from fastapi import APIRouter, WebSocket
from dotenv import load_dotenv
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import generate_response

load_dotenv()
API_KEY  = os.getenv("ELEVEN_LABS_API_KEY")         # ← make sure this exists
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
MODEL_ID = "eleven_multilingual_v2"

router = APIRouter()

@router.websocket("/agent/voice")
async def agent_voice(ws: WebSocket):
    await ws.accept()

    # 1️⃣ receive caller audio
    first = await ws.receive()
    if first["type"] != "websocket.receive" or "bytes" not in first:
        await ws.close(code=4000)
        return
    audio_bytes = first["bytes"]

    # 2️⃣ STT ➜ LLM
    user_text = transcribe_audio(audio_bytes)
    if not user_text:
        await ws.send_json({"error": "could_not_transcribe"})
        await ws.close()
        return

    agent_reply = generate_response(user_text)
    await ws.send_json({"user_text": user_text, "agent_reply": agent_reply})

    # 3️⃣ ElevenLabs streaming (aiohttp WebSocket)
    url = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/"
        f"{VOICE_ID}/stream-input?model_id={MODEL_ID}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, max_msg_size=0) as el_ws:

            # initialise connection (key inside JSON)
            await el_ws.send_json({
                "text": " ",
                "xi_api_key": API_KEY,
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.8,
                    "use_speaker_boost": False
                },
                "generation_config": {"chunk_length_schedule": [50, 100]}
            })

            # send LLM reply
            await el_ws.send_json({"text": agent_reply, "flush": True})
            await el_ws.send_json({"text": ""})          # end marker

            # relay audio chunks to the caller
            async for msg in el_ws:
                if msg.type is aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    audio_b64 = data.get("audio")
                    if audio_b64:                        # skip control packets
                        await ws.send_bytes(base64.b64decode(audio_b64))
                    if data.get("isFinal"):
                        break
                elif msg.type is aiohttp.WSMsgType.ERROR:
                    break

    await ws.close()
