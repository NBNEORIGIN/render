"""Etsy API v3 integration for Render.

Creates draft listings, uploads images, and manages inventory via Etsy API.
Mirrors ebay_api.py pattern. Rate limited to 5 QPS.
"""
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

from etsy_auth import get_etsy_auth_from_env, EtsyAuth
from config import (
    ETSY_SHOP_ID, ETSY_TAXONOMY_ID, ETSY_SHIPPING_PROFILE_ID,
    ETSY_RETURN_POLICY_ID, PUBLIC_BASE_URL, IMAGES_DIR,
)
from export_etsy import SIZE_CONFIG, COLOR_DISPLAY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ETSY_API_BASE = "https://api.etsy.com/v3"


def _etsy_title_case(text: str) -> str:
    """Convert text to title case safe for Etsy (no more than 3 words with 2+ consecutive caps)."""
    return text.title()


def _sanitise_tag(tag: str) -> str:
    """Strip characters Etsy doesn't allow in tags (only letters, numbers, spaces)."""
    return re.sub(r"[^a-zA-Z0-9 ]", "", tag).strip()

# Rate limiting: 5 QPS
_last_request_time = 0.0
_MIN_INTERVAL = 0.22  # slightly over 200ms to stay under 5 QPS


def _rate_limit():
    """Simple rate limiter for Etsy 5 QPS limit."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.time()


class EtsyListingManager:
    """Manager for Etsy Listings API operations."""

    def __init__(self, auth: EtsyAuth, shop_id: int = ETSY_SHOP_ID):
        self.auth = auth
        self.shop_id = shop_id
        self.base_url = f"{ETSY_API_BASE}/application/shops/{shop_id}"

    def _request(self, method: str, endpoint: str, data: Optional[dict] = None,
                 files: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """Make a rate-limited request to Etsy API."""
        _rate_limit()
        url = f"{self.base_url}/{endpoint}" if not endpoint.startswith("http") else endpoint

        if files:
            headers = self.auth.get_upload_headers()
            response = requests.request(method, url, headers=headers, data=data, files=files, params=params)
        else:
            headers = self.auth.get_auth_headers()
            response = requests.request(method, url, headers=headers, json=data, params=params)

        if response.status_code == 204:
            return {}

        if not response.ok:
            logging.error("Etsy API %s %s: %s %s", method, endpoint, response.status_code, response.text)
            response.raise_for_status()

        return response.json() if response.text else {}

    def create_draft_listing(self, product: dict, content: Optional[dict] = None) -> dict:
        """Create a draft listing from a Render product.

        Args:
            product: Product dict from render_products table
            content: Optional AI-generated content from render_product_content

        Returns:
            Etsy listing response dict with listing_id
        """
        size = product.get("size", "dracula").lower()
        color = product.get("color", "silver").lower()
        description_text = product.get("description", "Sign")

        size_info = SIZE_CONFIG.get(size, SIZE_CONFIG["dracula"])
        color_name = COLOR_DISPLAY.get(color, "Silver")

        # Use AI content if available, otherwise generate basic content
        if content and content.get("title"):
            title = _etsy_title_case(content["title"])[:140]
            desc_body = content.get("description", "")
        else:
            title = f"{_etsy_title_case(description_text)} Sign - {size_info['display']} Brushed Aluminium, Weatherproof"
            if len(title) > 140:
                title = title[:137] + "..."
            desc_body = (
                f"Clearly mark your property with this professional brushed aluminium sign. "
                f"Crafted from premium 1mm brushed aluminium with a {color_name.lower()} finish, "
                f"this {size_info['display']} sign delivers maximum impact. "
                f"UV-printed for crystal-clear visibility. Self-adhesive backing - no drilling required. "
                f"Weatherproof and UV-resistant for long-lasting outdoor use. Rounded corners for safety."
            )

        # Generate tags (max 13, each max 20 chars)
        base_tag = description_text.lower()[:20]
        tags = [
            base_tag, "sign", "aluminium", "safety sign",
            color_name.lower()[:20], "office", "weatherproof",
            "self adhesive", "uk", "property", "warning", "metal", "professional",
        ]
        tags = [_sanitise_tag(t)[:20] for t in tags[:13]]
        tags = [t for t in tags if t]  # drop empty after sanitisation

        listing_data = {
            "title": title,
            "description": desc_body,
            "price": size_info["price"],
            "quantity": 999,
            "taxonomy_id": ETSY_TAXONOMY_ID,
            "who_made": "i_did",
            "when_made": "made_to_order",
            "is_supply": False,
            "shipping_profile_id": ETSY_SHIPPING_PROFILE_ID,
            "return_policy_id": ETSY_RETURN_POLICY_ID,
            "readiness_state_id": 1402336022581,
            "tags": tags,
            "materials": ["brushed aluminium"],
            "type": "physical",
            "state": "draft",
            "is_taxable": True,
            "is_customizable": False,
            "is_personalizable": False,
        }

        result = self._request("POST", "listings", data=listing_data)
        listing_id = result.get("listing_id")
        logging.info("Created Etsy draft listing %s for %s: %s",
                      listing_id, product.get("m_number"), title)
        return result

    def upload_image(self, listing_id: int, image_path: Path, rank: int = 1) -> dict:
        """Upload an image to an Etsy listing.

        Args:
            listing_id: Etsy listing ID
            image_path: Local path to the image file
            rank: Display order (1-10)

        Returns:
            Etsy image response dict
        """
        if not image_path.exists():
            logging.warning("Image not found: %s", image_path)
            return {}

        with open(image_path, "rb") as f:
            files = {"image": (image_path.name, f, "image/jpeg")}
            data = {"rank": str(rank), "overwrite": "true"}
            result = self._request(
                "POST",
                f"listings/{listing_id}/images",
                data=data,
                files=files,
            )

        logging.info("Uploaded image rank %d to listing %s: %s", rank, listing_id, image_path.name)
        return result

    def upload_product_images(self, listing_id: int, m_number: str) -> list[dict]:
        """Upload all product images for an M-number to an Etsy listing.

        Image order: 001 (main), 002 (dimensions), 003 (peel-and-stick),
                     004 (rear), 006 (lifestyle)
        """
        results = []
        image_nums = ["001", "002", "003", "004", "006"]

        for rank, img_num in enumerate(image_nums, 1):
            # Try local filesystem first
            image_path = IMAGES_DIR / m_number / f"{m_number} - {img_num}.jpg"
            if not image_path.exists():
                # Try alternate naming (no spaces)
                image_path = IMAGES_DIR / m_number / f"{m_number}-{img_num}.jpg"
            if not image_path.exists():
                logging.warning("Image %s not found for %s, skipping", img_num, m_number)
                continue

            result = self.upload_image(listing_id, image_path, rank=rank)
            results.append(result)

        return results

    def update_listing(self, listing_id: int, data: dict) -> dict:
        """Update an existing listing."""
        return self._request("PUT", f"listings/{listing_id}", data=data)

    def get_listing(self, listing_id: int) -> dict:
        """Get listing details."""
        url = f"{ETSY_API_BASE}/application/listings/{listing_id}"
        return self._request("GET", url)

    def delete_listing(self, listing_id: int) -> dict:
        """Delete a listing."""
        url = f"{ETSY_API_BASE}/application/listings/{listing_id}"
        return self._request("DELETE", url)

    def update_listing_inventory(
        self,
        listing_id: int,
        products: list[dict],
        price_on_property: list[int] = None,
        quantity_on_property: list[int] = None,
        sku_on_property: list[int] = None,
    ) -> dict:
        """PUT full variation inventory for a listing.

        This is a full replace — always send the complete products array.
        Endpoint: PUT /v3/application/listings/{listing_id}/inventory
        """
        url = f"{ETSY_API_BASE}/application/listings/{listing_id}/inventory"
        body = {
            "products": products,
            "price_on_property": price_on_property or [],
            "quantity_on_property": quantity_on_property or [],
            "sku_on_property": sku_on_property or [],
        }
        return self._request("PUT", url, data=body)

    def bind_variation_images(self, listing_id: int, variation_images: list[dict]) -> dict:
        """Bind variation property values to listing images.

        POST /v3/application/shops/{shop_id}/listings/{listing_id}/variation-images
        variation_images: [{property_id, value, image_id}, ...]
        """
        return self._request(
            "POST",
            f"listings/{listing_id}/variation-images",
            data={"variation_images": variation_images},
        )

    def get_variation_images(self, listing_id: int) -> dict:
        """GET current variation-image bindings."""
        return self._request("GET", f"listings/{listing_id}/variation-images")

    def get_draft_listings(self, limit: int = 100, offset: int = 0) -> dict:
        """GET draft listings for the shop."""
        return self._request(
            "GET",
            "listings",
            params={"state": "draft", "limit": limit, "offset": offset},
        )


def publish_products_to_etsy(products: list[dict], content_map: dict = None,
                              dry_run: bool = False) -> list[dict]:
    """Publish a batch of QA-approved products to Etsy as draft listings.

    Args:
        products: List of product dicts from render_products (must be QA approved)
        content_map: Optional {m_number: content_dict} from render_product_content
        dry_run: If True, log actions without making API calls

    Returns:
        List of result dicts: [{m_number, listing_id, status, error}]
    """
    if content_map is None:
        content_map = {}

    auth = get_etsy_auth_from_env()
    manager = EtsyListingManager(auth)
    results = []

    for product in products:
        m_number = product.get("m_number", "")
        qa_status = product.get("qa_status", "")

        # Hard rule: never publish non-approved products
        if qa_status != "approved":
            results.append({
                "m_number": m_number,
                "listing_id": None,
                "status": "rejected",
                "error": f"QA status is '{qa_status}', not 'approved'",
            })
            continue

        if dry_run:
            logging.info("[DRY RUN] Would publish %s to Etsy", m_number)
            results.append({
                "m_number": m_number,
                "listing_id": "DRY_RUN",
                "status": "dry_run",
                "error": None,
            })
            continue

        try:
            content = content_map.get(m_number)
            listing = manager.create_draft_listing(product, content)
            listing_id = listing.get("listing_id")

            if listing_id:
                # Upload images
                manager.upload_product_images(listing_id, m_number)

            results.append({
                "m_number": m_number,
                "listing_id": listing_id,
                "status": "success",
                "error": None,
                "url": f"https://www.etsy.com/listing/{listing_id}" if listing_id else None,
            })

        except requests.HTTPError as e:
            error_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_msg = e.response.json().get("error", str(e))
                except Exception:
                    error_msg = e.response.text[:500]
            logging.error("Failed to publish %s to Etsy: %s", m_number, error_msg)
            results.append({
                "m_number": m_number,
                "listing_id": None,
                "status": "failed",
                "error": error_msg,
            })

        except Exception as e:
            logging.error("Unexpected error publishing %s to Etsy: %s", m_number, e)
            results.append({
                "m_number": m_number,
                "listing_id": None,
                "status": "failed",
                "error": str(e),
            })

    return results
