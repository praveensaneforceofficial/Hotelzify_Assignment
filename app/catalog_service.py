import math
import re
from typing import Optional, Tuple, Dict, Any
from app.mock_apis import CATALOG, get_catalog_info


def calculate_units_needed(required_capacity: int, max_capacity_per_unit: int) -> int:
    """
    Deterministic ceiling calculation:
    quantity = ceil(user_requirement / max_capacity_per_unit)
    e.g. 5 rooms for capacity 2 = 3 units.
    """
    if required_capacity <= 0 or max_capacity_per_unit <= 0:
        return 1
    return math.ceil(required_capacity / max_capacity_per_unit)


def normalize_text(text: str) -> str:
    """Lowercase and strip punctuation."""
    return re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower().strip()


def resolve_sku_from_text(user_query: str) -> Optional[str]:
    """
    Strict catalog matcher.
    Matches typos and informal names (e.g., 'arrow mesh wifi', 'sink hub').
    CRITICAL: Must return None if user asks for an unknown item (e.g., 'Netgear Orbi router').
    """
    query_clean = normalize_text(user_query)
    words = set(query_clean.split())
    
    # Negative checks for known non-catalog brands/products
    non_catalog_keywords = [
        "netgear", "orbi", "eero", "google nest", "tp-link", "cisco", 
        "asus", "d-link", "sonos", "bose", "sony"
    ]
    for non_cat in non_catalog_keywords:
        if non_cat in query_clean:
            return None

    # Check exact phrase or alias match
    best_sku: Optional[str] = None
    best_score = 0

    for sku_id, product in CATALOG.items():
        name_clean = normalize_text(product["name"])
        aliases = [normalize_text(a) for a in product.get("aliases", [])]
        all_candidates = [name_clean] + aliases

        for candidate in all_candidates:
            if candidate in query_clean:
                score = len(candidate)
                if score > best_score:
                    best_score = score
                    best_sku = sku_id
        
        for candidate in all_candidates:
            candidate_words = set(candidate.split())
            if candidate_words and candidate_words.issubset(words):
                score = len(" ".join(candidate_words))
                if score > best_score:
                    best_score = score
                    best_sku = sku_id

    if best_sku:
        return best_sku

    return None


def resolve_plan_code(text: str, sku_id: str) -> str:
    """
    Resolve requested plan for SKU. Default to 'STD' if unspecified.
    """
    text_upper = text.upper()
    product = CATALOG.get(sku_id, {})
    available_plans = product.get("plans", {"STD": 0.0})
    
    if "CARE" in text_upper and "CARE" in available_plans:
        return "CARE"
    if "PRO" in text_upper and "PRO" in available_plans:
        return "PRO"
    if "STD" in text_upper and "STD" in available_plans:
        return "STD"
    if "STANDARD" in text_upper and "STD" in available_plans:
        return "STD"

    return "STD" if "STD" in available_plans else list(available_plans.keys())[0]


def extract_rooms_or_capacity(text: str) -> Optional[int]:
    """
    Extracts number of rooms, doors, people, or tables (the coverage requirement).
    Does NOT mistake confirmation of already-calculated units for a room-count change.
    """
    # Explicit room/coverage patterns
    room_patterns = [
        r"(\d+)\s*(?:-|\s)?\s*(?:room|rooms|people|person|door|doors|table|tables|area|areas|zones?|house|suites?)",
        r"(?:change to|for|covers?|outfitting|need|have)\s*(\d+)\s*(?:room|rooms|people|person|door|doors|table|tables|area|areas|zones?|house|suites?)",
        r"(?:change to|updated to)\s*(\d+)"
    ]
    for pattern in room_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                val = int(match.group(1))
                if 1 <= val <= 1000:
                    return val
            except ValueError:
                pass
    
    # Check for number words
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    for word, num in word_to_num.items():
        pattern = rf"\b{word}\b\s*(?:-|\s)?\s*(?:room|rooms|people|person|door|doors|table|tables|area|areas|zone|suites?)"
        if re.search(pattern, text, re.IGNORECASE):
            return num

    return None


def extract_explicit_units(text: str) -> Optional[int]:
    """Extracts explicit unit count like '4 units', '3 packs'."""
    match = re.search(r"(\d+)\s*(?:unit|units|pack|packs)", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None
