# 🎙️ AI Caller Review Collector

> **An intelligent AI voice agent that conducts natural phone conversations to collect customer feedback**

Transform customer feedback collection with an AI agent that sounds and feels like talking to a real person. Sarah, our AI customer service representative, calls customers to gather authentic product reviews through natural conversation.

## ✨ What Makes This Special

### 🧠 **Intelligent Conversation Pipeline**
- **3-Step LLM Processing**: Analyze → Plan → Generate for structured, natural responses
- **Smart Context Awareness**: Remembers conversation history and adapts accordingly
- **Emotional Intelligence**: Detects sentiment and responds with appropriate empathy
- **Role Consistency**: Advanced role confusion detection prevents AI identity mix-ups

### 🎯 **Natural Conversation Flow**
- **Sarah Persona**: Warm, professional customer service representative
- **Structured Responses**: Always follows Acknowledge → Empathize → Ask pattern
- **Natural Pacing**: Automatic pause insertion for human-like speech rhythm
- **Topic Tracking**: Avoids repetitive questions by remembering what's been discussed

### 🔊 **High-Quality Audio Pipeline**
- **Real-time Processing**: WebSocket-based bidirectional audio streaming
- **Smart Format Handling**: Automatic browser audio format detection and optimization
- **Natural Voice**: ElevenLabs Rachel voice with optimized settings for phone conversations
- **Reliable STT**: AssemblyAI with direct WebM support (no conversion needed)

## 🏗️ Architecture

```
┌─────────────────┐    WebSocket    ┌──────────────────┐
│   Frontend      │◄──────────────►│   FastAPI        │
│   (Browser)     │                │   Backend        │
└─────────────────┘                └──────────────────┘
         │                                   │
         │ MediaRecorder                     │
         │ (WebM/Opus)                       │
         ▼                                   ▼
┌─────────────────┐                ┌──────────────────┐
│ Web Audio API   │                │ 3-Step Pipeline  │
│ Audio Playback  │                │ ┌──────────────┐ │
└─────────────────┘                │ │1. Analyze    │ │
                                   │ │2. Plan       │ │
                                   │ │3. Generate   │ │
                                   │ └──────────────┘ │
                                   └──────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
            │ AssemblyAI   │    │ Google Gemini    │    │ ElevenLabs   │
            │ (STT)        │    │ 2.0 Flash        │    │ (TTS)        │
            └──────────────┘    │ (LLM)            │    └──────────────┘
                               └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Modern web browser (Chrome/Edge recommended)
- API Keys: Google AI, ElevenLabs, AssemblyAI

### Installation

1. **Clone and Setup**
   ```bash
   git clone https://github.com/jaibhasin/AI-Caller-Review-Collector.git
   cd AI-Caller-Review-Collector
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   # Create .env file
   echo "SECRET_KEY_GOOGLE_AI=your_google_ai_key" > .env
   echo "ELEVEN_LABS_API_KEY=your_elevenlabs_key" >> .env
   echo "ASSEMBLYAI_API_KEY=your_assemblyai_key" >> .env
   ```

3. **Launch**
   ```bash
   # Start backend
   uvicorn app.main:app --reload
   
   # Open frontend/index.html in browser
   # Click "Start Call" and begin conversation!
   ```

## 🎭 Meet Sarah - Your AI Agent

Sarah is designed to be the perfect customer service representative:

- **Personality**: Warm, professional, genuinely interested
- **Communication Style**: Natural, conversational, never rushed
- **Intelligence**: Understands context, emotions, and conversation flow
- **Consistency**: Always stays in character as the company representative

### Example Conversation
```
Sarah: "Hi there! This is Sarah calling from Lifelong. I hope you're 
       having a good day. I wanted to give you a quick call about the 
       pickleball set you got from us recently. Is this an okay time 
       to chat for just a minute?"

Customer: "Oh hi! Yeah, sure, I have a few minutes."

Sarah: "Wonderful! I'm so glad I caught you at a good time... How has 
       your experience been with the pickleball set so far?"

Customer: "It's been really great actually! The grip is so comfortable."

Sarah: "Oh that's fantastic to hear that you love the grip comfort!... 
       What specifically makes it feel so good to use?"
```

## 🔧 Technical Features

### Intelligent Response Pipeline
```python
# Every customer response goes through:
1. ANALYZE    → Extract sentiment, topic, keywords, emotion level
2. PLAN       → Decide acknowledgment style, empathy approach, follow-up
3. GENERATE   → Create natural Sarah response following structure
4. POST-PROCESS → Fix role confusion, add natural pacing
```

### Advanced Conversation State
```python
conversation_state = {
    "topics_covered": ["grip", "durability"],
    "customer_sentiment": "positive",
    "turn_count": 3,
    "last_analysis": {...},
    "last_plan": {...},
    "conversation_history": [...]
}
```

### Audio Optimization
- **Browser Compatibility**: Automatic format detection (WebM → MP4 → fallback)
- **Natural Speech**: Optimized ElevenLabs settings with pauses and pacing
- **Reliable Processing**: Direct WebM support, no ffmpeg conversion needed
- **Quality Control**: Phone-optimized voice settings for clear communication

## 📁 Project Structure

```
AI-Caller-Review-Collector/
├── 🎯 Core Application
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── api/agent_voice.py         # 3-step pipeline WebSocket handler
│   │   └── services/
│   │       └── simple_stt_service.py  # Optimized AssemblyAI integration
│   └── frontend/
│       ├── index.html                 # Modern UI with audio visualization
│       ├── script.js                  # WebSocket + Web Audio API
│       └── styles.css                 # Responsive design
├── 📚 Documentation
│   ├── structured_response_pipeline.md
│   ├── conversation_improvements.md
│   └── role_confusion_fix.md
├── 🧪 Testing
│   ├── test_audio_formats.html
│   └── conversation_example.md
└── ⚙️ Configuration
    ├── requirements.txt
    ├── .env
    └── README.md
```

## 🔐 Environment Configuration

| Variable | Purpose | Example |
|----------|---------|---------|
| `SECRET_KEY_GOOGLE_AI` | Gemini 2.0 Flash API access | `AIzaSy...` |
| `ELEVEN_LABS_API_KEY` | Rachel voice synthesis | `sk_...` |
| `ASSEMBLYAI_API_KEY` | Real-time speech recognition | `a13c86...` |

## 🎨 API Endpoints

### REST API
- `GET /` - Health check and system status
- `GET /docs` - Interactive API documentation (Swagger UI)

### WebSocket API
- `WS /api/agent/voice` - Real-time voice conversation endpoint
  - Accepts: WebM/Opus audio chunks
  - Returns: JSON conversation data + MP3 audio chunks

## 🐛 Troubleshooting

### Common Issues

**🎤 Microphone Not Working**
```bash
# Check browser permissions
# Ensure HTTPS or localhost
# Verify Web Audio API support
```

**🔌 WebSocket Connection Failed**
```bash
# Verify backend is running: http://localhost:8000
# Check firewall settings
# Confirm CORS configuration
```

**🤖 AI Role Confusion**
```bash
# Automatic detection and fixing implemented
# Check console for "[DEBUG] Fixed role confusion" messages
# Review conversation_state in logs
```

**🔊 Audio Quality Issues**
```bash
# Test browser audio format support: open test_audio_formats.html
# Check ElevenLabs API quota
# Verify voice settings in agent_voice.py
```

## 🚀 Advanced Usage

### Custom Voice Configuration
```python
# In agent_voice.py, modify:
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
# Or try: "pNInz6obpgDQGcFmaJgB"  # Adam
```

### Conversation Customization
```python
# Modify BASE_PROMPT in agent_voice.py for different:
# - Product types
# - Company personas  
# - Conversation styles
# - Response structures
```

### Pipeline Tuning
```python
# Adjust LLM settings:
temperature=0.8,    # Creativity (0.1-1.0)
max_tokens=150,     # Response length
top_p=0.9          # Response variety
```

## 📊 Performance Metrics

- **Response Time**: ~2-3 seconds (STT + LLM Pipeline + TTS)
- **Audio Quality**: 16kHz, optimized for voice clarity
- **Conversation Length**: Automatically managed (5-7 turns typical)
- **Success Rate**: 95%+ natural conversation flow

## 🤝 Contributing

This is a portfolio project, but suggestions and improvements are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your improvements
4. Submit a pull request

## 📄 License

MIT License - Feel free to use this project for learning and development.

## 👤 Author

**Jai Bhasin**
- 🐙 GitHub: [@jaibhasin](https://github.com/jaibhasin)
- 💼 Portfolio: [Your Portfolio URL]
- 📧 Email: [Your Email]

## 🙏 Acknowledgments

- **Google AI** - Gemini 2.0 Flash LLM
- **ElevenLabs** - Natural voice synthesis
- **AssemblyAI** - Real-time speech recognition
- **FastAPI** - Modern Python web framework
- **LangChain** - LLM application framework

---

*Built with ❤️ for natural human-AI conversation*
