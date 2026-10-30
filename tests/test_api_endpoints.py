import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_api_catalog_endpoint():
    """Verify GET /api/catalog returns 10 packages with required attributes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/catalog")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 10
        assert "SKU_AIRPODS_PRO2" in data
        assert "SKU_MESH_WIFI6" in data
        assert "SKU_TEAM_HUB" in data


@pytest.mark.asyncio
async def test_api_chat_flow_and_logs():
    """Verify full chat turn-by-turn endpoint with live log inspection."""
    session_id = "test_endpoint_session"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Reset session
        await client.post("/api/reset", json={"session_id": session_id})

        # Turn 1: Product inquiry
        res1 = await client.post("/api/chat", json={
            "session_id": session_id,
            "message": "I need arrow mesh wifi for 4 rooms on STD plan"
        })
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["state"]["quantity"] == 2
        assert d1["state"]["final_price"] == 798.00
        assert d1["state"]["booking_status"] == "IDLE"

        # Turn 2: Confirm booking
        res2 = await client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Yes, please confirm booking"
        })
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["state"]["booking_status"] == "BOOKED"
        assert d2["executed_api"] is not None
        assert d2["executed_api"]["api"] == "POST /api/bookings"
        assert d2["executed_api"]["payload"]["quantity"] == 2


@pytest.mark.asyncio
async def test_api_bookings_direct_endpoint():
    """Verify POST /api/bookings direct execution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/bookings", json={
            "sku_id": "SKU_MESH_WIFI6",
            "plan_code": "PRO",
            "quantity": 3,
            "promo_code": "CLOSENOW15",
            "final_price": 1272.45
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "CONFIRMED"
        assert data["booking_id"].startswith("BKG-")
        assert data["quantity"] == 3
        assert data["promo_code"] == "CLOSENOW15"
