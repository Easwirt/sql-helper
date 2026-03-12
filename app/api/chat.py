"""Chat endpoint for the AI Data Analyst."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm_provider.agent import run_agent

router = APIRouter()

# Simple in-memory session store (no thread safety needed for PoC)
conversation_store: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    message: str
    role: str = "controller"
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list = []
    session_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    # Load previous context for this session
    context = []
    if request.session_id and request.session_id in conversation_store:
        context = conversation_store[request.session_id][-6:]  # Last 6 messages
    
    # Run the agent
    result = await run_agent(
        request.message,
        role=request.role,
        context_messages=context,
    )
    
    # Save user message to session
    if request.session_id:
        if request.session_id not in conversation_store:
            conversation_store[request.session_id] = []
        conversation_store[request.session_id].append({
            "role": "user", 
            "content": request.message[:1000]
        })
        # Keep only last 12 messages
        conversation_store[request.session_id] = conversation_store[request.session_id][-12:]
    
    return ChatResponse(
        reply=result["reply"],
        tool_calls=result["tool_calls"],
        session_id=request.session_id,
    )