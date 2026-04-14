"""Etsy variation listing push pipeline for Render.

Pushes one Etsy draft listing per EtsyListingGroup (product family),
with the full Size × Color inventory grid in a single updateListingInventory call.

Flow per group:
  1. Validate group (≥2 variants, option values set, grid complete)
  2. createDraftListing
  3. Upload deduped images (canonical variant first, then one image per unique color)
  4. Build products[] from variants + fill missing grid combinations
  5. Detect price_on / quantity_on / sku_on from variance
  6. PUT updateListingInventory
  7. POST variation-images (bind color → image)
  8. Persist etsy_listing_id + status to render_etsy_listing_group
"""
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from config import ETSY_SHOP_ID, ETSY_TAXONOMY_ID, IMAGES_DIR
from etsy_auth import get_etsy_auth_from_env
from etsy_api import EtsyListingManager, _etsy_title_case, _sanitise_tag
from etsy_taxonomy_properties import (
    resolve_property_id,
    resolve_value_ids,
    property_display_name,
    SIZE_ORDER,
    COLOR_ORDER,
)

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pv_value(product: dict, property_id: int) -> Optional[str]:
    """Extract the first value for property_id from a product's property_values."""
    for pv in product.get("property_values", []):
        if pv["property_id"] == property_id:
            vals = pv.get("values", [])
            return vals[0] if vals else None
    return None


def _build_property_value(
    property_name: str,
    value: str,
) -> dict:
    """Build a property_values entry for the inventory payload."""
    pid, is_standard = resolve_property_id(property_name)
    value_ids = resolve_value_ids(property_name, [value]) if is_standard else []
    return {
        "property_id": pid,
        "property_name": property_display_name(property_name),
        "values": [value],
        "value_ids": value_ids,
    }


# ── Step 4 — build products[] ─────────────────────────────────────────────────

def build_products(
    group: dict,
    variants: list[dict],
) -> tuple[list[dict], int, Optional[int]]:
    """Build Etsy inventory products[] from render variant rows.

    Returns (products, opt1_pid, opt2_pid).
    """
    opt1_prop = group["option1_property"]
    opt2_prop = group.get("option2_property") or ""

    opt1_pid, _ = resolve_property_id(opt1_prop)
    opt2_pid = resolve_property_id(opt2_prop)[0] if opt2_prop else None

    products = []
    for v in variants:
        opt1_val = v.get("etsy_option1_value") or ""
        opt2_val = v.get("etsy_option2_value") or ""

        if not opt1_val:
            log.warning("Variant %s has no etsy_option1_value — skipping", v.get("m_number"))
            continue

        pv = [_build_property_value(opt1_prop, opt1_val)]
        if opt2_pid and opt2_val:
            pv.append(_build_property_value(opt2_prop, opt2_val))

        price = _variant_price(v)
        qty = 10  # default stock quantity for Etsy variation listings

        products.append({
            "sku": v.get("m_number", ""),
            "property_values": pv,
            "offerings": [{
                "price":              price,
                "quantity":           qty,
                "is_enabled":         True,
                "readiness_state_id": 1402336022581,
            }],
        })

    return products, opt1_pid, opt2_pid


def _variant_price(v: dict) -> float:
    """Derive price from the variant's blank size slug."""
    from export_etsy import SIZE_CONFIG
    size_slug = (v.get("size") or "saville").lower()
    return SIZE_CONFIG.get(size_slug, SIZE_CONFIG["saville"])["price"]


# ── Step 4b — complete-grid fill ──────────────────────────────────────────────

def fill_missing_combinations(
    products: list[dict],
    opt1_pid: int,
    opt2_pid: Optional[int],
    group: dict,
) -> list[dict]:
    """Ensure every size × color combination exists (Etsy rejects partial grids).

    Missing combinations get quantity=0, is_enabled=False, price=min(existing).
    """
    if opt2_pid is None:
        return products  # single-axis, no grid to fill

    opt1_prop = group["option1_property"]
    opt2_prop = group.get("option2_property") or ""

    opt1_pid_check, _ = resolve_property_id(opt1_prop)
    opt2_pid_check, _ = resolve_property_id(opt2_prop)

    # Collect distinct values in canonical order
    opt1_vals_all = {_pv_value(p, opt1_pid) for p in products}
    opt2_vals_all = {_pv_value(p, opt2_pid) for p in products}

    # Sort by known canonical order if possible
    def sort_key_size(v):
        # canonical size order from SIZE_ORDER display strings
        from etsy_taxonomy_properties import SIZE_DISPLAY_MM
        order = list(SIZE_DISPLAY_MM.values())
        try:
            return order.index(v)
        except ValueError:
            return 999

    def sort_key_color(v):
        from etsy_taxonomy_properties import COLOR_DISPLAY
        order = list(COLOR_DISPLAY.values())
        try:
            return order.index(v)
        except ValueError:
            return 999

    opt1_vals = sorted(opt1_vals_all, key=sort_key_size)
    opt2_vals = sorted(opt2_vals_all, key=sort_key_color)

    existing = {
        (_pv_value(p, opt1_pid), _pv_value(p, opt2_pid)): p
        for p in products
    }

    min_price = min(p["offerings"][0]["price"] for p in products)
    filled = []

    for o1 in opt1_vals:
        for o2 in opt2_vals:
            if (o1, o2) in existing:
                filled.append(existing[(o1, o2)])
            else:
                log.info("Filling missing grid combination: %s × %s", o1, o2)
                filled.append({
                    "sku": f"PLACEHOLDER-{o1}-{o2}".replace(" ", ""),
                    "property_values": [
                        _build_property_value(opt1_prop, o1),
                        _build_property_value(opt2_prop, o2),
                    ],
                    "offerings": [{
                        "price":              min_price,
                        "quantity":           0,
                        "is_enabled":         False,
                        "readiness_state_id": 1402336022581,
                    }],
                })

    return filled


# ── Step 5 — detect *_on_property ────────────────────────────────────────────

def detect_on_property(
    products: list[dict],
    opt1_pid: int,
    opt2_pid: Optional[int],
) -> tuple[list[int], list[int], list[int]]:
    """Detect which property drives price / quantity / SKU variance.

    Returns (price_on_property, quantity_on_property, sku_on_property) as
    lists of property_ids.
    """
    def varies_along(field_fn, pivot_pid, other_pid):
        """True if field varies when we fix other_pid and walk pivot_pid."""
        groups = defaultdict(list)
        for p in products:
            if not p["offerings"][0]["is_enabled"]:
                continue  # ignore placeholder rows
            key = _pv_value(p, other_pid) if other_pid else "__all__"
            groups[key].append(field_fn(p))
        return any(len(set(vals)) > 1 for vals in groups.values())

    def price_fn(p): return p["offerings"][0]["price"]
    def qty_fn(p):   return p["offerings"][0]["quantity"]
    def sku_fn(p):   return p["sku"]

    price_on, qty_on, sku_on = [], [], []

    for fn, target in [(price_fn, price_on), (qty_fn, qty_on), (sku_fn, sku_on)]:
        if varies_along(fn, opt1_pid, opt2_pid):
            target.append(opt1_pid)
        if opt2_pid and varies_along(fn, opt2_pid, opt1_pid):
            target.append(opt2_pid)

    return price_on, qty_on, sku_on


# ── Step 3 — image upload ─────────────────────────────────────────────────────

def upload_group_images(
    manager: EtsyListingManager,
    listing_id: int,
    variants: list[dict],
    opt2_prop: Optional[str],
) -> dict[str, int]:
    """Upload deduped images for the group; return {m_number-rank: listing_image_id}.

    Strategy:
    - Upload ranks 001-004 for the canonical variant (first by SIZE_ORDER × silver)
    - Upload rank 001 for each additional unique color (for variation-image binding)
    - Cap at 10 images total (Etsy hard limit)

    Returns {f"{m_number}-{rank}": image_id} for later variation-image binding.
    """
    from etsy_taxonomy_properties import SIZE_ORDER, COLOR_ORDER, size_display_from_slug

    IMAGE_RANKS = ["001", "002", "003", "004"]
    MAX_IMAGES = 10
    image_map: dict[str, int] = {}  # "{m_number}-{rank}" → listing_image_id

    # Sort variants: canonical first (smallest size, silver color)
    def variant_sort_key(v):
        size_slug = (v.get("size") or "saville").lower()
        color_slug = (v.get("color") or "silver").lower()
        si = SIZE_ORDER.index(size_slug) if size_slug in SIZE_ORDER else 99
        ci = COLOR_ORDER.index(color_slug) if color_slug in COLOR_ORDER else 99
        return (si, ci)

    sorted_variants = sorted(variants, key=variant_sort_key)
    canonical = sorted_variants[0]

    # Upload canonical variant's primary images (001-004)
    uploaded_colors = set()
    rank = 1

    for img_num in IMAGE_RANKS:
        if rank > MAX_IMAGES:
            break
        m = canonical["m_number"]
        path = _find_image(m, img_num)
        if path:
            result = manager.upload_image(listing_id, path, rank=rank)
            if result.get("listing_image_id"):
                key = f"{m}-{img_num}"
                image_map[key] = result["listing_image_id"]
                rank += 1
    canonical_color = (canonical.get("color") or "silver").lower()
    uploaded_colors.add(canonical_color)

    # Upload 001 image for each additional unique color (for variation-image binding)
    if opt2_prop:
        seen_by_color: dict[str, dict] = {}
        for v in sorted_variants:
            c = (v.get("color") or "silver").lower()
            if c not in seen_by_color:
                seen_by_color[c] = v

        for color_slug, v in seen_by_color.items():
            if color_slug in uploaded_colors:
                continue
            if rank > MAX_IMAGES:
                log.warning("Hit 10-image Etsy limit; skipping color %s", color_slug)
                break
            m = v["m_number"]
            path = _find_image(m, "001")
            if path:
                result = manager.upload_image(listing_id, path, rank=rank)
                if result.get("listing_image_id"):
                    image_map[f"{m}-001"] = result["listing_image_id"]
                    rank += 1
                    uploaded_colors.add(color_slug)

    return image_map


def _find_image(m_number: str, img_num: str) -> Optional[Path]:
    """Find image file, trying both naming conventions."""
    for name in [f"{m_number} - {img_num}.jpg", f"{m_number}-{img_num}.jpg"]:
        p = IMAGES_DIR / m_number / name
        if p.exists():
            return p
    return None


# ── Step 7 — variation-image binding ─────────────────────────────────────────

def build_variation_image_bindings(
    variants: list[dict],
    image_map: dict[str, int],
    opt2_prop: str,
    opt2_pid: int,
) -> list[dict]:
    """Build variation-images payload binding each color to its image_id.

    Etsy swaps the listing thumbnail when a buyer picks a color.
    """
    from etsy_taxonomy_properties import COLOR_ORDER

    # Map color_slug → m_number of first (canonical smallest-size) variant
    seen: dict[str, str] = {}
    for v in sorted(variants, key=lambda v: (
        COLOR_ORDER.index((v.get("color") or "silver").lower())
        if (v.get("color") or "silver").lower() in COLOR_ORDER else 99
    )):
        c = (v.get("color") or "silver").lower()
        if c not in seen:
            seen[c] = v["m_number"]

    _, is_standard = resolve_property_id(opt2_prop)

    bindings = []
    for color_slug, m_number in seen.items():
        # Find the image_id for this variant's 001 image
        img_id = image_map.get(f"{m_number}-001")
        if not img_id:
            # Fall back to any image for this m_number in the map
            for key, iid in image_map.items():
                if key.startswith(f"{m_number}-"):
                    img_id = iid
                    break
        if not img_id:
            log.warning("No image found for color %s (m_number=%s) — skipping binding", color_slug, m_number)
            continue

        from etsy_taxonomy_properties import color_display_from_slug, resolve_value_ids
        color_display = color_display_from_slug(color_slug)
        value_ids = resolve_value_ids(opt2_prop, [color_display]) if is_standard else []

        entry = {
            "property_id": opt2_pid,
            "image_id":    img_id,
        }
        # Standard properties (like primary_color) require value_id for variation-image binding
        if value_ids:
            entry["value_id"] = value_ids[0]
        else:
            entry["value"] = color_display

        bindings.append(entry)

    return bindings


# ── Orchestrator ──────────────────────────────────────────────────────────────

def push_listing_group(group: dict, variants: list[dict]) -> dict:
    """Create one Etsy draft listing for a group with the full variation grid.

    Args:
        group: Row from render_etsy_listing_group (as dict)
        variants: Rows from render_products (as dicts) belonging to this group

    Returns:
        {success, listing_id, error, variant_count}
    """
    parent_sku = group.get("parent_sku", "?")

    # ── Validate ──────────────────────────────────────────────────────────────
    if len(variants) < 2:
        return {"success": False, "listing_id": None,
                "error": f"Group {parent_sku}: need ≥2 variants, got {len(variants)}"}

    missing_opts = [v["m_number"] for v in variants
                    if not v.get("etsy_option1_value")]
    if missing_opts:
        return {"success": False, "listing_id": None,
                "error": f"Group {parent_sku}: missing etsy_option1_value on {missing_opts}"}

    auth = get_etsy_auth_from_env()
    manager = EtsyListingManager(auth)

    opt1_prop = group["option1_property"]
    opt2_prop = group.get("option2_property") or ""

    opt1_pid, _ = resolve_property_id(opt1_prop)
    opt2_pid, _ = resolve_property_id(opt2_prop) if opt2_prop else (None, False)

    listing_id = None

    try:
        # ── Step 2 — createDraftListing ───────────────────────────────────────
        listing_data = _build_draft_listing_payload(group, variants)
        result = manager._request("POST", "listings", data=listing_data)
        listing_id = result.get("listing_id")
        if not listing_id:
            raise ValueError(f"createDraftListing returned no listing_id: {result}")
        log.info("Group %s: created draft listing %s", parent_sku, listing_id)

        # ── Step 3 — upload images ────────────────────────────────────────────
        image_map = upload_group_images(manager, listing_id, variants, opt2_prop)
        log.info("Group %s: uploaded %d images", parent_sku, len(image_map))

        # ── Step 4 — build products[] ─────────────────────────────────────────
        products, opt1_pid_built, opt2_pid_built = build_products(group, variants)
        if not products:
            raise ValueError("build_products returned empty list")

        # ── Step 4b — fill missing grid combinations ──────────────────────────
        products = fill_missing_combinations(products, opt1_pid_built, opt2_pid_built, group)
        log.info("Group %s: %d products in inventory grid", parent_sku, len(products))

        # ── Step 5 — detect *_on_property ────────────────────────────────────
        price_on, qty_on, sku_on = detect_on_property(products, opt1_pid_built, opt2_pid_built)
        log.info("Group %s: price_on=%s qty_on=%s sku_on=%s",
                 parent_sku, price_on, qty_on, sku_on)

        # ── Step 6 — PUT updateListingInventory ───────────────────────────────
        manager.update_listing_inventory(
            listing_id, products,
            price_on_property=price_on,
            quantity_on_property=qty_on,
            sku_on_property=sku_on,
        )
        log.info("Group %s: inventory updated", parent_sku)

        # ── Step 7 — bind variation images ────────────────────────────────────
        if opt2_prop and opt2_pid_built and image_map:
            bindings = build_variation_image_bindings(
                variants, image_map, opt2_prop, opt2_pid_built
            )
            if bindings:
                manager.bind_variation_images(listing_id, bindings)
                log.info("Group %s: bound %d variation images", parent_sku, len(bindings))

        return {
            "success":       True,
            "listing_id":    listing_id,
            "variant_count": len([p for p in products if p["offerings"][0]["is_enabled"]]),
            "error":         None,
        }

    except Exception as exc:
        error_msg = str(exc)
        log.error("Group %s push failed: %s", parent_sku, error_msg)
        # If we created a listing but inventory failed, note the listing_id for cleanup
        return {
            "success":    False,
            "listing_id": listing_id,
            "error":      error_msg,
        }


def _build_draft_listing_payload(group: dict, variants: list[dict]) -> dict:
    """Build the createDraftListing body from a group row."""
    # Minimum price across variants (Etsy shows the range)
    prices = [_variant_price(v) for v in variants]
    min_price = min(prices)

    tags = group.get("tags") or []
    if isinstance(tags, str):
        import json
        tags = json.loads(tags)

    return {
        "title":                _etsy_title_case(group["title"]),
        "description":          group["description"],
        "price":                min_price,
        "quantity":             999,  # overwritten by inventory PUT
        "taxonomy_id":          group.get("taxonomy_id") or 2844,
        "who_made":             group.get("who_made") or "i_did",
        "when_made":            group.get("when_made") or "made_to_order",
        "is_supply":            group.get("is_supply") or False,
        "shipping_profile_id":  group["shipping_profile_id"],
        "return_policy_id":     group["return_policy_id"],
        "readiness_state_id":   group.get("readiness_state_id") or 1402336022581,
        "tags":                 [t for t in [_sanitise_tag(t)[:20] for t in tags[:13]] if t],
        "materials":            ["brushed aluminium"],
        "type":                 "physical",
        "state":                "draft",
        "is_taxable":           True,
        "is_customizable":      False,
        "is_personalizable":    False,
    }
