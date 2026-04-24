"""Configuration for Render — NBNE sign product generator."""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database — Cairn PostgreSQL on nbne1 (render_ prefixed tables in claw DB)
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://cairn:cairn_nbne_2026@192.168.1.228:5432/claw")

# API Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Default users seeded on first run (email -> display name)
DEFAULT_USERS = {
    "gabby@nbnesigns.com": "Gabby",
    "toby@nbnesigns.com": "Toby",
    "sanna@nbnesigns.com": "Sanna",
    "ivan@nbnesigns.com": "Ivan",
    "ben@nbnesigns.com": "Ben",
    "jo@nbnesigns.com": "Jo",
    "nyo@nbnesigns.com": "Nyo",
}
DEFAULT_PASSWORD = "!49Monkswood"

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# SMTP — IONOS outbound mail for bug reports
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.ionos.co.uk")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
BUG_REPORT_RECIPIENTS = ["toby@nbnesigns.com", "gabby@nbnesigns.com"]

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

# Etsy API
ETSY_API_KEY = os.environ.get("ETSY_API_KEY", "")
ETSY_SHARED_SECRET = os.environ.get("ETSY_SHARED_SECRET", "")
ETSY_SHOP_ID = int(os.environ.get("ETSY_SHOP_ID", "11706740"))
ETSY_REDIRECT_URI = os.environ.get("ETSY_REDIRECT_URI", "http://localhost:5000/etsy/oauth/callback")
ETSY_TAXONOMY_ID = 2844              # Signs category
ETSY_SHIPPING_PROFILE_ID = 208230423243
ETSY_RETURN_POLICY_ID = 1074420280634

# Phloe shop integration
PHLOE_API_URL = os.environ.get("PHLOE_API_URL", "https://app.nbnesigns.co.uk")
PHLOE_TENANT_SLUG = os.environ.get("PHLOE_TENANT_SLUG", "mind-department")
PHLOE_API_TOKEN = os.environ.get("PHLOE_API_TOKEN", "")

# Brand
BRAND_NAME = "NorthByNorthEast"
