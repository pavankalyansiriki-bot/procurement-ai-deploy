import re

BLOCKED_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'forget\s+(all\s+)?rules',
    r'bypass\s+security',
    r'act\s+as\s+(if|though)',
    r'you\s+are\s+now',
    r'jailbreak',
    r'what\s+is\s+the\s+weather',
    r'tell\s+me\s+a\s+joke',
    r'write\s+(me\s+a?\s+)?(poem|story|essay|code)',
    r'who\s+(are|is)\s+you',
    r'what\s+is\s+your\s+name',
    r'help\s+me\s+with\s+(homework|cooking|relationship)',
    r'stock\s+price',
    r'play\s+(music|song)',
    r'open\s+(youtube|netflix)',
]

PROCUREMENT_REQUIRED_WORDS = [
    'buy', 'purchase', 'order', 'procure', 'get', 'acquire',
    'need', 'request', 'laptop', 'computer', 'equipment',
    'supply', 'supplies', 'item', 'product', 'unit', 'units'
]


def check_guardrails(text: str) -> tuple[bool, str]:
    """Returns (blocked: bool, reason: str)"""
    text_lower = text.lower().strip()

    if len(text_lower) < 5:
        return True, "Request too short. Please describe what you want to purchase."
    if len(text_lower) > 500:
        return True, "Request too long. Please be concise (max 500 characters)."

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text_lower):
            return True, (
                "Request blocked: irrelevant or unsafe content detected. "
                "This system only handles procurement requests."
            )

    if not any(word in text_lower for word in PROCUREMENT_REQUIRED_WORDS):
        return True, (
            "Not a procurement request. Please ask about buying, ordering, "
            "or procuring items. Example: 'Buy 20 Dell laptops'"
        )

    return False, ""
