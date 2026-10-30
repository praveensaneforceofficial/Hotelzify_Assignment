import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY
from app.state_machine import process_user_turn, session_manager

logger = logging.getLogger(__name__)

# System prompt for LLM conversational refinement
SALES_PERSONA_SYSTEM_PROMPT = """
You are a warm, highly professional, and consultative B2B Sales Executive for Hotelzify.
Your job is to assist hotel and property owners with technology packages (Wi-Fi Mesh, Conference Bars, Smart Locks, Thermostats, etc.).

STRICT SALES & OPERATIONAL RULES:
1. NEVER hallucinate or quote prices different from the provided context.
2. When presenting pricing, always state:
   - Package name
   - Plan code (STD, PRO, CARE)
   - Calculated quantity and capacity rationale (e.g. "covers up to 2 rooms per unit, so 5 rooms requires 3 units")
   - Total price and applied promo code (or standard price if none).
3. DISCOUNT RULES:
   - Standard pricing first (0% discount, promo_code=None).
   - If customer pushes back or negotiates once: offer 10% off with promo code SAVE10.
   - If customer pushes back a second time: offer 15% off with promo code CLOSENOW15 (absolute maximum).
   - Never skip straight to 15% on the first objection.
   - Never offer discounts unprompted.
   - If customer demands more than 15% (e.g. 20%, 50%, or SAVE50), politely but firmly explain that 15% via CLOSENOW15 is company policy and maximum management authorization.
4. MID-CONVERSATION CHANGES:
   - If customer changes rooms or plans, ALWAYS ensure the updated numbers and price are clearly stated and confirmed before booking.
5. Tone: Persuasive, friendly, articulate, professional.
"""


class SalesAgent:
    def __init__(self):
        self.openai_client: Optional[AsyncOpenAI] = None
        if OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client: {e}")

    async def handle_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        Processes a user turn:
        1. Executes through Deterministic State Machine to guarantee 100% mathematical and rule accuracy.
        2. If OpenAI client is active, can enhance the conversational polish while preserving exact figures.
        """
        result = await process_user_turn(session_id, user_message)
        
        # If the state machine executed a booking, catalog list, or specific guidance, return deterministic response immediately
        if result["action"] in ("ALREADY_BOOKED", "BOOKING_PENDING", "NON_CATALOG_REJECTED", "ROOMS_REQUIRED_FOR_DISCOUNT", "CATALOG_LISTED"):
            return result

        # Optional: Enrich message via OpenAI if available and desired
        if self.openai_client:
            try:
                # We provide the deterministic ground truth to OpenAI to ensure 0% hallucination
                state = result["state"]
                context_instruction = (
                    f"Core facts you MUST communicate accurately:\n"
                    f"- Action: {result['action']}\n"
                    f"- Product: {state.get('product_name')}\n"
                    f"- Plan: {state.get('plan_code')}\n"
                    f"- Quantity: {state.get('quantity')}\n"
                    f"- Currency: INR (₹)\n"
                    f"- Promo Code: {state.get('promo_code')}\n"
                    f"- Final Price: ₹{state.get('final_price', 0.0):,.2f}\n"
                    f"- Baseline Message: {result['message']}\n"
                    f"Refine this into a polished, professional sales message matching the persona. Do not change any numbers, codes, or products. Always express currency in INR (₹)."
                )

                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SALES_PERSONA_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                        {"role": "system", "content": context_instruction}
                    ],
                    temperature=0.2,
                    max_tokens=250
                )
                refined_text = response.choices[0].message.content
                if refined_text:
                    # Verify critical numbers are not stripped
                    if str(state.get('final_price')) in refined_text or f"{state.get('final_price'):.2f}" in refined_text or not state.get('final_price'):
                        result["message"] = refined_text
            except Exception as e:
                logger.warning(f"OpenAI call skipped/failed, using deterministic response: {e}")

        return result


# Singleton agent instance
sales_agent = SalesAgent()
