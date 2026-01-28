"""eBay API integration for SignMaker.

Creates listings via eBay Inventory API and auto-promotes via Marketing API.
"""
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

from ebay_auth import get_ebay_auth_from_env, EbayAuth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# eBay category for signs
EBAY_CATEGORY_ID = "166675"

# Default ad rate for Promoted Listings (Cost Per Sale)
DEFAULT_AD_RATE_PERCENT = "5.0"

# Policies file path
POLICIES_FILE = Path(__file__).parent / "ebay_policies.json"


@dataclass
class EbayProduct:
    """Product data for eBay listing."""
    sku: str
    title: str
    description: str
    color: str
    size: str
    price: float
    image_urls: list[str] = field(default_factory=list)
    bullet_points: list[str] = field(default_factory=list)


class EbayMarketingManager:
    """Manager for eBay Marketing API (Promoted Listings)."""
    
    def __init__(self, auth: EbayAuth, marketplace_id: str = "EBAY_GB"):
        self.auth = auth
        self.marketplace_id = marketplace_id
        self.marketing_base = f"{auth.api_base}/sell/marketing/v1"
    
    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        url = f"{self.marketing_base}/{endpoint}"
        headers = self.auth.get_auth_headers()
        headers["Content-Language"] = "en-GB"
        
        response = requests.request(method, url, headers=headers, json=data, params=params)
        
        if response.status_code == 201:
            location = response.headers.get("Location", "")
            campaign_id = location.split("/")[-1] if location else ""
            return {"campaignId": campaign_id, "location": location}
        
        if response.status_code == 204:
            return {}
        
        if not response.ok:
            logging.error("Marketing API Error: %s %s", response.status_code, response.text)
            response.raise_for_status()
        
        return response.json() if response.text else {}
    
    def create_general_campaign(self, campaign_name: str, ad_rate_percent: str = DEFAULT_AD_RATE_PERCENT) -> Optional[str]:
        """Create a Promoted Listings General strategy campaign (Cost Per Sale)."""
        start_date = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        campaign_data = {
            "campaignName": campaign_name,
            "marketplaceId": self.marketplace_id,
            "startDate": start_date,
            "fundingStrategy": {
                "fundingModel": "COST_PER_SALE",
                "bidPercentage": ad_rate_percent,
            },
        }
        
        try:
            result = self._make_request("POST", "ad_campaign", data=campaign_data)
            campaign_id = result.get("campaignId")
            logging.info("Created Promoted Listings campaign: %s (ID: %s) at %s%% ad rate", campaign_name, campaign_id, ad_rate_percent)
            return campaign_id
        except requests.HTTPError as e:
            logging.error("Failed to create campaign: %s", e)
            return None
    
    def add_listing_to_campaign(self, campaign_id: str, listing_id: str, bid_percentage: str = DEFAULT_AD_RATE_PERCENT, inventory_reference_id: Optional[str] = None) -> bool:
        """Add a listing to an existing Promoted Listings campaign."""
        if inventory_reference_id:
            ad_data = {
                "inventoryReferenceId": inventory_reference_id,
                "inventoryReferenceType": "INVENTORY_ITEM_GROUP",
                "bidPercentage": bid_percentage,
            }
            try:
                self._make_request("POST", f"ad_campaign/{campaign_id}/create_ads_by_inventory_reference", data=ad_data)
                logging.info("Added inventory group %s to campaign %s", inventory_reference_id, campaign_id)
                return True
            except requests.HTTPError as e:
                logging.warning("Inventory reference approach failed, trying listing ID: %s", e)
        
        ad_data = {"listingId": listing_id, "bidPercentage": bid_percentage}
        try:
            self._make_request("POST", f"ad_campaign/{campaign_id}/ad", data=ad_data)
            logging.info("Added listing %s to campaign %s", listing_id, campaign_id)
            return True
        except requests.HTTPError as e:
            logging.error("Failed to add listing to campaign: %s", e)
            return False
    
    def get_campaigns(self) -> list:
        """Get existing campaigns."""
        try:
            result = self._make_request("GET", "ad_campaign", params={"marketplace_id": self.marketplace_id})
            return result.get("campaigns", [])
        except requests.HTTPError:
            return []
    
    def find_or_create_general_campaign(self, campaign_name: str = "SignMaker Auto Promotion", ad_rate_percent: str = DEFAULT_AD_RATE_PERCENT) -> Optional[str]:
        """Find an existing general campaign or create a new one."""
        campaigns = self.get_campaigns()
        for campaign in campaigns:
            if campaign.get("campaignName") == campaign_name:
                logging.info("Found existing campaign: %s (ID: %s)", campaign_name, campaign.get("campaignId"))
                return campaign.get("campaignId")
        return self.create_general_campaign(campaign_name, ad_rate_percent)


class EbayInventoryManager:
    """Manager for eBay Inventory API operations."""
    
    def __init__(self, auth: EbayAuth, marketplace_id: str = "EBAY_GB"):
        self.auth = auth
        self.marketplace_id = marketplace_id
        self.inventory_base = f"{auth.api_base}/sell/inventory/v1"
    
    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        url = f"{self.inventory_base}/{endpoint}"
        headers = self.auth.get_auth_headers()
        headers["Content-Language"] = "en-GB"
        
        response = requests.request(method, url, headers=headers, json=data, params=params)
        
        if response.status_code == 204:
            return {}
        
        if not response.ok:
            logging.error("API Error: %s %s", response.status_code, response.text)
            response.raise_for_status()
        
        return response.json() if response.text else {}
    
    def create_or_replace_inventory_item(self, sku: str, title: str, description: str, image_urls: list[str], aspects: dict) -> None:
        """Create or replace an inventory item."""
        inventory_item = {
            "availability": {"shipToLocationAvailability": {"quantity": 100}},
            "condition": "NEW",
            "product": {
                "title": title[:80],
                "description": description,
                "aspects": aspects,
                "imageUrls": image_urls[:12] if image_urls else [],
            },
        }
        self._make_request("PUT", f"inventory_item/{sku}", data=inventory_item)
        logging.info("Created/updated inventory item: %s", sku)
    
    def get_offers_by_sku(self, sku: str) -> list:
        """Get existing offers for a SKU."""
        try:
            result = self._make_request("GET", "offer", params={"sku": sku, "marketplace_id": self.marketplace_id})
            return result.get("offers", [])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def withdraw_offer_by_sku(self, sku: str) -> bool:
        """Withdraw any published offers for a SKU."""
        try:
            offers = self.get_offers_by_sku(sku)
            for offer in offers:
                if offer.get("status") == "PUBLISHED":
                    offer_id = offer["offerId"]
                    try:
                        self._make_request("POST", f"offer/{offer_id}/withdraw")
                        logging.info("Withdrew offer %s for SKU %s", offer_id, sku)
                    except requests.HTTPError:
                        pass
            return True
        except Exception as e:
            logging.error("Failed to withdraw offers for SKU %s: %s", sku, e)
            return False
    
    def delete_offer_by_sku(self, sku: str) -> bool:
        """Delete all offers for a SKU."""
        try:
            offers = self.get_offers_by_sku(sku)
            for offer in offers:
                try:
                    self._make_request("DELETE", f"offer/{offer['offerId']}")
                    logging.info("Deleted offer %s for SKU %s", offer["offerId"], sku)
                except requests.HTTPError:
                    pass
            return True
        except Exception as e:
            logging.error("Failed to delete offers for SKU %s: %s", sku, e)
            return False
    
    def create_offer(self, sku: str, price: float, policy_ids: dict, category_id: str = EBAY_CATEGORY_ID) -> str:
        """Create an offer for an inventory item."""
        offer = {
            "sku": sku,
            "marketplaceId": self.marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 100,
            "categoryId": category_id,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
                "returnPolicyId": policy_ids["returnPolicyId"],
                "paymentPolicyId": policy_ids["paymentPolicyId"],
            },
            "pricingSummary": {"price": {"value": str(price), "currency": "GBP"}},
            "merchantLocationKey": os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "default"),
        }
        result = self._make_request("POST", "offer", data=offer)
        offer_id = result["offerId"]
        logging.info("Created offer: %s for SKU: %s at £%.2f", offer_id, sku, price)
        return offer_id
    
    def delete_inventory_item_group(self, group_key: str) -> bool:
        """Delete an inventory item group."""
        try:
            self._make_request("DELETE", f"inventory_item_group/{group_key}")
            logging.info("Deleted inventory item group: %s", group_key)
            return True
        except requests.HTTPError as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                return True
            return False
    
    def create_or_replace_inventory_item_group(self, group_key: str, title: str, description: str, image_urls: list[str], aspects: dict, variation_specs: dict[str, list[str]], sku_list: list[str], variant_images: Optional[list[dict]] = None) -> None:
        """Create or replace an inventory item group for multi-variation listings."""
        specifications = [{"name": name, "values": values} for name, values in variation_specs.items()]
        
        group_data = {
            "title": title[:80],
            "description": description,
            "imageUrls": image_urls[:12],
            "aspects": aspects,
            "variantSKUs": sku_list,
            "variesBy": {
                "aspectsImageVariesBy": ["Size"],
                "specifications": specifications,
            },
        }
        
        if variant_images:
            group_data["variesBy"]["variantImages"] = variant_images
        
        self._make_request("PUT", f"inventory_item_group/{group_key}", data=group_data)
        logging.info("Created/updated inventory item group: %s with %d SKUs", group_key, len(sku_list))
    
    def publish_inventory_item_group(self, group_key: str, policy_ids: dict, category_id: str = EBAY_CATEGORY_ID) -> Optional[str]:
        """Publish an inventory item group as a multi-variation listing."""
        publish_data = {
            "inventoryItemGroupKey": group_key,
            "marketplaceId": self.marketplace_id,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
                "returnPolicyId": policy_ids["returnPolicyId"],
                "paymentPolicyId": policy_ids["paymentPolicyId"],
            },
            "categoryId": category_id,
        }
        
        try:
            result = self._make_request("POST", "offer/publish_by_inventory_item_group", data=publish_data)
            listing_id = result.get("listingId")
            logging.info("Published inventory group %s as listing: %s", group_key, listing_id)
            return listing_id
        except requests.HTTPError as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    errors = error_data.get('errors', [])
                    if errors:
                        error_msg = errors[0].get('message', str(e))
                        # Check if it's a 404 "Offer not available" error
                        if e.response.status_code == 404 and 'not available' in error_msg.lower():
                            logging.warning("Inventory group %s has stale offers. Try deleting the group and recreating.", group_key)
                except:
                    pass
            logging.error("Failed to publish inventory group %s: %s", group_key, error_msg)
            return None


def load_policy_ids() -> dict:
    """Load saved policy IDs from file."""
    if not POLICIES_FILE.exists():
        raise FileNotFoundError("Policy IDs not found. Run ebay_setup_policies.py first.")
    with POLICIES_FILE.open("r") as f:
        return json.load(f)


def build_ebay_description(product: dict, bullet_points: list[str] = None) -> str:
    """Build eBay-optimized HTML description."""
    desc = product.get("description", "")
    
    html_parts = [
        '<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">',
        f'<h2>{desc}</h2>',
        '<p>Premium quality brushed aluminium sign with UV-resistant printing.</p>',
    ]
    
    if bullet_points:
        html_parts.append('<h3>Features:</h3><ul>')
        for bullet in bullet_points:
            html_parts.append(f'<li>{bullet}</li>')
        html_parts.append('</ul>')
    else:
        html_parts.append('''<ul>
<li>High-quality brushed aluminium construction</li>
<li>UV-resistant printing for long-lasting clarity</li>
<li>Weatherproof and durable</li>
<li>Self-adhesive backing for easy installation</li>
<li>Rounded corners for safety</li>
</ul>''')
    
    html_parts.append('</div>')
    return '\n'.join(html_parts)


def create_ebay_listing(products: list[dict], policy_ids: dict, promote: bool = True, ad_rate: str = DEFAULT_AD_RATE_PERCENT, dry_run: bool = False) -> Optional[str]:
    """
    Create eBay listing from SignMaker products.
    
    Args:
        products: List of product dicts from database
        policy_ids: eBay policy IDs
        promote: Whether to auto-promote the listing
        ad_rate: Ad rate percentage for promotion
        dry_run: Preview without creating
    
    Returns:
        Listing ID if successful
    """
    if not products:
        return None
    
    auth = get_ebay_auth_from_env()
    marketplace_id = policy_ids.get("marketplaceId", "EBAY_GB")
    manager = EbayInventoryManager(auth, marketplace_id=marketplace_id)
    marketing_manager = EbayMarketingManager(auth, marketplace_id=marketplace_id) if promote else None
    
    # Group key from first product
    first_product = products[0]
    group_key = re.sub(r'[^a-zA-Z0-9_]', '_', first_product.get("m_number", "listing").lower())
    
    logging.info("Creating eBay listing: %s with %d products", group_key, len(products))
    
    # Collect variation values
    size_values = set()
    color_values = set()
    sku_list = []
    all_images = []
    
    # Size display mapping
    size_display = {
        "dracula": "9.5 x 9.5 cm",
        "saville": "11 x 9.5 cm",
        "dick": "14 x 9 cm",
        "barzan": "19 x 14 cm",
        "baby_jesus": "29 x 19 cm",
    }
    
    # Price mapping
    size_prices = {
        "dracula": 10.99,
        "saville": 11.99,
        "dick": 12.99,
        "barzan": 15.99,
        "baby_jesus": 17.99,
    }
    
    color_display = {"silver": "Silver", "gold": "Gold", "white": "White"}
    
    for product in products:
        sku = product.get("m_number", "")
        size = product.get("size", "dracula").lower()
        color = product.get("color", "silver").lower()
        
        size_name = size_display.get(size, size)
        color_name = color_display.get(color, color.title())
        price = size_prices.get(size, 12.99)
        
        size_values.add(size_name)
        color_values.add(color_name)
        
        # Build aspects
        aspects = {
            "Size": [size_name],
            "Colour": [color_name],
            "Brand": ["NorthByNorthEast"],
            "Material": ["Aluminium"],
            "Type": ["Safety Sign"],
        }
        
        # Build description
        description = build_ebay_description(product)
        
        # Build title
        title = f"{product.get('description', 'Sign')} - {size_name} Aluminium"[:80]
        
        # Image URLs (from R2) - format: M1288%20-%20001.jpg
        # Includes lifestyle image (006.jpg) as 5th image
        r2_url = os.environ.get("R2_PUBLIC_URL", "")
        image_urls = []
        if r2_url:
            for img_num in ["001", "002", "003", "004", "006"]:
                # URL encode the space in filename
                image_urls.append(f"{r2_url}/{sku}%20-%20{img_num}.jpg")
        
        if dry_run:
            logging.info("[DRY RUN] Would create inventory item: %s (%s, %s) at £%.2f", sku, size_name, color_name, price)
        else:
            # Clean up existing offers first
            try:
                manager.withdraw_offer_by_sku(sku)
                manager.delete_offer_by_sku(sku)
            except Exception as e:
                logging.debug("Cleanup for %s: %s", sku, e)
            
            # Create inventory item
            manager.create_or_replace_inventory_item(sku, title, description, image_urls, aspects)
            
            # Always create a fresh offer for each SKU
            try:
                manager.create_offer(sku, price, policy_ids)
                logging.info("Created offer for SKU: %s at £%.2f", sku, price)
            except requests.HTTPError as e:
                # If offer already exists (409 conflict), that's OK
                if hasattr(e, 'response') and e.response.status_code == 409:
                    logging.info("Offer already exists for %s, continuing", sku)
                else:
                    logging.warning("Could not create offer for %s: %s", sku, e)
        
        sku_list.append(sku)
        all_images.extend(image_urls[:3])
    
    # Common aspects
    common_aspects = {
        "Brand": ["NorthByNorthEast"],
        "Material": ["Aluminium"],
        "Type": ["Safety Sign"],
    }
    
    # Variation specs
    variation_specs = {
        "Size": sorted(list(size_values)),
        "Colour": sorted(list(color_values)),
    }
    
    if dry_run:
        logging.info("[DRY RUN] Would create inventory group: %s", group_key)
        return "DRY_RUN"
    
    # Delete existing inventory item group to clear stale offers
    try:
        manager.delete_inventory_item_group(group_key)
        logging.info("Deleted existing inventory group: %s", group_key)
    except Exception as e:
        logging.debug("No existing group to delete or error: %s", e)
    
    # Create inventory item group
    group_title = f"{first_product.get('description', 'Sign')} - Aluminium Sign"[:80]
    group_description = build_ebay_description(first_product)
    
    manager.create_or_replace_inventory_item_group(
        group_key=group_key,
        title=group_title,
        description=group_description,
        image_urls=all_images[:12],
        aspects=common_aspects,
        variation_specs=variation_specs,
        sku_list=sku_list,
    )
    
    # Publish
    listing_id = manager.publish_inventory_item_group(group_key, policy_ids)
    
    if listing_id and promote and marketing_manager:
        logging.info("Waiting 10 seconds for listing to propagate...")
        time.sleep(10)
        
        campaign_id = marketing_manager.find_or_create_general_campaign(ad_rate_percent=ad_rate)
        if campaign_id:
            success = marketing_manager.add_listing_to_campaign(
                campaign_id=campaign_id,
                listing_id=listing_id,
                bid_percentage=ad_rate,
                inventory_reference_id=group_key,
            )
            if success:
                logging.info("Listing promoted with %s%% ad rate", ad_rate)
    
    return listing_id
