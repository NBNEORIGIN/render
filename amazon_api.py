"""
Amazon SP-API — Listings Items publisher for Render.

Self-contained LWA token refresh (no dependency on Cairn's token cache —
Docker networking prevents container-to-container calls).
"""
import os
import time
import json
import logging
import requests

log = logging.getLogger(__name__)

# ── LWA token cache ────────────────────────────────────────────────────────────
_token_cache: dict = {"token": None, "expires_at": 0.0}

LISTINGS_API_HOST = "https://sellingpartnerapi-eu.amazon.com"
MARKETPLACE_ID = "A1F83G8C2ARO7P"  # Amazon UK


def get_sp_api_token() -> str:
    """Return a valid LWA access token, refreshing if within 60 s of expiry."""
    if time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    r = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": os.environ["AMAZON_REFRESH_TOKEN_EU"],
            "client_id": os.environ["AMAZON_CLIENT_ID"],
            "client_secret": os.environ["AMAZON_CLIENT_SECRET"],
        },
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"]
    return _token_cache["token"]


def _headers() -> dict:
    return {
        "x-amz-access-token": get_sp_api_token(),
        "Content-Type": "application/json",
    }


# ── Payload builders ───────────────────────────────────────────────────────────

def _mk_str(value, lang: str = "en_GB") -> list:
    return [{"value": value, "language_tag": lang, "marketplace_id": MARKETPLACE_ID}]


def _mk_val(value) -> list:
    return [{"value": value, "marketplace_id": MARKETPLACE_ID}]


def _image_locators(image_urls: list) -> dict:
    attrs = {}
    if not image_urls:
        return attrs
    attrs["main_product_image_locator"] = [
        {"media_location": image_urls[0], "marketplace_id": MARKETPLACE_ID}
    ]
    for i, url in enumerate(image_urls[1:8], 1):
        attrs[f"other_product_image_locator_{i}"] = [
            {"media_location": url, "marketplace_id": MARKETPLACE_ID}
        ]
    return attrs


def build_parent_payload(listing: dict) -> dict:
    return {
        "productType": "SIGNAGE",
        "requirements": "LISTING",
        "attributes": {
            "item_name":        _mk_str(listing["title_base"]),
            "brand":            _mk_val(listing["brand_name"]),
            "product_description": _mk_str(listing.get("description") or ""),
            "generic_keyword":  _mk_val(listing.get("generic_keywords") or ""),
            "recommended_browse_nodes": _mk_val(listing.get("recommended_browse_nodes") or ""),
            "variation_theme":  [{"name": listing.get("variation_theme") or "Size & Colour",
                                  "marketplace_id": MARKETPLACE_ID}],
            "parentage_level":  _mk_val("parent"),
            "child_parent_sku_relationship": [],
            "batteries_required": _mk_val(bool(listing.get("batteries_required"))),
            "supplier_declared_dg_hz_regulation": _mk_val("not_applicable"),
            "country_of_origin": _mk_val("GB"),
        },
    }


def build_child_payload(listing: dict, variant: dict) -> dict:
    image_urls = variant.get("image_urls") or []
    if isinstance(image_urls, str):
        try:
            image_urls = json.loads(image_urls)
        except Exception:
            image_urls = []

    # Filter out empty bullet points
    bullet_points = [
        {"value": v, "language_tag": "en_GB", "marketplace_id": MARKETPLACE_ID}
        for v in [
            listing.get("bullet_point_1"),
            listing.get("bullet_point_2"),
            listing.get("bullet_point_3"),
            listing.get("bullet_point_4"),
            listing.get("bullet_point_5"),
        ]
        if v
    ]

    attrs = {
        "item_name":        _mk_str(variant["title_full"]),
        "brand":            _mk_val(listing["brand_name"]),
        "product_description": _mk_str(listing.get("description") or ""),
        "externally_assigned_product_identifier": [
            {"type": "ean", "value": variant["ean"], "marketplace_id": MARKETPLACE_ID}
        ],
        "part_number":      _mk_val(variant["sku"]),
        "manufacturer":     _mk_val("North By North East Print and Sign Limited"),
        "bullet_point":     bullet_points,
        "generic_keyword":  _mk_val(listing.get("generic_keywords") or ""),
        "color":            _mk_val(variant.get("colour_name") or ""),
        "color_map":        _mk_val(variant.get("colour_map") or variant.get("colour_name") or ""),
        "size":             _mk_val(variant.get("size_name") or ""),
        "size_map":         _mk_val(variant.get("size_map") or variant.get("size_name") or ""),
        "relationship_type": _mk_val("variation"),
        "child_parent_sku_relationship": [{
            "child_relationship_type": "variation",
            "parent_sku": listing["internal_ref"] + "_PARENT",
            "marketplace_id": MARKETPLACE_ID,
        }],
        "parentage_level":  _mk_val("child"),
        "purchasable_offer": [{
            "currency": "GBP",
            "our_price": [{"schedule": [{"value_with_tax": float(variant["list_price"])}]}],
            "marketplace_id": MARKETPLACE_ID,
        }],
        "fulfillment_availability": [{
            "fulfillment_channel_code": variant.get("fulfillment_channel") or "AMAZON_UK_RAFN",
            "quantity": variant.get("quantity") or 5,
            "marketplace_id": MARKETPLACE_ID,
        }],
        "merchant_shipping_group": _mk_val(
            variant.get("shipping_group") or "RM Tracked 48 Free, 24 -- £2.99, SD -- £7.99"
        ),
        "condition_type":   _mk_val("new_new"),
        "batteries_required": _mk_val(False),
        "supplier_declared_dg_hz_regulation": _mk_val("not_applicable"),
        "country_of_origin": _mk_val("GB"),
        "recommended_browse_nodes": _mk_val(listing.get("recommended_browse_nodes") or ""),
    }

    if variant.get("length_cm") and variant.get("width_cm"):
        attrs["item_dimensions"] = [{
            "length": {"value": float(variant["length_cm"]), "unit": "centimeters"},
            "width":  {"value": float(variant["width_cm"]),  "unit": "centimeters"},
            "marketplace_id": MARKETPLACE_ID,
        }]

    if variant.get("style_name"):
        attrs["style"] = _mk_val(variant["style_name"])

    attrs.update(_image_locators(image_urls))
    return {"productType": "SIGNAGE", "requirements": "LISTING", "attributes": attrs}


# ── API calls ──────────────────────────────────────────────────────────────────

def put_listing(seller_id: str, sku: str, payload: dict) -> requests.Response:
    url = f"{LISTINGS_API_HOST}/listings/2021-08-01/items/{seller_id}/{sku}"
    params = {"marketplaceIds": MARKETPLACE_ID}
    return requests.put(url, headers=_headers(), params=params,
                        json=payload, timeout=30)


def get_listing(seller_id: str, sku: str) -> requests.Response:
    url = f"{LISTINGS_API_HOST}/listings/2021-08-01/items/{seller_id}/{sku}"
    params = {"marketplaceIds": MARKETPLACE_ID, "includedData": "summaries"}
    return requests.get(url, headers=_headers(), params=params, timeout=30)


# ── Publish sequence ───────────────────────────────────────────────────────────

def _log_spapi(conn, sku: str, operation: str, request_payload: dict,
               response_status: int, response_body: dict,
               error_code: str | None = None):
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO render_spapi_log "
            "(sku, operation, request_payload, response_status, response_body, error_code) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (sku, operation, json.dumps(request_payload),
             response_status, json.dumps(response_body), error_code),
        )
    except Exception as e:
        log.warning("Failed to write spapi_log: %s", e)


def _update_variant_status(conn, sku: str, status: str, asin: str | None = None):
    cur = conn.cursor()
    if asin:
        cur.execute(
            "UPDATE render_catalogue_variant "
            "SET amazon_status=%s, amazon_asin=%s, amazon_published_at=NOW(), updated_at=NOW() "
            "WHERE sku=%s",
            (status, asin, sku),
        )
    else:
        cur.execute(
            "UPDATE render_catalogue_variant "
            "SET amazon_status=%s, amazon_published_at=NOW(), updated_at=NOW() "
            "WHERE sku=%s",
            (status, sku),
        )


def publish_listing(seller_id: str, listing: dict, variants: list, conn) -> dict:
    """
    Publish parent + all child variants to Amazon UK.

    Returns a result dict: { parent: {status, code}, children: [{sku, status, code}] }
    Follows the required sequence: parent first, then children 0.2s apart.
    """
    results = {"parent": {}, "children": []}
    parent_sku = listing["internal_ref"] + "_PARENT"

    # 1. PUT parent
    parent_payload = build_parent_payload(listing)
    r = put_listing(seller_id, parent_sku, parent_payload)
    parent_body = {}
    try:
        parent_body = r.json()
    except Exception:
        parent_body = {"raw": r.text}
    _log_spapi(conn, parent_sku, "create_parent", parent_payload, r.status_code, parent_body)
    results["parent"] = {"sku": parent_sku, "status_code": r.status_code, "ok": r.status_code == 202}
    if r.status_code not in (200, 202):
        error_code = parent_body.get("errors", [{}])[0].get("code") if isinstance(parent_body, dict) else None
        results["parent"]["error"] = parent_body
        results["parent"]["error_code"] = error_code
        return results  # abort — children require parent

    # 2. PUT each child
    for variant in variants:
        sku = variant["sku"]
        child_result = {"sku": sku}

        if not variant.get("ean"):
            child_result["status"] = "skipped"
            child_result["error"] = "No EAN assigned"
            results["children"].append(child_result)
            continue

        child_payload = build_child_payload(listing, variant)
        r = put_listing(seller_id, sku, child_payload)
        child_body = {}
        try:
            child_body = r.json()
        except Exception:
            child_body = {"raw": r.text}

        error_code = None
        if r.status_code in (200, 202):
            _update_variant_status(conn, sku, "pending")
            child_result["status"] = "pending"
            child_result["status_code"] = r.status_code
        else:
            error_code = child_body.get("errors", [{}])[0].get("code") if isinstance(child_body, dict) else None
            _update_variant_status(conn, sku, "error")
            child_result["status"] = "error"
            child_result["status_code"] = r.status_code
            child_result["error"] = child_body
            child_result["error_code"] = error_code

        _log_spapi(conn, sku, "create_child", child_payload, r.status_code, child_body, error_code)
        results["children"].append(child_result)
        time.sleep(0.2)  # SP-API rate limit: 5 req/s

    return results


def poll_asins(seller_id: str, conn) -> list:
    """
    For all variants with amazon_status='pending' and published >15 min ago,
    attempt to retrieve ASIN. Returns list of {sku, result} dicts.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sku FROM render_catalogue_variant
        WHERE amazon_status = 'pending'
          AND amazon_published_at < NOW() - INTERVAL '15 minutes'
    """)
    pending = [row[0] for row in cur.fetchall()]

    results = []
    for sku in pending:
        r = get_listing(seller_id, sku)
        body = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}

        _log_spapi(conn, sku, "poll_asin", {}, r.status_code, body)

        if r.status_code == 200:
            summaries = body.get("summaries", [])
            asin = summaries[0].get("asin") if summaries else None
            if asin:
                _update_variant_status(conn, sku, "live", asin=asin)
                results.append({"sku": sku, "result": "live", "asin": asin})
            else:
                results.append({"sku": sku, "result": "still_pending"})
        elif r.status_code == 404:
            results.append({"sku": sku, "result": "not_found"})
        else:
            error_code = body.get("errors", [{}])[0].get("code") if isinstance(body, dict) else None
            if error_code in ("THROTTLED",):
                results.append({"sku": sku, "result": "throttled"})
            else:
                _update_variant_status(conn, sku, "error")
                results.append({"sku": sku, "result": "error", "code": error_code})

        time.sleep(0.2)

    return results
