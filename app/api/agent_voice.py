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
    model='gemini-2.0-flash-exp',  # Use the more advanced model
    google_api_key=GOOGLE_API_KEY,
    temperature=0.7,  # Make responses more natural and varied
    max_tokens=100    # Keep responses concise but not too short
)


from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage


API_KEY  = os.getenv("ELEVEN_LABS_API_KEY")
# Using a more conversational voice (this is Rachel - sounds more natural for phone calls)
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel - warm, conversational female voice
MODEL_ID = "eleven_turbo_v2_5"



router = APIRouter()


BASE_PROMPT = """You are Sarah, a friendly customer experience specialist calling to chat about the Lifelong Professional Pickleball Set you purchased. You're genuinely curious about their experience and want to have a natural conversation.

Your personality:
- Warm, conversational, and genuinely interested
- Speak like a real person, not a robot
- Use casual language and natural speech patterns
- Show empathy and enthusiasm
- Keep responses under 30 words but don't sound rushed

Conversation flow:
- Start with a warm greeting and check if it's a good time to chat
- Ask about their overall experience first
- Follow up based on what they say (be a good listener!)
- Ask about specific aspects naturally (comfort, durability, performance)
- If they're happy, ask what they love most
- If they have issues, show understanding and ask for details
- End warmly and thank them for their time

Remember: This should feel like talking to a friend who works in customer service, not a survey bot.

Example responses:
- "Oh that's awesome! What do you love most about them?"
- "I'm so sorry to hear that! Can you tell me what happened?"
- "That's exactly what we were hoping for! How's the grip feeling?"
- "Interesting! Have you noticed any difference in your game?"
- "Thanks for sharing that! Is there anything else you'd like me to know?"
- "Perfect! Well I really appreciate you taking the time to chat with me."

Conversation guidelines:
- If they seem busy or short, offer to call back later
- If they're very positive, focus on what they love most
- If they have complaints, be empathetic and get details
- After 4-5 exchanges, start thinking about wrapping up naturally
- Always end on a positive, grateful note

Current conversation:
{history}
Human: {input}
Assistant:"""

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
        
        
        # Generate initial greeting - make it sound natural and warm
        initial_reply = conversation.predict(input="Hi! This is Sarah calling from Lifelong. How are you doing today? I hope I'm not catching you at a bad time - I just wanted to check in about the pickleball set you ordered from us!").strip()
        await ws.send_json({"user_text": "Call started", "agent_reply": initial_reply}) # where is this sending and what is it sending which format 

        # Stream initial greeting audio
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={MODEL_ID}" # is there a websocket on that end as well , could we access it if this wasnt a websocket
        

        async with aiohttp.ClientSession() as session:   # what is aiohttp ? is it a websocket or what 
            async with session.ws_connect(url, max_msg_size=0) as el_ws: #what is session.ws_connect
                await el_ws.send_json({
                    "text": " ",
                    "xi_api_key": API_KEY,
                    "voice_settings": {
                        "stability": 0.5,        # More stable for natural conversation
                        "similarity_boost": 0.8,  # Slightly less aggressive
                        "use_speaker_boost": True, # Better for phone-like quality
                        "style": 0.2              # Add some conversational style
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
            
            # Analyze customer sentiment from their response
            user_lower = user_text.lower()
            if any(word in user_lower for word in ["love", "great", "awesome", "amazing", "perfect", "excellent"]):
                conversation_state["customer_sentiment"] = "positive"
            elif any(word in user_lower for word in ["hate", "terrible", "awful", "bad", "broken", "disappointed"]):
                conversation_state["customer_sentiment"] = "negative"
            elif any(word in user_lower for word in ["okay", "fine", "alright", "decent"]):
                conversation_state["customer_sentiment"] = "neutral"
            
            # Track topics mentioned
            if any(word in user_lower for word in ["grip", "handle", "comfortable"]):
                if "grip_comfort" not in conversation_state["topics_covered"]:
                    conversation_state["topics_covered"].append("grip_comfort")
            if any(word in user_lower for word in ["durable", "quality", "build", "material"]):
                if "durability" not in conversation_state["topics_covered"]:
                    conversation_state["topics_covered"].append("durability")
            if any(word in user_lower for word in ["game", "play", "performance", "better"]):
                if "performance" not in conversation_state["topics_covered"]:
                    conversation_state["topics_covered"].append("performance")
            
            # Build smarter context for AI
            context_input = user_text
            
            # Add sentiment context
            if conversation_state["customer_sentiment"] == "positive":
                context_input += " [Customer seems happy - focus on what they love most]"
            elif conversation_state["customer_sentiment"] == "negative":
                context_input += " [Customer has concerns - be empathetic and get details]"
            
            # Add topic context to avoid repetition
            if len(conversation_state["topics_covered"]) > 0:
                context_input += f" [Already discussed: {', '.join(conversation_state['topics_covered'])}]"
            
            # Add turn management
            if conversation_state["turn_count"] > 5:
                context_input += f" [Turn {conversation_state['turn_count']} - consider wrapping up soon]"
            
            agent_reply = conversation.predict(input=context_input).strip()
            
            # Clean up the response (remove any system notes)
            if "[Note:" in agent_reply:
                agent_reply = agent_reply.split("[Note:")[0].strip()
            
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
                            "stability": 0.5,        # More stable for natural conversation
                            "similarity_boost": 0.8,  # Good balance
                            "use_speaker_boost": True, # Better for phone-like quality
                            "style": 0.2              # Add some conversational style
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


