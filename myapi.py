import os, json, base64, asyncio, pathlib, websockets
from dotenv import load_dotenv

load_dotenv()
API_KEY  = os.getenv("ELEVEN_LABS_API_KEY")      # must be set
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
MODEL_ID = "eleven_multilingual_v2"
OUTFILE  = "stream_test.mp3"

async def go():
    uri = (f"wss://api.elevenlabs.io/v1/text-to-speech/"
           f"{VOICE_ID}/stream-input?model_id={MODEL_ID}")

    async with websockets.connect(uri, max_size=None) as ws:
        # initialise
        await ws.send(json.dumps({
            "text": " ",
            "xi_api_key": API_KEY,
            "voice_settings": {"stability": 0.3, "similarity_boost": 0.8}
        }))
        # actual text
        await ws.send(json.dumps({"text": "Realtime test from ElevenLabs.", "flush": True}))
        await ws.send(json.dumps({"text": ""}))

        pathlib.Path(OUTFILE).write_bytes(b"")      # truncate
        async for msg in ws:
            data = json.loads(msg)
            audio_b64 = data.get("audio")
            if audio_b64:                          # ← guard against null/None
                with open(OUTFILE, "ab") as f:
                    f.write(base64.b64decode(audio_b64))
            if data.get("isFinal"):
                break

asyncio.run(go())
print("✅ wrote", OUTFILE, "-", pathlib.Path(OUTFILE).stat().st_size, "bytes")
