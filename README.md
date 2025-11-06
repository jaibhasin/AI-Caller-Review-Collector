# AI Caller Review Collector

An AI-powered voice agent system for collecting customer feedback through interactive phone calls. The system uses real-time speech-to-text, natural language processing, and text-to-speech to conduct automated product review conversations.

## 🌟 Features

- **Real-time Voice Communication**: WebSocket-based bidirectional audio streaming
- **AI-Powered Conversations**: Uses Google's Gemini 2.0 Flash for intelligent responses
- **Speech Recognition**: AssemblyAI streaming STT for accurate transcription
- **Natural Voice Synthesis**: ElevenLabs text-to-speech for human-like responses
- **Web-Based Interface**: Modern, responsive UI with real-time audio visualization
- **Conversation Memory**: Maintains context throughout the call using LangChain
- **Call Analytics**: Track call duration, reviews collected, and conversation history

## 🏗️ Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with WebSocket support
- **STT Service**: AssemblyAI streaming speech-to-text
- **LLM**: Google Gemini 2.0 Flash (via LangChain)
- **TTS Service**: ElevenLabs API (Turbo v2.5)
- **Memory**: ConversationBufferMemory for context retention

### Frontend
- **Interface**: Vanilla JavaScript with Web Audio API
- **Communication**: WebSocket for real-time bidirectional streaming
- **Audio Processing**: MediaRecorder API for capturing user audio
- **Visualization**: Real-time audio waveform display

## 📋 Prerequisites

- Python 3.10+
- Node.js (for frontend development, optional)
- API Keys:
  - Google AI API key (for Gemini)
  - ElevenLabs API key (for TTS)
  - AssemblyAI API key (for STT)

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jaibhasin/AI-Caller-Review-Collector.git
   cd AI-Caller-Review-Collector
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY_GOOGLE_AI=your_google_ai_api_key
   ELEVEN_LABS_API_KEY=your_elevenlabs_api_key
   ASSEMBLYAI_API_KEY=your_assemblyai_api_key
   ```

## 🎯 Usage

1. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`

2. **Open the frontend**
   
   Open `frontend/index.html` in a modern web browser (Chrome/Edge recommended for best audio support)

3. **Make a call**
   - Click "Start Call" to establish WebSocket connection
   - Click "Start Recording" to begin speaking
   - The AI will respond with questions about the product
   - Click "End Call" when finished

## 📁 Project Structure

```
AI-Caller-Review-Collector/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── agent_voice.py      # WebSocket endpoint for voice agent
│   └── services/
│       ├── stt_streaming_service.py  # AssemblyAI streaming STT
│       ├── stt2_service.py           # Alternative STT service
│       └── whisper_service.py        # Whisper-based STT (alternative)
├── frontend/
│   ├── index.html              # Main UI
│   ├── script.js               # Client-side WebSocket & audio handling
│   └── styles.css              # UI styling
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (create this)
└── README.md                   # This file
```

## 🔧 API Endpoints

### REST Endpoints
- `GET /` - Health check and API status
- API documentation available at `/docs` (Swagger UI)

### WebSocket Endpoints
- `WS /api/voice-agent` - Real-time voice communication endpoint

## 🎨 Key Technologies

- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: Framework for building LLM applications
- **Google Gemini 2.0**: Advanced language model for conversation
- **AssemblyAI**: Real-time speech recognition
- **ElevenLabs**: High-quality text-to-speech synthesis
- **Web Audio API**: Browser-based audio recording and playback
- **WebSockets**: Real-time bidirectional communication

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY_GOOGLE_AI` | Google AI API key for Gemini | Yes |
| `ELEVEN_LABS_API_KEY` | ElevenLabs API key for TTS | Yes |
| `ASSEMBLYAI_API_KEY` | AssemblyAI API key for STT | Yes |

## 🐛 Troubleshooting

### Audio not recording
- Ensure microphone permissions are granted in browser
- Use HTTPS or localhost (required for microphone access)
- Check browser console for errors

### WebSocket connection fails
- Verify backend is running on port 8000
- Check CORS settings in `app/main.py`
- Ensure firewall allows WebSocket connections

### API errors
- Verify all API keys are correctly set in `.env`
- Check API key quotas and limits
- Review backend logs for detailed error messages

## 📝 License

This project is part of a personal portfolio/learning project.

## 👤 Author

**Jai Bhasin**
- GitHub: [@jaibhasin](https://github.com/jaibhasin)

## 🙏 Acknowledgments

- Google AI for Gemini API
- ElevenLabs for TTS API
- AssemblyAI for STT API
- FastAPI and LangChain communities
