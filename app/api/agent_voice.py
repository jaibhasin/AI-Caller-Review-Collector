import os, json, base64, aiohttp
from fastapi import APIRouter, WebSocket
from dotenv import load_dotenv
# Use the simple STT service instead of complex streaming
from app.services.simple_stt_service import transcribe_audio_simple
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import time


load_dotenv()




GOOGLE_API_KEY = os.getenv("SECRET_KEY_GOOGLE_AI")  # Ensure this exists

# Initialize LLM with better settings for conversation
llm = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash',  # Use the most advanced model
    google_api_key=GOOGLE_API_KEY,
    temperature=0.8,   # More creative and natural responses
    max_tokens=150,    # Allow longer, more natural responses
    top_p=0.9         # Better response variety
)


from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
import json


API_KEY  = os.getenv("ELEVEN_LABS_API_KEY")
# Using a more conversational voice (this is Rachel - sounds more natural for phone calls)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel - warm, conversational female voice
MODEL_ID = "eleven_turbo_v2_5"



router = APIRouter()


BASE_PROMPT = """You are Sarah, a customer service representative from Lifelong company. You are CALLING the customer to ask about their experience with the Lifelong Professional Pickleball Set they purchased.

IMPORTANT ROLE CLARITY:
- YOU are Sarah from Lifelong (the company)
- The HUMAN is the customer who bought the pickleball set
- YOU are asking THEM about their experience
- DO NOT respond as if you are the customer
- DO NOT say things like "Hi Sarah" - YOU ARE Sarah

Your job as Sarah:
- Ask the customer about their experience with the pickleball set
- Listen to their feedback and respond appropriately
- Be warm, friendly, and genuinely interested in their experience
- Speak naturally and take your time

How to respond as Sarah:
1. Acknowledge what the customer just told you
2. Show genuine interest in their experience  
3. Ask follow-up questions about the product
4. Use their words when responding ("You mentioned the grip...")

Example responses (YOU as Sarah speaking TO the customer):
- "Oh that's wonderful to hear! What do you love most about the set?"
- "I'm so glad you're enjoying it! How has the grip been working for you?"
- "That's exactly what we hoped for! Has it helped improve your game at all?"
- "Oh no, I'm sorry to hear that. Can you tell me what happened?"

REMEMBER: You are Sarah calling them, not the other way around!

Current conversation:
{history}
Human: {input}
Sarah:"""

prompt = PromptTemplate.from_template(BASE_PROMPT)


@router.websocket("/agent/voice")
async def agent_voice(ws: WebSocket):
    """
    This function handles the voice conversation:
    1. Accepts connection from frontend
    2. Sets up AI conversation memory
    3. Processes audio back and forth
    """
    await ws.accept()  # Accept the connection from frontend
    memory = ConversationBufferMemory()  # Remember conversation history
    
    conversation = ConversationChain(
        llm=llm,
        prompt=prompt,
        memory=memory
    )
    
    # Add initial system context to prevent role confusion
    memory.chat_memory.add_message(HumanMessage(content="[SYSTEM: You are Sarah from Lifelong calling the customer about their pickleball set purchase]"))
    memory.chat_memory.add_message(AIMessage(content="Understood. I am Sarah from Lifelong calling to ask about their experience."))
    
    # Track conversation state to make it smarter
    conversation_state = {
        "topics_covered": [],
        "customer_sentiment": "neutral",
        "main_feedback": None,
        "turn_count": 0
    }

    PRODUCT_NAME = "Lifelong Professional Pickleball Set"
    PRODUCT_DESC = (
        "A complete set with durable fiberglass paddles and ergonomic grips—balanced "
        "performance and comfort for all ages and skill levels."
    )

    try : 
        
        
        # Generate initial greeting - make it clear who Sarah is
        initial_reply = "Hi there! This is Sarah calling from Lifelong. I hope you're having a good day. I wanted to give you a quick call about the pickleball set you got from us recently. Is this an okay time to chat for just a minute?"
        await ws.send_json({"user_text": "Call started", "agent_reply": initial_reply}) # where is this sending and what is it sending which format 

        # Stream initial greeting audio
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}" # is there a websocket on that end as well , could we access it if this wasnt a websocket
        

        async with aiohttp.ClientSession() as session:   # what is aiohttp ? is it a websocket or what 
            async with session.ws_connect(url, max_msg_size=0) as el_ws: #what is session.ws_connect
                await el_ws.send_json({
                    "text": " ",
                    "xi_api_key": API_KEY,
                    "voice_settings": {
                        "stability": 0.8,         # Much more stable, less rushed
                        "similarity_boost": 0.7,   # Softer, more natural voice
                        "use_speaker_boost": True,
                        "style": 0.3              # More conversational but not too much
                    },
                    "generation_config": {
                        "chunk_length_schedule": [80, 120]  # Longer chunks = smoother speech
                    }
                })
                await el_ws.send_json({"text": initial_reply, "flush": True})
                await el_ws.send_json({"text": ""})
                async for msg in el_ws:
                    if msg.type is aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        audio_b64 = data.get("audio")
                        if audio_b64:
                            # Convert the audio data and send to frontend
                            chunk = base64.b64decode(audio_b64)
                            await ws.send_bytes(chunk)
                        else:
                            print("[DEBUG] No audio in this packet")
                            print(data)
                        if data.get("isFinal"):
                            break
                    elif msg.type is aiohttp.WSMsgType.ERROR:
                        break

        while True:
            # Step 1: Receive audio from user
            first = await ws.receive()
            if first["type"] != "websocket.receive" or "bytes" not in first:
                await ws.close(code=4000)
                return
            audio_bytes = first["bytes"]

            print(f"[DEBUG] Received audio: {len(audio_bytes)} bytes")

            # Step 2: Convert speech to text

            # Use simple STT - much easier and faster
            st = time.time()
            user_text = transcribe_audio_simple(audio_bytes)
            
            print("[DEBUG] Transcribed text:", user_text)
            print("[DEBUG] STT time:", round(time.time() - st, 3), "sec")
            
            # Check if transcription failed
            if "[ERROR]" in user_text or not user_text.strip():
                await ws.send_json({"error": "Could not understand audio"})
                continue


            # Step 3: Generate AI response with conversation intelligence
            llm_time1 = time.time()
            
            # Update conversation state
            conversation_state["turn_count"] += 1
            
            # Add context with clear role reminder
            context_input = f"Customer said: '{user_text}'"
            context_input += " [REMEMBER: You are Sarah from Lifelong calling THEM about their purchase. Do not respond as the customer.]"
            
            if conversation_state["turn_count"] > 5:
                context_input += f" [Turn {conversation_state['turn_count']} - consider wrapping up soon]"
            
            agent_reply = conversation.predict(input=context_input).strip()
            
            # Clean up the response (remove any system notes)
            if "[Note:" in agent_reply:
                agent_reply = agent_reply.split("[Note:")[0].strip()
            
            # Check for role confusion and fix it
            if any(phrase in agent_reply.lower() for phrase in ["hi sarah", "hello sarah", "thanks for calling", "this is a good time"]):
                # AI is responding as customer - fix this
                agent_reply = "Oh wonderful! I'm so glad to hear you're available to chat. How has your experience been with the pickleball set so far?"
                print("[DEBUG] Fixed role confusion in AI response")
            
            # Add natural pauses to make speech less rushed
            agent_reply = agent_reply.replace("! ", "!... ")  # Pause after excitement
            agent_reply = agent_reply.replace(". ", "... ")   # Longer pauses between sentences
            if not agent_reply.endswith((".", "!", "?")):
                agent_reply += "."  # Ensure proper ending
            
            print("[DEBUG] LLM response time:", round(time.time() - llm_time1, 3), "sec")
            print("[DEBUG] Agent reply:", agent_reply)
            await ws.send_json({"user_text": user_text, "agent_reply": agent_reply})

            # Step 4: Convert AI response to speech
            url = (
                f"wss://api.elevenlabs.io/v1/text-to-speech/"
                f"{VOICE_ID}/stream-input?model_id={MODEL_ID}"
            )
            tts_t = time.time()

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, max_msg_size=0) as el_ws:

                    # initialise connection (key inside JSON)
                    await el_ws.send_json({
                        "text": " ",
                        "xi_api_key": API_KEY,
                        "voice_settings": {
                            "stability": 0.8,         # Much more stable, less rushed
                            "similarity_boost": 0.7,   # Softer, more natural voice
                            "use_speaker_boost": True,
                            "style": 0.3              # More conversational but not too much
                        },
                        "generation_config": {
                            "chunk_length_schedule": [80, 120]  # Longer chunks = smoother speech
                        }
                    })

                    # send LLM reply
                    await el_ws.send_json({"text": agent_reply, "flush": True})
                    await el_ws.send_json({"text": ""})          # end marker

                    # relay audio chunks to the caller
                    async for msg in el_ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            audio_b64 = data.get("audio")
                            if audio_b64:
                                # Convert and send audio to frontend
                                chunk = base64.b64decode(audio_b64)
                                await ws.send_bytes(chunk)
                            if data.get("isFinal"):
                                break
                        elif msg.type is aiohttp.WSMsgType.ERROR:
                            break
            print("[DEBUG] TTS stream gen time:", round(time.time() - tts_t, 3), "sec")

    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await ws.send_json({"error": "Connection error occurred"})
        except:
            pass
    finally:
        # Clean up connection
        try:
            if ws.application_state.name != "DISCONNECTED" and ws.client_state.name != "DISCONNECTED":
                await ws.close()
        except:
            pass


