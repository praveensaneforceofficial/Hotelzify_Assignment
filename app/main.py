from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.mock_apis import get_catalog_info, create_booking, API_CALL_LOGS, BOOKINGS_DB
from app.state_machine import session_manager
from app.agent import sales_agent
from app.config import PORT, HOST

app = FastAPI(
    title="Hotelzify AI Sales Agent",
    description="100% Accuracy AI Sales Bot with Deterministic Guardrails & Concurrency Safety",
    version="1.0.0"
)

# Request Models
class ChatRequest(BaseModel):
    session_id: str = "default_session"
    message: str

class BookingRequest(BaseModel):
    sku_id: str
    plan_code: str
    quantity: int
    promo_code: Optional[str] = None
    final_price: float

class ResetRequest(BaseModel):
    session_id: str = "default_session"


# Static files mount
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serves the interactive web UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Hotelzify Sales Agent API is running. UI index.html not yet built."}


# Core API Endpoints specified in assignment
@app.get("/api/catalog")
async def get_catalog(query: Optional[str] = None):
    """
    1. GET API - Fetch available packages, capacities, and pricing.
    """
    return await get_catalog_info(query=query)


@app.post("/api/bookings")
async def post_booking(req: BookingRequest):
    """
    2. POST API - Create the final booking after discussing with user.
    """
    try:
        booking = await create_booking(
            sku_id=req.sku_id,
            plan_code=req.plan_code,
            quantity=req.quantity,
            promo_code=req.promo_code,
            final_price=req.final_price
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Conversational endpoint: handles user messages turn-by-turn.
    Returns agent reply, verified state, and any executed API calls.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    result = await sales_agent.handle_message(
        session_id=req.session_id,
        user_message=req.message
    )
    # Return per-session clean API logs (1 GET on inquiry, 1 POST on booking)
    session_logs = result["state"].get("session_api_logs", [])
    return {
        "reply": result["message"],
        "state": result["state"],
        "executed_api": result.get("executed_api"),
        "api_call_logs": session_logs
    }


@app.get("/api/logs")
async def get_logs():
    """Returns all recorded API call logs."""
    return {"logs": API_CALL_LOGS, "total_bookings": len(BOOKINGS_DB)}


@app.post("/api/reset")
async def reset_session_endpoint(req: ResetRequest):
    """Resets session state for a fresh test run."""
    session_manager.reset_session(req.session_id)
    return {"status": "SUCCESS", "message": f"Session '{req.session_id}' reset successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
