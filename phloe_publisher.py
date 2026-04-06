"""Phloe shop publisher — pushes QA-approved products to app.nbnesigns.co.uk/shop.

Uses JWT auth against Phloe Django API. Mirrors etsy_api.py pattern.
Products appear on the NBNE website shop with Stripe checkout.
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

from config import (
    PHLOE_API_URL, PHLOE_TENANT_SLUG, PHLOE_API_TOKEN,
    IMAGES_DIR,
)
from export_etsy import SIZE_CONFIG, COLOR_DISPLAY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class PhloeAuth:
    """JWT authentication for Phloe API."""

    def __init__(self, api_url: str, tenant_slug: str):
        self.api_url = api_url.rstrip("/")
        self.tenant_slug = tenant_slug
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expires_at: float = 0

    def login(self, username: str, password: str) -> str:
        """Authenticate and get JWT access token."""
        resp = requests.post(
            f"{self.api_url}/api/auth/login/",
            json={"username": username, "password": password},
            headers={"X-Tenant-Slug": self.tenant_slug},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access"]
        self._refresh_token = data.get("refresh")
        self._expires_at = time.time() + 28800  # 8 hour lifetime
        logging.info("Authenticated with Phloe as %s", username)
        return self._access_token

    def refresh(self) -> str:
        """Refresh the JWT access token."""
        if not self._refresh_token:
            raise RuntimeError("No refresh token — call login() first")
        resp = requests.post(
            f"{self.api_url}/api/auth/token/refresh/",
            json={"refresh": self._refresh_token},
            headers={"X-Tenant-Slug": self.tenant_slug},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access"]
        self._expires_at = time.time() + 28800
        return self._access_token

    def get_headers(self) -> dict:
        """Get auth headers with auto-refresh."""
        if not self._access_token:
            raise RuntimeError("Not authenticated — call login() first")
        if time.time() >= self._expires_at - 300:
            try:
                self.refresh()
            except Exception:
                raise RuntimeError("Token expired and refresh failed — re-login required")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-Tenant-Slug": self.tenant_slug,
            "Content-Type": "application/json",
        }

    def get_upload_headers(self) -> dict:
        """Get auth headers for multipart upload (no Content-Type)."""
        headers = self.get_headers()
        del headers["Content-Type"]
        return headers


# Module-level auth instance — login once, reuse
_phloe_auth: Optional[PhloeAuth] = None


def _get_auth() -> PhloeAuth:
    """Get or create Phloe auth instance."""
    global _phloe_auth
    if _phloe_auth is None:
        _phloe_auth = PhloeAuth(PHLOE_API_URL, PHLOE_TENANT_SLUG)
        # Login with service account credentials from env
        username = os.environ.get("PHLOE_USERNAME", "toby@nbnesigns.com")
        password = os.environ.get("PHLOE_PASSWORD", "")
        if not password:
            raise RuntimeError("PHLOE_PASSWORD not set — cannot authenticate with Phloe")
        _phloe_auth.login(username, password)
    return _phloe_auth


def push_product_to_phloe(product: dict, content: Optional[dict] = None) -> dict:
    """Push a single product to Phloe shop.

    Args:
        product: Product dict from render_products
        content: Optional AI content from render_product_content

    Returns:
        {m_number, product_id, status, error, url}
    """
    m_number = product.get("m_number", "")
    size = product.get("size", "dracula").lower()
    color = product.get("color", "silver").lower()
    description_text = product.get("description", "Sign")

    size_info = SIZE_CONFIG.get(size, SIZE_CONFIG["dracula"])
    color_name = COLOR_DISPLAY.get(color, "Silver")

    # Build product data for Phloe
    name = f"{description_text} Sign \u2013 {size_info['display']}"
    subtitle = f"{color_name} Brushed Aluminium"

    if content and content.get("description"):
        desc_body = content["description"]
    else:
        desc_body = (
            f"Professional brushed aluminium sign with {color_name.lower()} finish. "
            f"UV-printed for crystal-clear visibility. Self-adhesive backing \u2014 no drilling. "
            f"Weatherproof and UV-resistant. Size: {size_info['display']}."
        )

    product_data = {
        "name": name[:255],
        "subtitle": subtitle[:255],
        "description": desc_body,
        "category": "Signs",
        "price": str(size_info["price"]),
        "track_stock": True,
        "stock_quantity": 999,
        "active": True,
        "sort_order": 0,
    }

    try:
        auth = _get_auth()
        headers = auth.get_headers()
        base = PHLOE_API_URL.rstrip("/")

        # Create product
        resp = requests.post(
            f"{base}/api/shop/products/",
            json=product_data,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        created = resp.json()
        product_id = created["id"]
        logging.info("Created Phloe product %s for %s: %s", product_id, m_number, name)

        # Upload images
        image_nums = ["001", "006", "002", "003", "004"]  # main, lifestyle, dims, peel, rear
        for img_num in image_nums:
            image_path = IMAGES_DIR / m_number / f"{m_number} - {img_num}.jpg"
            if not image_path.exists():
                image_path = IMAGES_DIR / m_number / f"{m_number}-{img_num}.jpg"
            if not image_path.exists():
                continue

            with open(image_path, "rb") as f:
                files = {"images": (image_path.name, f, "image/jpeg")}
                img_resp = requests.post(
                    f"{base}/api/shop/products/{product_id}/images/",
                    headers=auth.get_upload_headers(),
                    files=files,
                    timeout=30,
                )
                if img_resp.ok:
                    logging.info("Uploaded %s to Phloe product %s", img_num, product_id)
                else:
                    logging.warning("Image upload %s failed: %s", img_num, img_resp.text[:200])

        return {
            "m_number": m_number,
            "product_id": product_id,
            "status": "success",
            "error": None,
            "url": f"{base}/shop",
        }

    except requests.HTTPError as e:
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                error_msg = str(e.response.json())
            except Exception:
                error_msg = e.response.text[:500]
        logging.error("Failed to push %s to Phloe: %s", m_number, error_msg)
        return {"m_number": m_number, "product_id": None, "status": "failed", "error": error_msg}

    except Exception as e:
        logging.error("Unexpected error pushing %s to Phloe: %s", m_number, e)
        return {"m_number": m_number, "product_id": None, "status": "failed", "error": str(e)}


def push_products_to_phloe(products: list[dict], content_map: dict = None) -> list[dict]:
    """Push a batch of products to Phloe shop.

    Args:
        products: List of product dicts (must be QA approved)
        content_map: Optional {m_number: content_dict}

    Returns:
        List of result dicts
    """
    if content_map is None:
        content_map = {}

    results = []
    for product in products:
        if product.get("qa_status") != "approved":
            results.append({
                "m_number": product.get("m_number"),
                "product_id": None,
                "status": "rejected",
                "error": f"QA status is '{product.get('qa_status')}', not 'approved'",
            })
            continue

        content = content_map.get(product.get("m_number"))
        result = push_product_to_phloe(product, content)
        results.append(result)

    return results
