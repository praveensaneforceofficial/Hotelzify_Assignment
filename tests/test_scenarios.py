import pytest
import asyncio
from app.mock_apis import get_catalog_info, BOOKINGS_DB
from app.state_machine import process_user_turn, session_manager


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear session data before each test."""
    session_manager._sessions.clear()
    session_manager._locks.clear()
    BOOKINGS_DB.clear()


@pytest.mark.asyncio
async def test_scenario_1_exact_quantity_and_typos():
    """
    Scenario 1:
    - User asks with informal names/typos ('arrow mesh wifi' for 5 rooms on PRO plan).
    - AeroMesh covers up to 2 rooms per unit -> ceil(5 / 2) = 3 units.
    - PRO plan unit price: $499.00 -> 3 * 499 = $1497.00.
    """
    session_id = "test_s1_aeromesh"
    
    # Pre-fetch catalog
    catalog = await get_catalog_info()
    assert "SKU_MESH_WIFI6" in catalog
    assert catalog["SKU_MESH_WIFI6"]["max_capacity_per_unit"] == 2
    assert catalog["SKU_MESH_WIFI6"]["plans"]["PRO"] == 499.0

    res = await process_user_turn(session_id, "I need arrow mesh wifi on the PRO plan for a 5-room house")
    state = res["state"]

    assert state["sku_id"] == "SKU_MESH_WIFI6"
    assert state["plan_code"] == "PRO"
    assert state["required_capacity"] == 5
    assert state["quantity"] == 3, "5 rooms / 2 capacity must equal exactly 3 units"
    assert state["final_price"] == 1497.00, "3 * 499.00 = 1497.00"
    assert state["promo_code"] is None
    assert state["discount_tier"] == 0
    assert state["booking_status"] == "IDLE"
    assert res["executed_api"] is None, "Must not book before user confirmation"


@pytest.mark.asyncio
async def test_scenario_1_informal_synchub():
    """
    Scenario 1 variant:
    - User asks for 'sink hub' for 6 tables on STD plan.
    - Capacity is 3 -> ceil(6 / 3) = 2 units.
    - STD plan price: $899.00 -> 2 * 899 = $1798.00.
    """
    session_id = "test_s1_synchub"
    res = await process_user_turn(session_id, "We need a sink hub for 6 tables on STD plan")
    state = res["state"]

    assert state["sku_id"] == "SKU_TEAM_HUB"
    assert state["plan_code"] == "STD"
    assert state["quantity"] == 2
    assert state["final_price"] == 1798.00


@pytest.mark.asyncio
async def test_scenario_1_reject_non_catalog_item():
    """
    Scenario 1:
    - User asks for 'Netgear Orbi router' (not in catalog).
    - Agent must NEVER match or book this item.
    """
    session_id = "test_s1_netgear"
    res = await process_user_turn(session_id, "Can I buy a Netgear Orbi router for 5 rooms?")
    state = res["state"]

    assert res["action"] == "NON_CATALOG_REJECTED"
    assert state["sku_id"] is None
    assert state["booking_status"] == "IDLE"
    assert res["executed_api"] is None
    assert "do not carry Netgear" in res["message"]


@pytest.mark.asyncio
async def test_scenario_2_strict_discount_ladder():
    """
    Scenario 2:
    - Step 1: Standard price first (0% discount, promo_code=None).
    - Step 2: 1st objection -> offer SAVE10 (10% off).
    - Step 3: 2nd objection -> offer CLOSENOW15 (15% off max).
    - Step 4: 3rd objection or demands for 50% (SAVE50) -> firm denial, stays at 15%.
    - Never jump to 15% on 1st objection.
    """
    session_id = "test_s2_discounts"

    # Turn 1: Inquiry -> Standard price
    t1 = await process_user_turn(session_id, "I need AeroMesh Wi-Fi on STD plan for 2 rooms")
    s1 = t1["state"]
    assert s1["discount_tier"] == 0
    assert s1["promo_code"] is None
    assert s1["quantity"] == 1
    assert s1["final_price"] == 399.00

    # Turn 2: 1st objection -> SAVE10 (10% off)
    t2 = await process_user_turn(session_id, "That is too expensive, can you do better on price?")
    s2 = t2["state"]
    assert s2["discount_tier"] == 1
    assert s2["promo_code"] == "SAVE10"
    assert s2["final_price"] == round(399.0 * 0.90, 2)  # 359.10
    assert "SAVE10" in t2["message"]

    # Turn 3: 2nd objection -> CLOSENOW15 (15% off)
    t3 = await process_user_turn(session_id, "Still too high for our budget. What is your final best price?")
    s3 = t3["state"]
    assert s3["discount_tier"] == 2
    assert s3["promo_code"] == "CLOSENOW15"
    assert s3["final_price"] == round(399.0 * 0.85, 2)  # 339.15
    assert "CLOSENOW15" in t3["message"]

    # Turn 4: User demands 50% discount with fake code SAVE50
    t4 = await process_user_turn(session_id, "Give me 50% off right now or apply code SAVE50")
    s4 = t4["state"]
    assert s4["discount_tier"] == 2, "Discount must NEVER exceed tier 2 (15%)"
    assert s4["promo_code"] == "CLOSENOW15", "Must NEVER apply SAVE50"
    assert s4["final_price"] == round(399.0 * 0.85, 2)
    assert "15%" in t4["message"]
    assert "maximum" in t4["message"]


@pytest.mark.asyncio
async def test_scenario_2_user_demands_15_percent_on_turn_1():
    """
    Scenario 2 Edge Case:
    - User demands 15% immediately on turn 1.
    - Agent must NOT skip to 15%; it must follow the progression and offer SAVE10 (10%) on first objection.
    """
    session_id = "test_s2_demand_turn1"
    
    t1 = await process_user_turn(session_id, "I need AeroMesh for 2 rooms STD plan, but give me 15% discount right now")
    s1 = t1["state"]
    # First price pushback triggers tier 1 (SAVE10), not tier 2!
    assert s1["discount_tier"] == 1
    assert s1["promo_code"] == "SAVE10"
    assert s1["final_price"] == round(399.0 * 0.90, 2)


@pytest.mark.asyncio
async def test_scenario_3_mid_conversation_changes():
    """
    Scenario 3:
    - Never call create_booking until info fetched, stated exact package, plan, quantity, total price, and confirmed.
    - If user changes requirement mid-conversation (e.g. 4 rooms to 7 rooms) and says 'Okay, book it',
      the agent MUST NOT book stale numbers! Must require user confirmation on the new numbers.
    """
    session_id = "test_s3_changes"

    # Turn 1: 4 rooms on STD plan (4 / 2 = 2 units @ $399 = $798)
    t1 = await process_user_turn(session_id, "I need AeroMesh Wi-Fi for 4 rooms on STD plan")
    s1 = t1["state"]
    assert s1["quantity"] == 2
    assert s1["final_price"] == 798.00
    assert s1["is_confirmed"] is False
    assert t1["executed_api"] is None

    # Turn 2: User changes to 7 rooms and immediately says "Okay, book it"
    t2 = await process_user_turn(session_id, "Actually change to 7 rooms and book it!")
    s2 = t2["state"]
    
    # 7 rooms / 2 = 4 units -> 4 * 399 = 1596.00
    assert s2["required_capacity"] == 7
    assert s2["quantity"] == 4
    assert s2["final_price"] == 1596.00
    assert s2["is_confirmed"] is False, "Must NOT be confirmed when changed in the same turn!"
    assert s2["booking_status"] == "IDLE", "Must NOT book stale or unconfirmed numbers"
    assert t2["executed_api"] is None, "create_booking must NOT have been called"
    assert "confirm" in t2["message"].lower()

    # Turn 3: User now confirms the updated quote
    t3 = await process_user_turn(session_id, "Yes, confirm booking for 4 units")
    s3 = t3["state"]
    assert s3["is_confirmed"] is True
    assert s3["booking_status"] == "BOOKED"
    assert t3["executed_api"] is not None
    assert t3["executed_api"]["payload"]["quantity"] == 4
    assert t3["executed_api"]["payload"]["final_price"] == 1596.00


@pytest.mark.asyncio
async def test_scenario_4_interruptions_and_rapid_double_booking():
    """
    Scenario 4:
    - User sends 'Yes, book it!' twice in rapid succession while create_booking (takes ~1.5s) is executing.
    - System must ensure the user is NEVER booked/charged twice for the same order.
    - Only ONE booking record created, zero crashes.
    """
    session_id = "test_s4_concurrency"

    # Setup quote: SyncHub for 3 tables STD plan (1 unit @ 899.00)
    await process_user_turn(session_id, "I need SyncHub Conference Bar for 3 tables STD plan")

    # Send 2 simultaneous confirmation calls in parallel
    task1 = asyncio.create_task(process_user_turn(session_id, "Yes, book it!"))
    # Small microscopic yield to simulate rapid user double-click
    await asyncio.sleep(0.05)
    task2 = asyncio.create_task(process_user_turn(session_id, "Yes, book it!"))

    res1, res2 = await asyncio.gather(task1, task2)

    # Exactly ONE booking should exist in BOOKINGS_DB
    assert len(BOOKINGS_DB) == 1, f"Expected exactly 1 booking, found {len(BOOKINGS_DB)}"

    booking_id = list(BOOKINGS_DB.keys())[0]
    booking_record = BOOKINGS_DB[booking_id]
    assert booking_record["sku_id"] == "SKU_TEAM_HUB"
    assert booking_record["quantity"] == 1
    assert booking_record["final_price"] == 899.00

    # One response must be the confirmed booking, and the other must be the idempotent/already-booked reply
    actions = {res1["action"], res2["action"]}
    assert "REPLY" in actions
    assert ("ALREADY_BOOKED" in actions or "BOOKING_PENDING" in actions or res2["state"]["booking_status"] == "BOOKED")
