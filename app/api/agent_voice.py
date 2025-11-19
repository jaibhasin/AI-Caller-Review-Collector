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

# Optimized single-pass response generation

def fix_role_confusion(response: str) -> str:
    """Fix any role confusion in the AI response"""
    confusion_phrases = ["hi sarah", "hello sarah", "thanks for calling", "this is a good time", "thanks so much for calling"]
    
    if any(phrase in response.lower() for phrase in confusion_phrases):
        print("[DEBUG] Fixed role confusion in AI response")
        return "Oh wonderful! I'm so glad to hear you're available to chat. How has your experience been with the pickleball set so far?"
    
    return response

def apply_natural_pacing(response: str) -> str:
    """Add natural pauses to make speech less rushed"""
    # Add pauses after excitement and between sentences
    response = response.replace("! ", "!... ")  # Pause after excitement
    response = response.replace(". ", "... ")   # Longer pauses between sentences
    
    # Ensure proper ending
    if not response.endswith((".", "!", "?")):
        response += "."
        
    return response


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
    
    # Track conversation state (simplified for speed)
    conversation_state = {
        "topics_covered": [],
        "customer_sentiment": "neutral", 
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
            stt_result = transcribe_audio_simple(audio_bytes)
            
            # Handle new detailed STT response
            if isinstance(stt_result, dict):
                user_text = stt_result["text"]
                stt_upload_time = round(stt_result.get("upload_time", 0))
                stt_processing_time = round(stt_result.get("processing_time", 0))
                stt_total_time = round(stt_result.get("total_time", 0))
                audio_duration = stt_result.get("audio_duration", 0)
                efficiency_ratio = stt_result.get("efficiency_ratio", 0)
            else:
                # Fallback for old format
                user_text = stt_result
                stt_upload_time = 0
                stt_processing_time = 0
                stt_total_time = 0
                audio_duration = 0
                efficiency_ratio = 0
            
            print("[DEBUG] Transcribed text:", user_text)
            print("[DEBUG] STT breakdown - Upload:", stt_upload_time, "ms, Processing:", stt_processing_time, "ms, Total:", stt_total_time, "ms")
            
            # Check if transcription failed
            if "[ERROR]" in user_text or not user_text.strip():
                await ws.send_json({"error": "Could not understand audio"})
                continue


            # Step 3: Generate AI response with optimized single LLM call
            llm_time1 = time.time()
            
            # Update conversation state
            conversation_state["turn_count"] += 1
            
            print(f"[DEBUG] Single-pass LLM call for turn {conversation_state['turn_count']}")
            
            # ONE-PASS optimized prompt that does analysis + planning + generation internally
            optimized_prompt = f"""
You are Sarah, a warm customer service rep from Lifelong calling about their pickleball set purchase.

CONTEXT:
- Customer just said: "{user_text}"
- Turn #{conversation_state['turn_count']} of conversation
- Topics already discussed: {conversation_state['topics_covered']}
- Previous sentiment: {conversation_state['customer_sentiment']}

INSTRUCTIONS:
1. Internally analyze their sentiment, topic, and emotion level
2. Internally plan your acknowledgment style and empathy approach  
3. Generate ONE natural response that:
   - Acknowledges what they specifically said
   - Shows appropriate empathy/enthusiasm
   - Asks a relevant follow-up question
   - Sounds conversational, not robotic
   - Is 1-2 sentences maximum

IMPORTANT:
- YOU are Sarah calling THEM (don't respond as the customer)
- Use their exact words when acknowledging
- Match their energy level appropriately
- If turn 6+, consider wrapping up naturally

Return ONLY the final conversational response, nothing else:"""

            # Single LLM call replaces the entire 3-step pipeline
            response = llm.invoke(optimized_prompt)
            agent_reply = response.content.strip()
            
            print(f"[DEBUG] Generated response: {agent_reply}")
            
            # Post-processing pipeline (keep these for quality)
            agent_reply = fix_role_confusion(agent_reply)
            agent_reply = apply_natural_pacing(agent_reply)
            
            # Simple conversation state updates (without complex analysis)
            # Update sentiment based on simple keyword detection
            user_lower = user_text.lower()
            if any(word in user_lower for word in ["love", "great", "awesome", "amazing", "perfect"]):
                conversation_state["customer_sentiment"] = "positive"
            elif any(word in user_lower for word in ["hate", "terrible", "awful", "bad", "broken"]):
                conversation_state["customer_sentiment"] = "negative"
            
            # Update topics based on simple keyword detection
            if any(word in user_lower for word in ["grip", "handle", "comfortable"]) and "grip" not in conversation_state["topics_covered"]:
                conversation_state["topics_covered"].append("grip")
            if any(word in user_lower for word in ["durable", "quality", "build"]) and "durability" not in conversation_state["topics_covered"]:
                conversation_state["topics_covered"].append("durability")
            if any(word in user_lower for word in ["game", "play", "performance"]) and "performance" not in conversation_state["topics_covered"]:
                conversation_state["topics_covered"].append("performance")
            
            llm_time = round((time.time() - llm_time1) * 1000)  # Convert to milliseconds
            
            print("[DEBUG] Optimized LLM time:", llm_time, "ms")
            print("[DEBUG] Conversation state:", conversation_state)
            print("[DEBUG] Final agent reply:", agent_reply)
            
            # Send conversation data with detailed performance metrics
            await ws.send_json({
                "user_text": user_text, 
                "agent_reply": agent_reply,
                "metrics": {
                    "stt_total_time": stt_total_time,
                    "stt_upload_time": stt_upload_time,
                    "stt_processing_time": stt_processing_time,
                    "llm_time": llm_time,
                    "turn_count": conversation_state["turn_count"],
                    "audio_size": len(audio_bytes),
                    "audio_duration": audio_duration,
                    "efficiency_ratio": efficiency_ratio
                }
            })

            # Step 4: Convert AI response to speech
            url = (
                f"wss://api.elevenlabs.io/v1/text-to-speech/"
                f"{VOICE_ID}/stream-input?model_id={MODEL_ID}"
            )
            tts_start = time.time()

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
            tts_time = round((time.time() - tts_start) * 1000)  # Convert to milliseconds
            print("[DEBUG] TTS stream gen time:", tts_time, "ms")
            
            # Send TTS completion metrics
            await ws.send_json({
                "metrics": {
                    "tts_time": tts_time,
                    "total_response_time": stt_time + llm_time + tts_time
                }
            })

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


