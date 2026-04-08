"""Seed initial Etsy listing groups and assign existing render_products to them.

Run once from the project root (inside Docker or with DB access):
    python etsy_seed_groups.py

This is idempotent — safe to re-run. Existing group rows are not overwritten.
"""
import logging
import sys
import os

# Allow running from render/ directory
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

from config import ETSY_SHIPPING_PROFILE_ID, ETSY_RETURN_POLICY_ID, ETSY_TAXONOMY_ID
from models import init_db, get_db, release_db, dict_cursor, EtsyListingGroup, Product
from etsy_taxonomy_properties import size_display_from_slug, color_display_from_slug


# ── Group definitions ─────────────────────────────────────────────────────────

GROUPS = [
    {
        "parent_sku":          "PLEASE_USE_OTHER_DOOR",
        "title":               "Please Use Other Door Sign – Brushed Aluminium, Weatherproof, Self-Adhesive",
        "description": (
            "<p><strong>Please Use Other Door</strong></p>"
            "<p>Premium quality brushed aluminium sign with UV-resistant printing. "
            "Direct customers and visitors clearly and professionally.</p>"
            "<ul>"
            "<li>Material: 1mm Brushed Aluminium</li>"
            "<li>Mounting: Self-Adhesive (peel and stick — no tools required)</li>"
            "<li>Fully weatherproof — indoor and outdoor use</li>"
            "<li>Available in Silver, Gold, and White finishes</li>"
            "<li>5 sizes to suit any door or entrance</li>"
            "<li>Made in Great Britain</li>"
            "</ul>"
        ),
        "taxonomy_id":         ETSY_TAXONOMY_ID,
        "shipping_profile_id": ETSY_SHIPPING_PROFILE_ID,
        "return_policy_id":    ETSY_RETURN_POLICY_ID,
        "readiness_state_id":  1402336022581,
        "who_made":            "i_did",
        "when_made":           "made_to_order",
        "is_supply":           False,
        "option1_property":    "size",
        "option2_property":    "primary_color",
        "tags": [
            "use other door", "aluminium sign", "door sign",
            "weatherproof sign", "office sign", "self adhesive",
            "brushed aluminium", "silver sign", "gold sign",
            "uk made", "made in britain", "professional sign", "entrance sign",
        ],
        "styles": [],
        # Pattern to match render_products.description for auto-assignment
        "_description_match": "Please Use Other Door",
    },
    {
        "parent_sku":          "BY_APPOINTMENT_ONLY",
        "title":               "By Appointment Only Sign – Brushed Aluminium, Weatherproof, Self-Adhesive",
        "description": (
            "<p><strong>By Appointment Only</strong></p>"
            "<p>Premium quality brushed aluminium sign with UV-resistant printing. "
            "Clearly communicate your appointment-only policy.</p>"
            "<ul>"
            "<li>Material: 1mm Brushed Aluminium</li>"
            "<li>Mounting: Self-Adhesive (peel and stick — no tools required)</li>"
            "<li>Fully weatherproof — indoor and outdoor use</li>"
            "<li>Available in Silver, Gold, and White finishes</li>"
            "<li>5 sizes to suit any premises</li>"
            "<li>Made in Great Britain</li>"
            "</ul>"
        ),
        "taxonomy_id":         ETSY_TAXONOMY_ID,
        "shipping_profile_id": ETSY_SHIPPING_PROFILE_ID,
        "return_policy_id":    ETSY_RETURN_POLICY_ID,
        "readiness_state_id":  1402336022581,
        "who_made":            "i_did",
        "when_made":           "made_to_order",
        "is_supply":           False,
        "option1_property":    "size",
        "option2_property":    "primary_color",
        "tags": [
            "appointment only", "aluminium sign", "business sign",
            "weatherproof sign", "office sign", "self adhesive",
            "brushed aluminium", "silver sign", "gold sign",
            "uk made", "professional sign", "appointment sign", "clinic sign",
        ],
        "styles": [],
        "_description_match": "By Appointment Only",
        # This group was already pushed by ShopUploader — adopt existing listing
        "_etsy_listing_id":   4485090559,
    },
]


def run():
    init_db()

    all_products = Product.all()
    log.info("Found %d products in render_products", len(all_products))

    for g_def in GROUPS:
        desc_match = g_def.pop("_description_match", None)
        existing_listing_id = g_def.pop("_etsy_listing_id", None)

        # Create or get the group
        group_id = EtsyListingGroup.upsert(g_def)
        log.info("Group %s → id=%d", g_def["parent_sku"], group_id)

        # If this group was already pushed externally, record the listing_id
        if existing_listing_id:
            group = EtsyListingGroup.get(group_id)
            if not group.get("etsy_listing_id"):
                EtsyListingGroup.set_push_result(
                    group_id, existing_listing_id, "adopted", ""
                )
                log.info("  Adopted existing Etsy listing %s", existing_listing_id)

        # Assign matching products to this group
        if desc_match:
            matching = [
                p for p in all_products
                if desc_match.lower() in (p.get("description") or "").lower()
            ]
            log.info("  Matched %d products for '%s'", len(matching), desc_match)

            for p in matching:
                size_slug = (p.get("size") or "saville").lower()
                color_slug = (p.get("color") or "silver").lower()
                opt1 = size_display_from_slug(size_slug)
                opt2 = color_display_from_slug(color_slug)

                EtsyListingGroup.assign_product(p["m_number"], group_id, opt1, opt2)
                log.info("    Assigned %s → size=%r color=%r", p["m_number"], opt1, opt2)

    # Summary
    for g in EtsyListingGroup.all():
        log.info(
            "Group %-30s id=%-4d variants=%-3d etsy_listing_id=%s",
            g["parent_sku"], g["id"], g["variant_count"],
            g.get("etsy_listing_id") or "(none)",
        )


if __name__ == "__main__":
    run()
