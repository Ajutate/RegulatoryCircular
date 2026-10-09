"""
Date Utilities
==============
Helpers for parsing and extracting regulatory effective dates.
Standardizes all dates to DD/MM/YYYY format.
"""

import re
from typing import Optional, Tuple

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}


def parse_date_to_dmy(raw_str: Optional[str]) -> Optional[str]:
    """
    Parse any date string into canonical DD/MM/YYYY format.
    Handles 'July 31, 2026', '31st July 2026', '31-07-2026', '2026-07-31', etc.
    """
    if not raw_str or str(raw_str).strip().lower() in ("null", "none", "n/a", "", "false", "no"):
        return None

    s = str(raw_str).strip().rstrip(".,;")
    # Strip ordinal suffixes: 1st, 2nd, 3rd, 31st
    s_clean = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', s, flags=re.IGNORECASE)

    # 1. DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$', s_clean)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mth <= 12:
            return f"{d:02d}/{mth:02d}/{y}"

    # 2. YYYY-MM-DD
    m = re.match(r'^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$', s_clean)
    if m:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mth <= 12:
            return f"{d:02d}/{mth:02d}/{y}"

    # 3. Month DD, YYYY or Month DD YYYY (e.g. July 31, 2026)
    m = re.match(r'^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$', s_clean)
    if m:
        mth_name, d, y = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        if mth_name in MONTHS and 1 <= d <= 31:
            return f"{d:02d}/{MONTHS[mth_name]:02d}/{y}"

    # 4. DD Month YYYY (e.g. 31 July 2026)
    m = re.match(r'^(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})$', s_clean)
    if m:
        d, mth_name, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        if mth_name in MONTHS and 1 <= d <= 31:
            return f"{d:02d}/{MONTHS[mth_name]:02d}/{y}"

    # 5. Fallback: extract any embedded date from string
    m = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', s_clean)
    if m and m.group(1).lower() in MONTHS:
        return f"{int(m.group(2)):02d}/{MONTHS[m.group(1).lower()]:02d}/{m.group(3)}"

    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9}),?\s+(\d{4})\b', s_clean)
    if m and m.group(2).lower() in MONTHS:
        return f"{int(m.group(1)):02d}/{MONTHS[m.group(2).lower()]:02d}/{m.group(3)}"

    m = re.search(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b', s_clean)
    if m:
        d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mth <= 12:
            return f"{d:02d}/{mth:02d}/{y}"

    return None


def extract_effective_date_from_text(text: str) -> Tuple[str, Optional[str]]:
    """
    Look for effective date, implementation date, release date, or deadline in paragraph text.
    Returns:
        (has_effective_date: "Yes"|"No", effective_date: "DD/MM/YYYY"|None)
    """
    if not text:
        return "No", None

    # Contextual regexes that strongly signal an effective / applicability / release date
    patterns = [
        # 1. Actionable phrases with dates: "scheduled to be released on live on ... July 31, 2026"
        r'(?:released on live|release on live|go-live|go live)\s+(?:on|as of|by|date of|the|end of day)*\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:released on live|release on live|go-live|go live)\s+(?:on|as of|by|date of|the|end of day)*\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})',
        
        # 2. "with effect from", "w.e.f.", "come into effect from", "take effect from"
        r'(?:come into (?:force|effect)|with effect from|w\.e\.f\.?|in force from|effective from|effective date(?:\s+is)?)\s+(?:from|on|as of|date of|the)*\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:come into (?:force|effect)|with effect from|w\.e\.f\.?|in force from|effective from|effective date(?:\s+is)?)\s+(?:from|on|as of|date of|the)*\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})',
        r'(?:come into (?:force|effect)|with effect from|w\.e\.f\.?|in force from|effective from|effective date(?:\s+is)?)\s+(?:from|on|as of|date of|the)*\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
        
        # 3. "applicable with effect from", "applicable from"
        r'(?:applicable\s+(?:with effect\s+)?from)\s+(?:on|the|date of)*\s*([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:applicable\s+(?:with effect\s+)?from)\s+(?:on|the|date of)*\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})',
        r'(?:applicable\s+(?:with effect\s+)?from)\s+(?:on|the|date of)*\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',

        # 4. "ensure ... incorporated ... before/by <date>"
        r'(?:incorporated|implemented|compliance|comply|ensure|submission|deadline)\s+.*?before\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:incorporated|implemented|compliance|comply|ensure|submission|deadline)\s+.*?before\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})',
        r'(?:on or before|by no later than|latest by|by)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        r'(?:on or before|by no later than|latest by|by)\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})',
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            parsed = parse_date_to_dmy(m.group(1))
            if parsed:
                return "Yes", parsed

    # 5. If text contains effective keywords anywhere, find the primary date
    if re.search(r'\b(effective|w\.e\.f|released on live|applicab|force from|deadline)\b', text, flags=re.IGNORECASE):
        # Look for Month DD, YYYY
        m = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', text)
        if m and m.group(1).lower() in MONTHS:
            parsed = parse_date_to_dmy(f"{m.group(1)} {m.group(2)}, {m.group(3)}")
            if parsed:
                return "Yes", parsed

        # Look for DD Month YYYY
        m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9}),?\s+(\d{4})\b', text)
        if m and m.group(2).lower() in MONTHS:
            parsed = parse_date_to_dmy(f"{m.group(1)} {m.group(2)} {m.group(3)}")
            if parsed:
                return "Yes", parsed

        # Look for DD/MM/YYYY
        m = re.search(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})\b', text)
        if m:
            parsed = parse_date_to_dmy(m.group(1))
            if parsed:
                return "Yes", parsed

    return "No", None


def harmonize_document_effective_dates(items: list) -> Tuple[list, Optional[str]]:
    """
    If any effective date is found in any paragraph of the document,
    apply that effective date to ALL paragraphs in the document:
      item.has_effective_date = "Yes"
      item.effective_date = target_date

    Works transparently with dicts, Pydantic models, and SQLAlchemy objects.
    Returns:
        (updated_items, target_date)
    """
    if not items:
        return items, None

    from collections import Counter
    date_counter = Counter()
    future_counter = Counter()

    for item in items:
        # 1. Read existing effective_date
        if isinstance(item, dict):
            eff = item.get("effective_date")
            p_type = str(item.get("para_type") or "")
            p_text = item.get("paragraph_text") or ""
        else:
            eff = getattr(item, "effective_date", None)
            p_type = str(getattr(item, "para_type", "") or "")
            p_text = getattr(item, "paragraph_text", "") or ""

        parsed = parse_date_to_dmy(eff)

        # 2. Safety fallback: extract from text if missing
        if not parsed and p_text:
            has_dt, detected = extract_effective_date_from_text(p_text)
            if has_dt == "Yes" and detected:
                parsed = detected

        if parsed:
            date_counter[parsed] += 1
            if "future" in p_type.lower():
                future_counter[parsed] += 1

    if not date_counter:
        return items, None

    # Priority: future effective dates if present, else most frequent date
    if future_counter:
        target_date = future_counter.most_common(1)[0][0]
    else:
        target_date = date_counter.most_common(1)[0][0]

    # Apply target date across ALL items
    for item in items:
        if isinstance(item, dict):
            item["has_effective_date"] = "Yes"
            item["effective_date"] = target_date
        else:
            try:
                setattr(item, "has_effective_date", "Yes")
                setattr(item, "effective_date", target_date)
            except Exception:
                pass

    return items, target_date

