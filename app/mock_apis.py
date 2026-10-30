import asyncio
import uuid
import time
from typing import Dict, Any, Optional

# 10 Products Catalog in Indian Rupees (INR - ₹)
# Realistic hotel tech pricing in INR
CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Core Required Evaluation Item 1
    "SKU_AIRPODS_PRO2": {
        "name": "AirPods Pro 2nd Gen",
        "description": "Active Noise Cancelling audio for VIP suites and personal communication.",
        "max_capacity_per_unit": 1,
        "plans": {
            "STD": 20000.0,
            "CARE": 24000.0
        },
        "aliases": ["airpods", "airpod pro", "apple airpods", "airpod", "airpd", "pods", "airpods pro 2nd gen", "air pod"]
    },
    # 2. Core Required Evaluation Item 2
    "SKU_MESH_WIFI6": {
        "name": "AeroMesh Wi-Fi 6E Home Pack",
        "description": "Ultra-fast enterprise-grade Wi-Fi mesh coverage (1 unit covers up to 2 rooms).",
        "max_capacity_per_unit": 2,
        "plans": {
            "STD": 30000.0,
            "PRO": 40000.0
        },
        "aliases": ["aeromesh", "arrow mesh wifi", "arrow mesh", "aero mesh", "mesh wifi", "mesh router", "aeromesh wifi"]
    },
    # 3. Core Required Evaluation Item 3
    "SKU_TEAM_HUB": {
        "name": "SyncHub Conference Bar",
        "description": "All-in-one AI audio/video conference bar for meeting rooms and group spaces (1 unit covers up to 3 rooms/tables).",
        "max_capacity_per_unit": 3,
        "plans": {
            "STD": 70000.0,
            "PRO": 90000.0
        },
        "aliases": ["synchub", "sink hub", "sync hub", "conference bar", "meeting bar", "synchub conference bar"]
    },
    # 4. Smart Hotel Product
    "SKU_SMART_LOCK": {
        "name": "KwikStay Smart RFID Door Lock",
        "description": "Keyless RFID and Bluetooth hotel door lock (1 lock covers 1 room/door).",
        "max_capacity_per_unit": 1,
        "plans": {
            "STD": 15000.0,
            "PRO": 18000.0
        },
        "aliases": ["smart lock", "hotel lock", "door lock", "kwikstay", "rfid lock", "keyless lock"]
    },
    # 5. Smart Hotel Product
    "SKU_ENERGY_THERMO": {
        "name": "EcoSense Smart Climate Thermostat",
        "description": "Automated energy-saving thermostat (1 unit controls climate for up to 4 rooms/zone).",
        "max_capacity_per_unit": 4,
        "plans": {
            "STD": 25000.0,
            "PRO": 32000.0
        },
        "aliases": ["ecosense", "thermostat", "ac controller", "climate hub", "smart thermostat"]
    },
    # 6. Smart Hotel Product
    "SKU_GUEST_TABLET": {
        "name": "RoomTouch Concierge Tablet",
        "description": "In-room guest service ordering and interactive tablet (1 tablet per 1 room).",
        "max_capacity_per_unit": 1,
        "plans": {
            "STD": 12000.0,
            "PRO": 16000.0
        },
        "aliases": ["roomtouch", "guest tablet", "concierge tablet", "room tablet", "in-room tablet"]
    },
    # 7. Smart Hotel Product
    "SKU_SURVEIL_CAM": {
        "name": "OmniEye 4K Security Dome Camera",
        "description": "High-definition night-vision corridor security camera (1 camera monitors 3 corridors/areas).",
        "max_capacity_per_unit": 3,
        "plans": {
            "STD": 22000.0,
            "PRO": 28000.0
        },
        "aliases": ["omnieye", "security camera", "cctv", "dome camera", "corridor camera"]
    },
    # 8. Smart Hotel Product
    "SKU_VOICE_ASSIST": {
        "name": "RoomVoice Hospitality Smart Speaker",
        "description": "Voice-enabled room service and music speaker for suites (1 speaker per 1 suite).",
        "max_capacity_per_unit": 1,
        "plans": {
            "STD": 9000.0,
            "PRO": 12000.0
        },
        "aliases": ["roomvoice", "smart speaker", "voice assistant", "room speaker"]
    },
    # 9. Smart Hotel Product
    "SKU_GATEWAY_IOT": {
        "name": "ZigLink Hospitality IoT Gateway",
        "description": "Central multi-protocol IoT hub connecting hotel sensors (1 gateway manages up to 8 rooms).",
        "max_capacity_per_unit": 8,
        "plans": {
            "STD": 38000.0,
            "PRO": 48000.0
        },
        "aliases": ["ziglink", "iot gateway", "zigbee gateway", "sensor hub", "iot hub"]
    },
    # 10. Smart Hotel Product
    "SKU_SMART_LIGHT": {
        "name": "LuminaMesh Smart Suite Lighting Pack",
        "description": "Intelligent automated ambient LED lighting kit (1 pack covers 2 rooms).",
        "max_capacity_per_unit": 2,
        "plans": {
            "STD": 18000.0,
            "PRO": 24000.0
        },
        "aliases": ["luminamesh", "smart lighting", "room lights", "led pack", "lumina light"]
    }
}

# In-memory booking records
BOOKINGS_DB: Dict[str, Dict[str, Any]] = {}
API_CALL_LOGS: list[Dict[str, Any]] = []


def log_api_call(api_name: str, method: str, payload: Any, response: Any, duration_ms: float):
    """Record an API call with timestamp and latency for the live inspector and test verification."""
    API_CALL_LOGS.append({
        "timestamp": time.time(),
        "api_name": api_name,
        "method": method,
        "payload": payload,
        "response": response,
        "duration_ms": duration_ms
    })


async def get_catalog_info(query: Optional[str] = None) -> Dict[str, Any]:
    """
    GET /api/catalog mock implementation.
    Returns available packages, capacities, and pricing in INR (₹).
    """
    t0 = time.time()
    catalog_view = {}
    for sku_id, item in CATALOG.items():
        if query:
            q_lower = query.lower()
            matches_sku = q_lower in sku_id.lower()
            matches_name = q_lower in item["name"].lower()
            matches_alias = any(q_lower in a for a in item.get("aliases", []))
            if not (matches_sku or matches_name or matches_alias):
                continue
        catalog_view[sku_id] = {
            "name": item["name"],
            "currency": "INR",
            "max_capacity_per_unit": item["max_capacity_per_unit"],
            "plans": item["plans"]
        }
    duration_ms = (time.time() - t0) * 1000
    log_api_call("get_catalog_info", "GET", {"query": query}, catalog_view, duration_ms)
    return catalog_view


async def create_booking(
    sku_id: str,
    plan_code: str,
    quantity: int,
    promo_code: Optional[str],
    final_price: float
) -> Dict[str, Any]:
    """
    POST /api/bookings mock implementation.
    Simulates ~1.5s network delay and creates a confirmed booking in INR.
    """
    t0 = time.time()
    payload = {
        "sku_id": sku_id,
        "plan_code": plan_code,
        "quantity": quantity,
        "promo_code": promo_code,
        "final_price": final_price,
        "currency": "INR"
    }
    
    if sku_id not in CATALOG:
        raise ValueError(f"Invalid SKU: '{sku_id}' not found in catalog.")
    
    product = CATALOG[sku_id]
    if plan_code not in product["plans"]:
        raise ValueError(f"Invalid plan '{plan_code}' for SKU '{sku_id}'. Available: {list(product['plans'].keys())}")
    
    if quantity <= 0:
        raise ValueError(f"Quantity must be greater than zero. Got: {quantity}")

    # Simulate ~1.5 seconds processing time
    await asyncio.sleep(1.5)

    booking_id = f"BKG-{uuid.uuid4().hex[:8].upper()}"
    booking_record = {
        "status": "CONFIRMED",
        "booking_id": booking_id,
        "sku_id": sku_id,
        "product_name": product["name"],
        "plan_code": plan_code,
        "quantity": quantity,
        "promo_code": promo_code,
        "currency": "INR",
        "final_price": round(final_price, 2),
        "created_at": time.time()
    }
    BOOKINGS_DB[booking_id] = booking_record
    duration_ms = (time.time() - t0) * 1000
    log_api_call("create_booking", "POST", payload, booking_record, duration_ms)
    return booking_record
