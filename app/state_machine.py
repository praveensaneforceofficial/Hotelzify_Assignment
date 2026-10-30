import asyncio
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.config import DISCOUNT_TIERS, MAX_DISCOUNT_TIER
from app.mock_apis import CATALOG, create_booking, get_catalog_info
from app.catalog_service import (
    calculate_units_needed,
    resolve_sku_from_text,
    resolve_plan_code,
    extract_rooms_or_capacity
)


class SessionState(BaseModel):
    session_id: str
    sku_id: Optional[str] = None
    product_name: Optional[str] = None
    plan_code: Optional[str] = None
    required_capacity: Optional[int] = None
    quantity: int = 0
    unit_price: float = 0.0
    currency: str = "INR"
    discount_tier: int = 0
    promo_code: Optional[str] = None
    discount_rate: float = 0.0
    final_price: float = 0.0
    
    # State validation flags
    is_quote_presented: bool = False
    is_confirmed: bool = False
    booking_status: str = "IDLE"  # "IDLE", "IN_PROGRESS", "BOOKED"
    booking_result: Optional[Dict[str, Any]] = None
    
    # Conversation tracking
    history: List[Dict[str, str]] = Field(default_factory=list)
    rejection_reason: Optional[str] = None


class SessionManager:
    """
    Thread-safe & async-safe session manager with per-session locks.
    Guarantees concurrency safety (Scenario 4) and deterministic business rules.
    """
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def get_or_create_session(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def reset_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._locks:
            del self._locks[session_id]


# Global session manager instance
session_manager = SessionManager()


def is_price_objection(message: str) -> bool:
    """Detects if user is negotiating or objecting to price."""
    objection_patterns = [
        r"too expensive", r"too high", r"price is high", r"costly",
        r"can you do better", r"best price", r"discount", r"cheaper",
        r"lower the price", r"cut the price", r"give me a deal",
        r"give me \d+%", r"apply code", r"save\d+", r"any offer",
        r"budget is tight", r"less expensive", r"better offer",
        r"can i get 15", r"give 15", r"give me 15"
    ]
    msg_clean = message.lower()
    return any(re.search(p, msg_clean) for p in objection_patterns)


def is_explicit_confirmation(message: str) -> bool:
    """Detects explicit user agreement to book."""
    confirm_patterns = [
        r"\b(?:yes|yeah|yep)\b.*\b(?:book|confirm|proceed|buy|take it|go ahead)\b",
        r"\bbook it\b",
        r"\bconfirm booking\b",
        r"\bproceed with booking\b",
        r"\bconfirm it\b",
        r"\bgo ahead and book\b",
        r"\blet's book it\b",
        r"\bplease book\b",
        r"^yes\b",
        r"^confirm\b",
        r"^book\b"
    ]
    msg_clean = message.lower().strip()
    return any(re.search(p, msg_clean) for p in confirm_patterns)


def recalculate_pricing(state: SessionState):
    """
    Deterministic pricing formula:
    Price = Unit Price * Quantity * (1 - Discount Rate)
    """
    if not state.sku_id or not state.plan_code or state.quantity <= 0:
        state.final_price = 0.0
        return

    product = CATALOG[state.sku_id]
    state.product_name = product["name"]
    state.unit_price = product["plans"].get(state.plan_code, 0.0)
    
    tier_info = DISCOUNT_TIERS[state.discount_tier]
    state.promo_code = tier_info["code"]
    state.discount_rate = tier_info["rate"]

    raw_total = state.unit_price * state.quantity
    discount_amount = raw_total * state.discount_rate
    state.final_price = round(raw_total - discount_amount, 2)


async def process_user_turn(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    Core Deterministic State Transition Engine.
    Executes all 4 Scenario rules with mathematical precision and concurrency safety.
    """
    lock = session_manager.get_lock(session_id)
    
    async with lock:
        state = session_manager.get_or_create_session(session_id)
        state.history.append({"role": "user", "content": user_message})

        # --- SCENARIO 4: CONCURRENCY / IDEMPOTENCY CHECK ---
        if state.booking_status == "BOOKED":
            res = state.booking_result
            return {
                "action": "ALREADY_BOOKED",
                "message": f"Your order is already confirmed! Booking ID: {res['booking_id']} for {res['quantity']} unit(s) of {res['product_name']} ({res['plan_code']}) at ₹{res['final_price']:,.2f}.",
                "state": state.model_dump(),
                "executed_api": None
            }

        if state.booking_status == "IN_PROGRESS":
            return {
                "action": "BOOKING_PENDING",
                "message": "Your booking is currently being processed. Please hold on a moment!",
                "state": state.model_dump(),
                "executed_api": None
            }

        # --- SCENARIO 1: CATALOG LOOKUP & CAPACITY PARSING ---
        detected_sku = resolve_sku_from_text(user_message)
        detected_rooms = extract_rooms_or_capacity(user_message)
        from app.catalog_service import extract_explicit_units
        detected_units = extract_explicit_units(user_message)

        # Core Flow Step 1: Call GET API (get_catalog_info) to fetch available packages, capacities, and pricing
        await get_catalog_info(query=detected_sku)

        # Check for unknown / non-catalog request
        msg_lower = user_message.lower()
        if any(brand in msg_lower for brand in ["netgear", "orbi", "eero", "google nest", "tp-link", "cisco"]):
            state.rejection_reason = "Product not in catalog"
            reply = "I apologize, but we do not carry Netgear or other third-party routers in our official catalog. Our flagship solution is the AeroMesh Wi-Fi 6E Home Pack. Would you like details on AeroMesh instead?"
            state.history.append({"role": "assistant", "content": reply})
            return {
                "action": "NON_CATALOG_REJECTED",
                "message": reply,
                "state": state.model_dump(),
                "executed_api": None
            }

        # --- SCENARIO 3: MID-CONVERSATION DIRTY-CHECK ---
        is_modified = False
        
        # Check SKU modification
        if detected_sku and detected_sku != state.sku_id:
            state.sku_id = detected_sku
            is_modified = True

        # Check Plan modification
        if state.sku_id:
            detected_plan = resolve_plan_code(user_message, state.sku_id)
            if not state.plan_code or (detected_plan != state.plan_code and any(p in user_message.upper() for p in ["STD", "PRO", "CARE", "STANDARD"])):
                state.plan_code = detected_plan
                is_modified = True

        # Check Capacity / Rooms modification
        if detected_rooms and detected_rooms != state.required_capacity:
            state.required_capacity = detected_rooms
            is_modified = True

        # If SKU and Capacity exist, update quantity
        if state.sku_id and state.required_capacity:
            product = CATALOG[state.sku_id]
            cap_per_unit = product["max_capacity_per_unit"]
            new_qty = calculate_units_needed(state.required_capacity, cap_per_unit)
            if new_qty != state.quantity:
                state.quantity = new_qty
                is_modified = True
        elif state.sku_id and state.required_capacity is None and CATALOG[state.sku_id]["max_capacity_per_unit"] == 1 and state.quantity == 0:
            # For 1-person/1-room personal items like AirPods Pro, default to 1 unit if unspecified
            state.required_capacity = 1
            state.quantity = 1
            is_modified = True
        elif detected_units and detected_units != state.quantity:
            # User specified different units directly without stating rooms
            state.quantity = detected_units
            is_modified = True

        # If any core parameter modified mid-conversation, invalidate confirmation
        if is_modified:
            state.is_confirmed = False
            state.is_quote_presented = True
            recalculate_pricing(state)

        # --- SCENARIO 2: STRICT DISCOUNT RULES ---
        objection = is_price_objection(user_message)
        discount_offered = False

        if objection:
            if state.discount_tier == 0:
                # 1st objection: offer SAVE10 (10% off)
                state.discount_tier = 1
                discount_offered = True
            elif state.discount_tier == 1:
                # 2nd objection: offer CLOSENOW15 (15% off - absolute maximum)
                state.discount_tier = 2
                discount_offered = True
            else:
                # 3rd+ objection: strictly capped at tier 2
                discount_offered = False

            recalculate_pricing(state)
            state.is_confirmed = False  # Price changed, needs new confirmation

        # --- SCENARIO 3: CONFIRMATION & BOOKING TRIGGER ---
        user_confirmed = is_explicit_confirmation(user_message)

        # Check if booking can proceed
        # RULE: Must have SKU, Plan, Qty, Price, Quote Presented, and User Confirmed
        # AND if user modified requirement in the same turn, they CANNOT confirm until updated numbers are shown!
        can_execute_booking = (
            user_confirmed and 
            not is_modified and 
            state.sku_id and 
            state.plan_code and 
            state.quantity > 0 and 
            state.final_price > 0 and 
            state.is_quote_presented
        )

        executed_api = None

        if can_execute_booking:
            # Mark IN_PROGRESS
            state.booking_status = "IN_PROGRESS"
            try:
                # Execute create_booking (with 1.5s simulated network delay)
                booking = await create_booking(
                    sku_id=state.sku_id,
                    plan_code=state.plan_code,
                    quantity=state.quantity,
                    promo_code=state.promo_code,
                    final_price=state.final_price
                )
                state.booking_status = "BOOKED"
                state.booking_result = booking
                state.is_confirmed = True
                
                promo_text = f" with code {state.promo_code}" if state.promo_code else " (standard pricing)"
                reply = (
                    f"🎉 Booking successfully confirmed! Your booking ID is {booking['booking_id']}. "
                    f"Order details: {state.quantity} unit(s) of {booking['product_name']} "
                    f"on the {state.plan_code} plan{promo_text} for a final total of ₹{state.final_price:,.2f}. "
                    f"Thank you for choosing Hotelzify!"
                )
                executed_api = {
                    "api": "POST /api/bookings",
                    "payload": {
                        "sku_id": state.sku_id,
                        "plan_code": state.plan_code,
                        "quantity": state.quantity,
                        "promo_code": state.promo_code,
                        "final_price": state.final_price
                    },
                    "response": booking
                }
            except Exception as e:
                state.booking_status = "IDLE"
                reply = f"Error processing booking: {str(e)}"
        
        elif user_confirmed and is_modified:
            # Scenario 3 Edge Case: User said "Change to 7 rooms and book it"
            # Must NOT book yet! Must confirm updated quote first.
            state.is_confirmed = False
            product = CATALOG[state.sku_id]
            reply = (
                f"I noticed you updated your requirement to {state.required_capacity} rooms. "
                f"For {state.required_capacity} rooms, you will need {state.quantity} unit(s) of {product['name']} "
                f"({product['max_capacity_per_unit']} rooms per unit) on the {state.plan_code} plan. "
                f"Your updated total is ₹{state.final_price:,.2f}"
                + (f" with promo code {state.promo_code}." if state.promo_code else ".")
                + " Before I complete the booking, please confirm if you're happy with these updated details!"
            )
        
        elif discount_offered:
            # Sales negotiation reply
            tier_info = DISCOUNT_TIERS[state.discount_tier]
            if state.discount_tier == 1:
                reply = (
                    f"I completely understand budget is essential. Because you're outfitting {state.required_capacity or state.quantity} room(s) today, "
                    f"I can offer our courtesy code **{tier_info['code']}** for 10% off! "
                    f"This reduces your total for {state.quantity} unit(s) of {state.product_name} ({state.plan_code}) "
                    f"from ₹{state.unit_price * state.quantity:,.2f} down to **₹{state.final_price:,.2f}**. "
                    f"Shall I go ahead and book this for you?"
                )
            elif state.discount_tier == 2:
                reply = (
                    f"I really want to earn your business. I'm authorized to unlock our executive closing code **{tier_info['code']}** "
                    f"for 15% off—this is our absolute maximum authorized discount. "
                    f"Your final price for {state.quantity} unit(s) of {state.product_name} ({state.plan_code}) "
                    f"is now just **₹{state.final_price:,.2f}**! "
                    f"Can I confirm your booking now?"
                )
        
        elif objection and state.discount_tier == 2:
            # User asking for more than 15% or using unauthorized codes like SAVE50
            reply = (
                f"I appreciate your negotiation, but **15% off via {state.promo_code}** is the absolute maximum discount "
                f"authorized by our management. We cannot accept unauthorized codes or provide further reductions. "
                f"Your final price remains **₹{state.final_price:,.2f}** for {state.quantity} unit(s). "
                f"Would you like me to book this now?"
            )
        
        elif state.sku_id and state.quantity > 0:
            # Standard quote presentation
            product = CATALOG[state.sku_id]
            state.is_quote_presented = True
            cap_explanation = f"Since 1 unit covers up to {product['max_capacity_per_unit']} room(s), you will need **{state.quantity} unit(s)** to cover {state.required_capacity} room(s)." if state.required_capacity else f"You selected **{state.quantity} unit(s)**."
            
            reply = (
                f"Great choice with the **{product['name']}** on the **{state.plan_code}** plan! "
                f"{cap_explanation} "
                f"At ₹{state.unit_price:,.2f} per unit, your total is **₹{state.final_price:,.2f}**"
                + (f" (including {state.promo_code} for 10% off)." if state.discount_tier == 1 else "")
                + (f" (including {state.promo_code} for 15% off)." if state.discount_tier == 2 else " (standard pricing, promo_code=None).")
                + " Would you like me to go ahead and confirm your booking?"
            )
        
        elif state.sku_id and state.quantity == 0:
            # Product matched, but user has not yet specified room count or quantity
            product = CATALOG[state.sku_id]
            plans_text = ", ".join([f"{plan}: ₹{price:,.2f}" for plan, price in product["plans"].items()])
            cap = product["max_capacity_per_unit"]
            reply = (
                f"We have the **{product['name']}** in our catalog! "
                f"Available plans: {plans_text}. "
                f"Each unit covers up to **{cap} room(s)**. "
                f"How many rooms or units do you need to cover?"
            )
        
        else:
            # General inquiry
            reply = (
                "Hello! Welcome to Hotelzify. I can assist you with hotel technology packages including "
                "our AeroMesh Wi-Fi 6E Home Pack, SyncHub Conference Bars, Smart Door Locks, and Climate Thermostats. "
                "How many rooms or people are you looking to outfit?"
            )

        state.history.append({"role": "assistant", "content": reply})

        return {
            "action": "REPLY",
            "message": reply,
            "state": state.model_dump(),
            "executed_api": executed_api
        }
