import asyncio
import sys
from app.state_machine import process_user_turn, session_manager
from app.mock_apis import get_catalog_info, API_CALL_LOGS


async def main():
    session_id = "cli_evaluation_session"
    print("=" * 70)
    print("🏨 Hotelzify AI Sales Agent — Interactive CLI")
    print("   100% Accuracy Challenge | Concurrency & Policy Guardrails")
    print("=" * 70)
    print("Pre-fetching catalog info via GET /api/catalog...")
    catalog = await get_catalog_info()
    print(f"Loaded {len(catalog)} packages from catalog.")
    print("Type your message below. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("\n[Customer]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("\nExiting CLI. Goodbye!")
                break

            result = await process_user_turn(session_id, user_input)
            
            print(f"\n[Sales Bot]: {result['message']}")
            
            # Print state debug inspection
            state = result["state"]
            print("-" * 50)
            print(f"[State Inspector]:")
            print(f"  • Product: {state.get('product_name')} ({state.get('sku_id')})")
            print(f"  • Plan: {state.get('plan_code')}")
            print(f"  • Capacity / Qty: {state.get('required_capacity')} rooms -> {state.get('quantity')} units")
            print(f"  • Discount Tier: {state.get('discount_tier')} (Code: {state.get('promo_code')})")
            print(f"  • Final Price: ${state.get('final_price', 0.0):.2f}")
            print(f"  • Confirmed: {state.get('is_confirmed')} | Booking: {state.get('booking_status')}")

            if result.get("executed_api"):
                api = result["executed_api"]
                print(f"\n⚡ [API EXECUTED]: {api['api']}")
                print(f"   Payload : {api['payload']}")
                print(f"   Response: {api['response']}")
            print("-" * 50)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI.")
            break


if __name__ == "__main__":
    asyncio.run(main())
