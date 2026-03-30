"""Configuration for Render — NBNE sign product generator."""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'render.db'}")

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Authentication — set APP_TOKEN in environment; leave empty to disable (dev only)
APP_TOKEN = os.environ.get("APP_TOKEN", "")

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# eBay API
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "")
EBAY_RU_NAME = os.environ.get("EBAY_RU_NAME", "")
EBAY_ENVIRONMENT = os.environ.get("EBAY_ENVIRONMENT", "production")
EBAY_MERCHANT_LOCATION_KEY = os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "default")

# Image storage — serve images from own server.
# In production on Render.com, set IMAGES_DIR to a mounted persistent disk path.
IMAGES_DIR = Path(os.environ.get("IMAGES_DIR", str(BASE_DIR / "static" / "images")))

# Public base URL for marketplace image links (must be publicly reachable by Amazon/Etsy/eBay)
# e.g. https://render.nbnesigns.co.uk
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://render.nbnesigns.co.uk").rstrip("/")

# Product blanks seed data — populates the blanks DB table on first run.
# After first run, source of truth is the blanks table; add new blanks via the UI.
# Format: slug -> {width_mm, height_mm, is_circular, display, amazon_code,
#                  sign_bounds: (x, y, w, h), peel_bounds: (x, y, w, h) or None,
#                  has_portrait: bool}
BLANK_SEEDS = {
    "dracula": {
        "width_mm": 95, "height_mm": 95, "is_circular": True,
        "display": "9.5 x 9.5 cm", "amazon_code": "XS",
        "sign_bounds": (37, 27, 85, 85), "peel_bounds": None,
        "has_portrait": False,
    },
    "saville": {
        "width_mm": 115, "height_mm": 95, "is_circular": False,
        "display": "11 x 9.5 cm", "amazon_code": "S",
        "sign_bounds": (30, 24, 93, 73), "peel_bounds": None,
        "has_portrait": False,
    },
    "dick": {
        "width_mm": 140, "height_mm": 90, "is_circular": False,
        "display": "14 x 9 cm", "amazon_code": "M",
        "sign_bounds": (25, 30, 110, 60), "peel_bounds": None,
        "has_portrait": True,
    },
    "barzan": {
        "width_mm": 194, "height_mm": 143, "is_circular": False,
        "display": "19 x 14 cm", "amazon_code": "L",
        "sign_bounds": (25, 25, 164, 113), "peel_bounds": None,
        "has_portrait": False,
    },
    "baby_jesus": {
        "width_mm": 290, "height_mm": 190, "is_circular": False,
        "display": "29 x 19 cm", "amazon_code": "XL",
        "sign_bounds": (25, 25, 240, 140), "peel_bounds": (8, 120, 130, 85),
        "has_portrait": True,
    },
}

# Colors
COLORS = {
    "silver": "Silver",
    "gold": "Gold",
    "white": "White",
}

# Brand
BRAND_NAME = "NorthByNorthEast"
