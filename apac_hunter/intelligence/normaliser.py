import re

def normalise_name(name: str) -> str:
    if not name:
        return None

    name = name.strip()

    # Remove anything in parentheses
    name = re.sub(r'\s*\([^)]*\)', '', name).strip()

    # If name contains uncertainty language, try to salvage the core name
    uncertainty_phrases = [
        "specific individual", "individual tbd", "individual unclear",
        "not named", "tbd", "unclear", "unknown", "to be determined",
        "not identified", "unidentified"
    ]
    
    name_lower = name.lower()
    for phrase in uncertainty_phrases:
        if phrase in name_lower:
            # Try to extract just the family/person name before the uncertainty phrase
            # e.g. "Lee Family specific individual TBD" -> "Lee Family"
            idx = name_lower.find(phrase)
            core = name[:idx].strip().rstrip('-—,')
            if len(core) >= 3:
                name = core
                break
            else:
                return None  # Can't salvage a meaningful name

    # Title case family names
    if "family" in name.lower():
        name = " ".join(p.capitalize() for p in name.split())

    # Remove trailing punctuation
    name = name.rstrip('.,;:-— ')

    return name if len(name) >= 3 else None
