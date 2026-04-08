"""eBay listing export generator.

Generates eBay Seller Hub bulk upload CSV with variation listings.
Upload via: Seller Hub → Listings → Bulk actions → Upload listings

Variation format:
- One parent row per design (no price/quantity)
- One child row per size × colour variant (price, quantity, EAN)
"""
import csv
import io

EBAY_CATEGORY_ID = "166675"

SIZE_CONFIG = {
    "dracula":    {"display": "9.5 x 9.5 cm", "price": 10.99},
    "saville":    {"display": "11 x 9.5 cm",  "price": 11.99},
    "dick":       {"display": "14 x 9 cm",     "price": 12.99},
    "barzan":     {"display": "19 x 14 cm",    "price": 15.99},
    "baby_jesus": {"display": "29 x 19 cm",    "price": 17.99},
}

COLOR_DISPLAY = {
    "silver": "Silver",
    "gold":   "Gold",
    "white":  "White",
}

# Columns required by eBay Seller Hub variation upload
HEADERS = [
    "*Action",
    "ItemID",
    "Relationship",
    "RelationshipDetails",
    "*Title",
    "*Category",
    "ConditionID",
    "*Description",
    "PicURL",
    "*Quantity",
    "*StartPrice",
    "*Currency",
    "*Format",
    "*Duration",
    "*Location",
    "*Country",
    "*DispatchTimeMax",
    "*ReturnsAcceptedOption",
    "ReturnsWithinOption",
    "RefundOption",
    "ShippingCostPaidByOption",
    "*ShippingType",
    "ShippingService-1:Option",
    "ShippingService-1:Cost",
    "ShippingService-1:FreeShipping",
    "C:Brand",
    "C:Material",
    "C:Colour",
    "C:Size",
    "C:Type",
    "C:Mounting Type",
    "EAN",
]


def generate_ebay_csv(products: list[dict], base_url: str = "") -> str:
    """
    Generate eBay Seller Hub variation listing CSV.

    Groups products by description — each unique description becomes
    one parent listing with size × colour children.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=HEADERS, extrasaction="ignore")
    writer.writeheader()

    # Group by description (= the design)
    groups: dict[str, list[dict]] = {}
    for p in products:
        key = (p.get("description") or "Sign").strip()
        groups.setdefault(key, []).append(p)

    base = base_url.rstrip("/") if base_url else ""

    for description, variants in groups.items():
        title = f"{description} Sign - Brushed Aluminium Weatherproof Self-Adhesive"
        if len(title) > 80:
            title = title[:77] + "..."

        desc_html = (
            f"<p><strong>{description}</strong></p>"
            f"<p>Premium quality brushed aluminium sign with UV-resistant printing. "
            f"Available in multiple sizes and finishes.</p>"
            f"<ul>"
            f"<li>Material: 1mm Brushed Aluminium</li>"
            f"<li>Mounting: Self-Adhesive (peel and stick — no tools required)</li>"
            f"<li>Fully weatherproof — indoor and outdoor use</li>"
            f"<li>Made in Great Britain</li>"
            f"</ul>"
        )

        # Use first variant's images for the parent
        first = variants[0]
        m0 = first.get("m_number", "")
        pic_url = "|".join([
            f"{base}/images/{m0}/{m0}-001.jpg",
            f"{base}/images/{m0}/{m0}-002.jpg",
            f"{base}/images/{m0}/{m0}-003.jpg",
            f"{base}/images/{m0}/{m0}-004.jpg",
        ]) if base else ""

        # Parent row — no price, quantity, EAN, Colour, Size
        parent = {
            "*Action":      "Add",
            "ItemID":       "",
            "Relationship": "",
            "RelationshipDetails": "",
            "*Title":       title,
            "*Category":    EBAY_CATEGORY_ID,
            "ConditionID":  "1000",
            "*Description": desc_html,
            "PicURL":       pic_url,
            "*Quantity":    "",
            "*StartPrice":  "",
            "*Currency":    "GBP",
            "*Format":      "FixedPrice",
            "*Duration":    "GTC",
            "*Location":    "Alnwick, Northumberland",
            "*Country":     "GB",
            "*DispatchTimeMax":      "3",
            "*ReturnsAcceptedOption": "ReturnsAccepted",
            "ReturnsWithinOption":   "Days_30",
            "RefundOption":          "MoneyBack",
            "ShippingCostPaidByOption": "Buyer",
            "*ShippingType":         "Flat",
            "ShippingService-1:Option":      "UK_RoyalMailSecondClassStandard",
            "ShippingService-1:Cost":        "0.00",
            "ShippingService-1:FreeShipping": "True",
            "C:Brand":    "NorthByNorthEast",
            "C:Material": "Aluminium",
            "C:Type":     "Sign",
            "C:Mounting Type": "Self-Adhesive",
        }
        writer.writerow(parent)

        # Child rows — one per variant
        for p in variants:
            m_number = p.get("m_number", "")
            size     = (p.get("size") or "saville").lower()
            color    = (p.get("color") or "silver").lower()
            ean      = p.get("ean") or ""

            size_info     = SIZE_CONFIG.get(size, SIZE_CONFIG["saville"])
            color_display = COLOR_DISPLAY.get(color, "Silver")

            child_pics = "|".join([
                f"{base}/images/{m_number}/{m_number}-001.jpg",
                f"{base}/images/{m_number}/{m_number}-002.jpg",
            ]) if base else ""

            child = {
                "*Action":           "Add",
                "ItemID":            "",
                "Relationship":      "Variation",
                "RelationshipDetails": f"C:Colour={color_display}|C:Size={size_info['display']}",
                "*Title":            title,
                "*Category":         EBAY_CATEGORY_ID,
                "ConditionID":       "1000",
                "*Description":      "",
                "PicURL":            child_pics,
                "*Quantity":         "10",
                "*StartPrice":       str(size_info["price"]),
                "*Currency":         "GBP",
                "*Format":           "FixedPrice",
                "*Duration":         "GTC",
                "*Location":         "",
                "*Country":          "",
                "*DispatchTimeMax":  "",
                "*ReturnsAcceptedOption": "",
                "ReturnsWithinOption":    "",
                "RefundOption":           "",
                "ShippingCostPaidByOption": "",
                "*ShippingType":     "",
                "ShippingService-1:Option":       "",
                "ShippingService-1:Cost":         "",
                "ShippingService-1:FreeShipping":  "",
                "C:Brand":    "NorthByNorthEast",
                "C:Material": "Aluminium",
                "C:Colour":   color_display,
                "C:Size":     size_info["display"],
                "C:Type":     "Sign",
                "C:Mounting Type": "Self-Adhesive",
                "EAN":        ean,
            }
            writer.writerow(child)

    return output.getvalue()
