import asyncio
import websockets
import json

# Update this if needed
URI = "ws://127.0.0.1:8000/api/agent/voice"

AUDIO_IN  = "fixed1.wav"     # Input audio file
AUDIO_OUT = "reply.mp3"      # Output file (TTS response)

async def main():
    # Read caller audio
    with open(AUDIO_IN, "rb") as f:
        payload = f.read()

    async with websockets.connect(URI, max_size=None) as ws:
        print("🔗 Connected to agent")

        # 1️⃣ Send audio to backend
        await ws.send(payload)

        # 2️⃣ Receive text metadata
        meta = await ws.recv()
        meta_data = json.loads(meta)
        print("👤 User:", meta_data.get("user_text"))
        print("🤖 Agent:", meta_data.get("agent_reply"))

        # 3️⃣ Receive audio stream
        with open(AUDIO_OUT, "wb") as out:
            while True:
                try:
                    msg = await ws.recv()
                    if isinstance(msg, bytes):
                        out.write(msg)
                except websockets.exceptions.ConnectionClosed:
                    break

    print(f"✅ Audio saved to {AUDIO_OUT}")

if __name__ == "__main__":
    asyncio.run(main())
