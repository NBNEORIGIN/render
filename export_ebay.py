"""eBay listing export generator.

Generates eBay Seller Hub bulk upload CSV (Reports tab format).
This is the current supported format — File Exchange is deprecated.
Upload via: Seller Hub → Listings → Bulk actions → Upload listings
"""
import csv
import io

# eBay category for signs
EBAY_CATEGORY_ID = "166675"

# Size mappings
SIZE_CONFIG = {
    "dracula": {"display": "9.5 x 9.5 cm", "price": 10.99},
    "saville": {"display": "11 x 9.5 cm", "price": 11.99},
    "dick": {"display": "14 x 9 cm", "price": 12.99},
    "barzan": {"display": "19 x 14 cm", "price": 15.99},
    "baby_jesus": {"display": "29 x 19 cm", "price": 17.99},
}

COLOR_DISPLAY = {
    "silver": "Silver",
    "gold": "Gold",
    "white": "White",
}


def generate_ebay_csv(products: list[dict], base_url: str = "") -> str:
    """
    Generate eBay Seller Hub bulk listing upload CSV.

    Upload via Seller Hub → Listings → Bulk actions → Upload listings.
    Template format matches eBay's current Seller Hub Reports tab.
    """
    output = io.StringIO()

    # Seller Hub bulk upload format (current as of 2025)
    headers = [
        "*Action",
        "ItemID",
        "*Title",
        "*Category",
        "ConditionID",
        "ConditionDescription",
        "*Description",
        "PicURL",
        "*Quantity",
        "*StartPrice",
        "*Currency",
        "*Format",
        "*Duration",
        "BuyItNowPrice",
        "*Location",
        "*Country",
        "PaymentInstructions",
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
    ]

    writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()

    for product in products:
        m_number = product.get("m_number", "")
        description = product.get("description", "")
        size = product.get("size", "dracula").lower()
        color = product.get("color", "silver").lower()

        size_info = SIZE_CONFIG.get(size, SIZE_CONFIG["dracula"])
        color_display = COLOR_DISPLAY.get(color, "Silver")

        title = f"{description} Sign - {size_info['display']} Brushed Aluminium Self-Adhesive"
        if len(title) > 80:
            title = title[:77] + "..."

        desc_html = (
            f"<p><strong>{description}</strong></p>"
            f"<p>Premium quality brushed aluminium sign with UV-resistant printing.</p>"
            f"<ul>"
            f"<li>Size: {size_info['display']}</li>"
            f"<li>Material: 1mm Brushed Aluminium</li>"
            f"<li>Finish: {color_display}</li>"
            f"<li>Mounting: Self-Adhesive (peel and stick)</li>"
            f"<li>Fully weatherproof — indoor and outdoor use</li>"
            f"</ul>"
        )

        pic_url = ""
        if base_url:
            base = base_url.rstrip("/")
            pic_url = "|".join([
                f"{base}/images/{m_number}/{m_number}-001.jpg",
                f"{base}/images/{m_number}/{m_number}-002.jpg",
                f"{base}/images/{m_number}/{m_number}-003.jpg",
                f"{base}/images/{m_number}/{m_number}-004.jpg",
            ])

        row = {
            "*Action": "Add",
            "ItemID": "",
            "*Title": title,
            "*Category": EBAY_CATEGORY_ID,
            "ConditionID": "1000",
            "ConditionDescription": "New",
            "*Description": desc_html,
            "PicURL": pic_url,
            "*Quantity": "10",
            "*StartPrice": str(size_info["price"]),
            "*Currency": "GBP",
            "*Format": "FixedPrice",
            "*Duration": "GTC",
            "BuyItNowPrice": "",
            "*Location": "Alnwick, Northumberland",
            "*Country": "GB",
            "PaymentInstructions": "",
            "*DispatchTimeMax": "3",
            "*ReturnsAcceptedOption": "ReturnsAccepted",
            "ReturnsWithinOption": "Days_30",
            "RefundOption": "MoneyBack",
            "ShippingCostPaidByOption": "Buyer",
            "*ShippingType": "Flat",
            "ShippingService-1:Option": "UK_RoyalMailSecondClassStandard",
            "ShippingService-1:Cost": "0.00",
            "ShippingService-1:FreeShipping": "True",
            "C:Brand": "NorthByNorthEast",
            "C:Material": "Aluminium",
            "C:Colour": color_display,
            "C:Size": size_info["display"],
            "C:Type": "Sign",
            "C:Mounting Type": "Self-Adhesive",
        }

        writer.writerow(row)

    return output.getvalue()
