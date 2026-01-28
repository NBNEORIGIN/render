"""eBay Business Policies Setup for SignMaker.

One-time setup script to create or retrieve fulfillment, return, and payment policies.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

from ebay_auth import get_ebay_auth_from_env, EbayAuth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Default policy configurations for UK signage business
DEFAULT_FULFILLMENT_POLICY = {
    "name": "Standard UK Shipping",
    "description": "Standard shipping for signage products within the UK",
    "marketplaceId": "EBAY_GB",
    "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
    "handlingTime": {"value": 1, "unit": "DAY"},
    "shippingOptions": [
        {
            "optionType": "DOMESTIC",
            "costType": "FLAT_RATE",
            "shippingServices": [
                {
                    "sortOrder": 1,
                    "shippingCarrierCode": "Royal Mail",
                    "shippingServiceCode": "UK_RoyalMailSecondClassStandard",
                    "shippingCost": {"value": "0.00", "currency": "GBP"},
                    "additionalShippingCost": {"value": "0.00", "currency": "GBP"},
                    "freeShipping": True,
                    "buyerResponsibleForShipping": False,
                    "buyerResponsibleForPickup": False,
                }
            ],
        }
    ],
}

DEFAULT_RETURN_POLICY = {
    "name": "30 Day Returns",
    "description": "30-day return policy for signage products",
    "marketplaceId": "EBAY_GB",
    "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
    "returnsAccepted": True,
    "returnPeriod": {"value": 30, "unit": "DAY"},
    "refundMethod": "MONEY_BACK",
    "returnShippingCostPayer": "BUYER",
}

DEFAULT_PAYMENT_POLICY = {
    "name": "Immediate Payment",
    "description": "Immediate payment required via eBay managed payments",
    "marketplaceId": "EBAY_GB",
    "categoryTypes": [{"name": "ALL_EXCLUDING_MOTORS_VEHICLES"}],
    "immediatePay": True,
    "paymentMethods": [{"paymentMethodType": "PERSONAL_CHECK"}],
}

POLICIES_FILE = Path(__file__).parent / "ebay_policies.json"


class EbayPoliciesManager:
    """Manager for eBay business policies."""
    
    def __init__(self, auth: EbayAuth, marketplace_id: str = "EBAY_GB"):
        self.auth = auth
        self.marketplace_id = marketplace_id
        self.base_url = f"{auth.api_base}/sell/account/v1"
    
    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        headers = self.auth.get_auth_headers()
        
        response = requests.request(method, url, headers=headers, json=data, params=params)
        
        if response.status_code == 204:
            return {}
        
        if not response.ok:
            logging.error("API Error: %s %s", response.status_code, response.text)
            response.raise_for_status()
        
        return response.json() if response.text else {}
    
    def get_fulfillment_policies(self) -> list:
        result = self._make_request("GET", "fulfillment_policy", params={"marketplace_id": self.marketplace_id})
        return result.get("fulfillmentPolicies", [])
    
    def get_return_policies(self) -> list:
        result = self._make_request("GET", "return_policy", params={"marketplace_id": self.marketplace_id})
        return result.get("returnPolicies", [])
    
    def get_payment_policies(self) -> list:
        result = self._make_request("GET", "payment_policy", params={"marketplace_id": self.marketplace_id})
        return result.get("paymentPolicies", [])
    
    def create_fulfillment_policy(self, policy: dict) -> dict:
        return self._make_request("POST", "fulfillment_policy", data=policy)
    
    def create_return_policy(self, policy: dict) -> dict:
        return self._make_request("POST", "return_policy", data=policy)
    
    def create_payment_policy(self, policy: dict) -> dict:
        return self._make_request("POST", "payment_policy", data=policy)
    
    def find_or_create_fulfillment_policy(self, name: str = "Standard UK Shipping") -> str:
        policies = self.get_fulfillment_policies()
        for policy in policies:
            if policy.get("name") == name:
                logging.info("Found existing fulfillment policy: %s (%s)", name, policy["fulfillmentPolicyId"])
                return policy["fulfillmentPolicyId"]
        
        config = DEFAULT_FULFILLMENT_POLICY.copy()
        config["name"] = name
        config["marketplaceId"] = self.marketplace_id
        
        result = self.create_fulfillment_policy(config)
        policy_id = result["fulfillmentPolicyId"]
        logging.info("Created fulfillment policy: %s (%s)", name, policy_id)
        return policy_id
    
    def find_or_create_return_policy(self, name: str = "30 Day Returns") -> str:
        policies = self.get_return_policies()
        for policy in policies:
            if policy.get("name") == name:
                logging.info("Found existing return policy: %s (%s)", name, policy["returnPolicyId"])
                return policy["returnPolicyId"]
        
        config = DEFAULT_RETURN_POLICY.copy()
        config["name"] = name
        config["marketplaceId"] = self.marketplace_id
        
        result = self.create_return_policy(config)
        policy_id = result["returnPolicyId"]
        logging.info("Created return policy: %s (%s)", name, policy_id)
        return policy_id
    
    def find_or_create_payment_policy(self, name: str = "Immediate Payment") -> str:
        policies = self.get_payment_policies()
        for policy in policies:
            if policy.get("name") == name:
                logging.info("Found existing payment policy: %s (%s)", name, policy["paymentPolicyId"])
                return policy["paymentPolicyId"]
        
        config = DEFAULT_PAYMENT_POLICY.copy()
        config["name"] = name
        config["marketplaceId"] = self.marketplace_id
        
        result = self.create_payment_policy(config)
        policy_id = result["paymentPolicyId"]
        logging.info("Created payment policy: %s (%s)", name, policy_id)
        return policy_id
    
    def setup_all_policies(self) -> dict:
        """Set up all required policies and return their IDs."""
        policy_ids = {
            "fulfillmentPolicyId": self.find_or_create_fulfillment_policy(),
            "returnPolicyId": self.find_or_create_return_policy(),
            "paymentPolicyId": self.find_or_create_payment_policy(),
            "marketplaceId": self.marketplace_id,
        }
        
        with POLICIES_FILE.open("w") as f:
            json.dump(policy_ids, f, indent=2)
        logging.info("Saved policy IDs to %s", POLICIES_FILE)
        
        return policy_ids
    
    def list_all_policies(self) -> None:
        print("\n=== Fulfillment Policies ===")
        for policy in self.get_fulfillment_policies():
            print(f"  - {policy['name']} (ID: {policy['fulfillmentPolicyId']})")
        
        print("\n=== Return Policies ===")
        for policy in self.get_return_policies():
            print(f"  - {policy['name']} (ID: {policy['returnPolicyId']})")
        
        print("\n=== Payment Policies ===")
        for policy in self.get_payment_policies():
            print(f"  - {policy['name']} (ID: {policy['paymentPolicyId']})")


def load_policy_ids() -> dict:
    """Load saved policy IDs from file."""
    if not POLICIES_FILE.exists():
        raise FileNotFoundError("Policy IDs not found. Run 'python ebay_setup_policies.py' first.")
    with POLICIES_FILE.open("r") as f:
        return json.load(f)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="eBay Business Policies Setup")
    parser.add_argument("--list", action="store_true", help="List existing policies")
    parser.add_argument("--marketplace", type=str, default="EBAY_GB", help="Marketplace ID")
    args = parser.parse_args()
    
    try:
        auth = get_ebay_auth_from_env()
        manager = EbayPoliciesManager(auth, marketplace_id=args.marketplace)
        
        if args.list:
            manager.list_all_policies()
        else:
            print("\nSetting up eBay business policies...")
            policy_ids = manager.setup_all_policies()
            
            print("\n=== Policy Setup Complete ===")
            print(f"Fulfillment Policy ID: {policy_ids['fulfillmentPolicyId']}")
            print(f"Return Policy ID:      {policy_ids['returnPolicyId']}")
            print(f"Payment Policy ID:     {policy_ids['paymentPolicyId']}")
            print(f"\nPolicy IDs saved to: {POLICIES_FILE}")
    except ValueError as e:
        print(f"\nError: {e}")
        print("Please run 'python ebay_auth.py' first to authenticate.")
    except Exception as e:
        logging.error("Error: %s", e)
