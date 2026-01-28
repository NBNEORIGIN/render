"""Configuration for SignMaker web app."""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'signmaker.db'}")

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Cloudflare R2
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "productimages")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# eBay API
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "")
EBAY_RU_NAME = os.environ.get("EBAY_RU_NAME", "")
EBAY_ENVIRONMENT = os.environ.get("EBAY_ENVIRONMENT", "production")
EBAY_MERCHANT_LOCATION_KEY = os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "default")

# Product sizes (internal name -> dimensions in cm, Amazon size code)
SIZES = {
    "dracula": {"dimensions": (9.5, 9.5), "code": "XS", "display": "9.5 x 9.5 cm"},
    "saville": {"dimensions": (11.0, 9.5), "code": "S", "display": "11 x 9.5 cm"},
    "dick": {"dimensions": (14.0, 9.0), "code": "M", "display": "14 x 9 cm"},
    "barzan": {"dimensions": (19.0, 14.0), "code": "L", "display": "19 x 14 cm"},
    "baby_jesus": {"dimensions": (29.0, 19.0), "code": "XL", "display": "29 x 19 cm"},
}

# Colors
COLORS = {
    "silver": "Silver",
    "gold": "Gold",
    "white": "White",
}

# Brand
BRAND_NAME = "NorthByNorthEast"
