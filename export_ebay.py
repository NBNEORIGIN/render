"""eBay listing export generator.

Generates eBay-compatible CSV from product database.
"""
import csv
import io
import logging
from typing import Optional

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

# Color mappings
COLOR_DISPLAY = {
    "silver": "Silver",
    "gold": "Gold", 
    "white": "White",
}

# Mounting info
MOUNTING_INFO = {
    "self_adhesive": "Self Adhesive",
    "screw_mount": "Screw Mount",
}


def generate_ebay_csv(products: list[dict], r2_public_url: str = "") -> str:
    """
    Generate eBay File Exchange compatible CSV.
    
    Args:
        products: List of product dicts from database
        r2_public_url: Base URL for R2 images
    
    Returns:
        CSV string
    """
    output = io.StringIO()
    
    # eBay File Exchange headers
    headers = [
        "Action(SiteID=UK)",
        "ItemID",
        "Category",
        "Title",
        "Description",
        "ConditionID",
        "PicURL",
        "Quantity",
        "StartPrice",
        "Format",
        "Duration",
        "PayPalAccepted",
        "PayPalEmailAddress",
        "ShippingType",
        "ShippingService-1:Option",
        "ShippingService-1:Cost",
        "DispatchTimeMax",
        "ReturnsAcceptedOption",
        "RefundOption",
        "ReturnsWithinOption",
        "ShippingCostPaidByOption",
        "*C:Brand",
        "*C:Material",
        "*C:Type",
        "*C:Colour",
        "*C:Size",
    ]
    
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    
    for product in products:
        m_number = product.get("m_number", "")
        description = product.get("description", "")
        size = product.get("size", "dracula").lower()
        color = product.get("color", "silver").lower()
        mounting = product.get("mounting_type", "self_adhesive")
        
        size_info = SIZE_CONFIG.get(size, SIZE_CONFIG["dracula"])
        color_display = COLOR_DISPLAY.get(color, "Silver")
        mounting_display = MOUNTING_INFO.get(mounting, "Self Adhesive")
        
        # Build title
        title = f"{description} Sign - {size_info['display']} Aluminium {mounting_display}"
        if len(title) > 80:
            title = title[:77] + "..."
        
        # Build description HTML
        desc_html = f"""<p><strong>{description}</strong></p>
<p>Premium quality aluminium sign with UV-resistant printing.</p>
<ul>
<li>Size: {size_info['display']}</li>
<li>Material: Brushed Aluminium</li>
<li>Finish: {color_display}</li>
<li>Mounting: {mounting_display}</li>
<li>Weatherproof and durable</li>
</ul>"""
        
        # Image URL
        pic_url = ""
        if r2_public_url:
            pic_url = f"{r2_public_url}/{m_number}/{m_number}_main.jpg"
        
        row = {
            "Action(SiteID=UK)": "Add",
            "ItemID": "",
            "Category": EBAY_CATEGORY_ID,
            "Title": title,
            "Description": desc_html,
            "ConditionID": "1000",  # New
            "PicURL": pic_url,
            "Quantity": "10",
            "StartPrice": str(size_info["price"]),
            "Format": "FixedPrice",
            "Duration": "GTC",
            "PayPalAccepted": "1",
            "PayPalEmailAddress": "",
            "ShippingType": "Flat",
            "ShippingService-1:Option": "UK_RoyalMailSecondClassStandard",
            "ShippingService-1:Cost": "0",
            "DispatchTimeMax": "3",
            "ReturnsAcceptedOption": "ReturnsAccepted",
            "RefundOption": "MoneyBack",
            "ReturnsWithinOption": "Days_30",
            "ShippingCostPaidByOption": "Buyer",
            "*C:Brand": "NorthByNorthEast",
            "*C:Material": "Aluminium",
            "*C:Type": "Safety Sign",
            "*C:Colour": color_display,
            "*C:Size": size_info["display"],
        }
        
        writer.writerow(row)
    
    return output.getvalue()


if __name__ == "__main__":
    # Test
    test_products = [
        {"m_number": "M1001", "description": "No Entry", "size": "saville", "color": "silver"},
        {"m_number": "M1002", "description": "Staff Only", "size": "dick", "color": "gold"},
    ]
    print(generate_ebay_csv(test_products))
