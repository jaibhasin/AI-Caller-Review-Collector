import os, json, base64, aiohttp
from fastapi import APIRouter, WebSocket
from dotenv import load_dotenv
from app.services.stt2_service import transcribe_audio
# from app.services.whisper_service import transcribe_audio
# from app.services.llm_service import generate_response
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')

GOOGLE_API_KEY = os.getenv("SECRET_KEY_GOOGLE_AI")  # Ensure this exists

from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory


API_KEY  = os.getenv("ELEVEN_LABS_API_KEY")         # ← make sure this exists
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
MODEL_ID = "eleven_turbo_v2_5"

router = APIRouter()


BASE_PROMPT = """You are an AI phone agent gathering concise customer feedback.

Product context
• Name: {product_name}
• One-line description: {product_description}

Guidelines for every reply (≤ 25 words)
1. Greet or respond politely.
2. Ask one clear question about the product’s quality, features, or user experience.
3. If the caller answers clearly, thank them and sign off.
4. If the answer is vague, ask one follow-up for clarification.
5. No explanations about yourself or the system.
6. Mirror the caller’s language; default to English if unsure.
7. Never exceed 25 words.

Caller: {input}
Agent:"""

prompt = PromptTemplate.from_template(BASE_PROMPT)


@router.websocket("/agent/voice")
async def agent_voice(ws: WebSocket):
    await ws.accept()
    memory = ConversationBufferMemory()
    conversation = ConversationChain(
        llm = llm,
        prompt = prompt,
        input_variables = ["product_name", "product_description", "input"],
        memory = memory
    )

    PRODUCT_NAME = "Lifelong Professional Pickleball Set"
    PRODUCT_DESC = (
        "A complete set with durable fiberglass paddles and ergonomic grips—balanced "
        "performance and comfort for all ages and skill levels."
    )

    try : 
        
        
        initial_reply = conversation.run(
            product_name = PRODUCT_NAME,
            product_description = PRODUCT_DESC,
            input = ""
        ).strip()
        await ws.send_json({"user_text": "Call started", "agent_reply": initial_reply})

        # Stream initial greeting audio
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, max_msg_size=0) as el_ws:
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
                await el_ws.send_json({"text": initial_reply, "flush": True})
                await el_ws.send_json({"text": ""})
                async for msg in el_ws:
                    if msg.type is aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        audio_b64 = data.get("audio")
                        if audio_b64:
                            await ws.send_bytes(base64.b64decode(audio_b64))
                        if data.get("isFinal"):
                            break
                    elif msg.type is aiohttp.WSMsgType.ERROR:
                        break

        while True : 

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

            # agent_reply = generate_response(user_text)
            # full_prompt = f"{BASE_PROMPT}\nUser: {user_text}\nAgent:"
            # agent_reply = conversation.run(full_prompt)

            agent_reply = conversation.run(
                product_name = PRODUCT_NAME,
                product_description = PRODUCT_DESC,
                input = user_text
            )

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
    finally : 
        await ws.close()
