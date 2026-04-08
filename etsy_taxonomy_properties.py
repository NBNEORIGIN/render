"""Etsy taxonomy property ID mapping for Render.

Etsy allows max 2 variation properties per listing.
Standard properties (from Etsy taxonomy) have fixed property_ids.
Custom properties use Etsy's reserved custom slots (513, 514).

For taxonomy_id 2844 (Signs), verified against:
GET /v3/application/seller-taxonomy/nodes/2844/properties
"""
import logging

# Standard Etsy taxonomy property IDs
STANDARD_PROPERTIES: dict[str, int] = {
    "primary_color":   200,
    "secondary_color": 52047899002,
    "occasion":        46803063659,
    "holiday":         46803063641,
}

# Custom property slots (not taxonomy-defined; free-text values only)
CUSTOM_PROPERTY_SLOTS: dict[str, int] = {
    "size":   513,
    "finish": 514,
}

# Display names for each property (shown as dropdown label in Etsy)
PROPERTY_DISPLAY_NAMES: dict[str, str] = {
    "primary_color":   "Primary color",
    "secondary_color": "Secondary color",
    "size":            "Size",
    "finish":          "Finish",
    "occasion":        "Occasion",
    "holiday":         "Holiday",
}

# Known Etsy value_ids for primary_color (property 200).
# Verified against GET /v3/application/seller-taxonomy/nodes/2844/properties (2026-04-08).
PRIMARY_COLOR_VALUE_IDS: dict[str, int] = {
    "Beige":    1213,
    "Black":    1,
    "Blue":     2,
    "Bronze":   1216,
    "Brown":    3,
    "Clear":    1219,
    "Copper":   1218,
    "Gold":     1214,
    "Gray":     5,
    "Green":    4,
    "Orange":   6,
    "Pink":     7,
    "Purple":   8,
    "Rainbow":  1220,
    "Red":      9,
    "Rose gold": 1217,
    "Silver":   1215,
    "White":    10,
    "Yellow":   11,
}

# Map property_name → {value_text: value_id} for standard properties
STANDARD_VALUE_IDS: dict[str, dict[str, int]] = {
    "primary_color": PRIMARY_COLOR_VALUE_IDS,
}

# Size display strings for each Render blank slug (mm format for Etsy)
SIZE_DISPLAY_MM: dict[str, str] = {
    "dracula":    "95 x 95mm",
    "saville":    "115 x 95mm",
    "dick":       "140 x 90mm",
    "barzan":     "194 x 143mm",
    "baby_jesus": "290 x 190mm",
}

# Size display order for consistent grid ordering
SIZE_ORDER: list[str] = ["dracula", "saville", "dick", "barzan", "baby_jesus"]

# Color display strings for each Render color slug
COLOR_DISPLAY: dict[str, str] = {
    "silver": "Silver",
    "gold":   "Gold",
    "white":  "White",
}

COLOR_ORDER: list[str] = ["silver", "gold", "white"]


def resolve_property_id(logical_name: str) -> tuple[int, bool]:
    """Return (property_id, is_standard).

    is_standard=True means values should use value_ids from STANDARD_VALUE_IDS.
    is_standard=False means pass free-text values only (value_ids=[]).
    """
    if logical_name in STANDARD_PROPERTIES:
        return STANDARD_PROPERTIES[logical_name], True
    if logical_name in CUSTOM_PROPERTY_SLOTS:
        return CUSTOM_PROPERTY_SLOTS[logical_name], False
    raise ValueError(f"Unknown Etsy property: {logical_name!r}")


def resolve_value_ids(property_name: str, values: list[str]) -> list[int]:
    """Return value_ids list for a standard property + value list.

    Returns [] for custom properties or unrecognised values (Etsy accepts text-only).
    """
    lookup = STANDARD_VALUE_IDS.get(property_name, {})
    result = []
    for v in values:
        vid = lookup.get(v)
        if vid is not None:
            result.append(vid)
        else:
            logging.warning("No value_id found for %s=%r — using text-only", property_name, v)
    return result


def property_display_name(logical_name: str) -> str:
    return PROPERTY_DISPLAY_NAMES.get(logical_name, logical_name.replace("_", " ").title())


def size_display_from_slug(slug: str) -> str:
    """Convert blank slug (e.g. 'saville') to Etsy size display string."""
    return SIZE_DISPLAY_MM.get(slug.lower(), slug)


def color_display_from_slug(slug: str) -> str:
    """Convert color slug (e.g. 'silver') to Etsy color display string."""
    return COLOR_DISPLAY.get(slug.lower(), slug.title())
