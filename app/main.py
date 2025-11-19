from fastapi import FastAPI # main class to create webapp 

from app.api.agent_voice import router as agent_voice_router # router to group endpoints , so they become active 

app = FastAPI(title="AI Voice Review Collector", description="AI-powered voice agent for collecting customer feedback")

# Add CORS middleware for frontend integration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_voice_router, prefix="/api", tags=["Agent Voice"])

@app.get("/")
async def root():
    return {"message": "AI Voice Review Collector API is running!", "status": "active"}
