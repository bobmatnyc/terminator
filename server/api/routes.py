"""REST API routes for TermPilot."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["terminal"])

@router.get("/sessions")
async def list_sessions():
    """List all terminal sessions."""
    raise NotImplementedError("list_sessions not yet implemented")

@router.post("/sessions")
async def create_session():
    """Create a new terminal session."""
    raise NotImplementedError("create_session not yet implemented")

@router.post("/sessions/{session_id}/send")
async def send_to_session(session_id: str):
    """Send text to a terminal session."""
    raise NotImplementedError("send_to_session not yet implemented")
