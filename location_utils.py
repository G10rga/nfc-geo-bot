from __future__ import annotations

import re

# English name → alternate spellings / Georgian forms that may appear on Maps.
TBILISI_DISTRICTS: dict[str, tuple[str, ...]] = {
    "Saburtalo": ("saburtalo", "საბურთალო", "vake-saburtalo", "ვაკე-საბურთალო"),
    "Vake": ("vake", "ვაკე"),
    "Vera": ("vera", "ვერა"),
    "Mtatsminda": ("mtatsminda", "მთაწმინდა"),
    "Sololaki": ("sololaki", "სოლოლაკი"),
    "Avlabari": ("avlabari", "ავლაბარი"),
    "Isani": ("isani", "ისანი"),
    "Samgori": ("samgori", "სამგორი"),
    "Gldani": ("gldani", "გლდანი"),
    "Didube": ("didube", "დიდუბე"),
    "Nadzaladevi": ("nadzaladevi", "ნაძალადევი"),
    "Chughureti": ("chughureti", "chugureti", "ჩუღურეთი"),
    "Krtsanisi": ("krtsanisi", "კრწანისი"),
    "Digomi": ("digomi", "dighomi", "დიღომი"),
    "Didi Digomi": ("didi digomi", "დიდი დიღომი"),
    "Ortachala": ("ortachala", "ორთაჭალა"),
    "Varketili": ("varketili", "ვარკეთილი"),
    "Isani-Samgori": ("isani-samgori", "ისანი-სამგორი"),
}

_CITY_ALIASES = {
    "tbilisi": "Tbilisi",
    "თბილისი": "Tbilisi",
    "tbilisi georgia": "Tbilisi",
}


def normalize_city(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    key = re.sub(r"\s+", " ", text).casefold()
    if key in _CITY_ALIASES:
        return _CITY_ALIASES[key]
    # "Tbilisi, something" or "something, Tbilisi"
    for part in re.split(r"[,/|]", text):
        part_key = part.strip().casefold()
        if part_key in _CITY_ALIASES:
            return _CITY_ALIASES[part_key]
    if "tbilisi" in key or "თბილისი" in text:
        return "Tbilisi"
    return text.split(",")[0].strip()


def detect_district(*texts: str) -> str:
    blob = " | ".join(t for t in texts if t).casefold()
    if not blob:
        return ""

    # Prefer more specific multi-word districts first.
    ranked = sorted(
        TBILISI_DISTRICTS.items(),
        key=lambda item: max(len(a) for a in item[1]),
        reverse=True,
    )
    for english, aliases in ranked:
        for alias in aliases:
            if alias.casefold() in blob:
                # Avoid matching bare "vake" inside "vake-saburtalo" as only Vake
                # when Saburtalo spelling is also present — Saburtalo aliases
                # include vake-saburtalo and are longer, so they win first.
                return english
    return ""


def format_general_location(
    *,
    city_hint: str = "",
    address: str = "",
    page_text: str = "",
) -> str:
    """Build Location cell like 'Tbilisi, Saburtalo'."""
    city = normalize_city(city_hint) or normalize_city(address) or "Tbilisi"
    district = detect_district(address, page_text, city_hint)
    if district:
        return f"{city}, {district}"
    return city


def has_district(location: str) -> bool:
    """True when Location already looks like 'City, District'."""
    text = (location or "").strip()
    if "," not in text:
        return False
    city, rest = text.split(",", 1)
    return bool(city.strip()) and bool(rest.strip())
