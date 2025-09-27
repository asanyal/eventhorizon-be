"""
Meeting title exceptions - events that should be filtered out from calendar results
"""

# Exact title matches - events with these exact titles will be excluded
EXCLUDED_EXACT_TITLES = [
    "Block",
    "Refrain from scheduling | Ask before scheduling",
    "Buffer / Do not schedule",
    "Blocked",
    "Try and not schedule if possible"
]

# Partial matches - events containing these substrings will be excluded
EXCLUDED_PARTIAL_TITLES = [
    # Add partial matches here if needed
    # Example: "vacation", "out of office"
]

# Case-insensitive partial matches - events containing these substrings (case-insensitive) will be excluded
EXCLUDED_CASE_INSENSITIVE_PARTIAL_TITLES = [
    # Add case-insensitive partial matches here if needed
    "Commute",
    "OOO"
]


def should_exclude_event(event_title: str) -> bool:
    """
    Check if an event should be excluded based on its title
    
    Args:
        event_title: The title/summary of the calendar event
        
    Returns:
        True if the event should be excluded, False otherwise
    """
    if not event_title:
        return False
    
    # Check exact matches
    if event_title in EXCLUDED_EXACT_TITLES:
        return True
    
    # Check partial matches (case-sensitive)
    for partial in EXCLUDED_PARTIAL_TITLES:
        if partial in event_title:
            return True
    
    # Check case-insensitive partial matches
    event_title_lower = event_title.lower()
    for partial in EXCLUDED_CASE_INSENSITIVE_PARTIAL_TITLES:
        if partial.lower() in event_title_lower:
            return True
    
    return False


def add_excluded_title(title: str, match_type: str = "exact") -> None:
    """
    Add a new title to the exclusion list
    
    Args:
        title: The title to exclude
        match_type: Type of matching - "exact", "partial", or "case_insensitive_partial"
    """
    if match_type == "exact":
        if title not in EXCLUDED_EXACT_TITLES:
            EXCLUDED_EXACT_TITLES.append(title)
    elif match_type == "partial":
        if title not in EXCLUDED_PARTIAL_TITLES:
            EXCLUDED_PARTIAL_TITLES.append(title)
    elif match_type == "case_insensitive_partial":
        if title not in EXCLUDED_CASE_INSENSITIVE_PARTIAL_TITLES:
            EXCLUDED_CASE_INSENSITIVE_PARTIAL_TITLES.append(title)
    else:
        raise ValueError("match_type must be 'exact', 'partial', or 'case_insensitive_partial'")


def get_excluded_titles_summary() -> dict:
    """
    Get a summary of all excluded titles
    
    Returns:
        Dictionary with lists of excluded titles by type
    """
    return {
        "exact_matches": EXCLUDED_EXACT_TITLES.copy(),
        "partial_matches": EXCLUDED_PARTIAL_TITLES.copy(),
        "case_insensitive_partial_matches": EXCLUDED_CASE_INSENSITIVE_PARTIAL_TITLES.copy(),
    }
