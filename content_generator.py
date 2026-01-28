"""AI content generator for Amazon product listings using Claude API."""
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from jobs import Job

# Product size dimensions in cm
SIZE_DIMENSIONS_CM = {
    "dracula": (9.5, 9.5),
    "saville": (11.0, 9.5),
    "dick": (14.0, 9.0),
    "barzan": (19.0, 14.0),
    "baby_jesus": (29.0, 19.0),
}

# Color display names
COLOR_DISPLAY_NAMES = {
    "silver": "Silver Brushed Aluminium",
    "white": "White Aluminium",
    "gold": "Gold Brushed Aluminium",
}

# Size display names
SIZE_DISPLAY_NAMES = {
    "dracula": "9.5 x 9.5 cm",
    "saville": "11 x 9.5 cm",
    "dick": "14 x 9 cm",
    "barzan": "19 x 14 cm",
    "baby_jesus": "29 x 19 cm",
}

# Amazon size_map values
SIZE_MAP_VALUES = {
    "dracula": "XS",
    "saville": "S",
    "dick": "M",
    "barzan": "L",
    "baby_jesus": "XL",
}

# Pricing by size
SIZE_PRICING = {
    "dracula": 10.99,
    "saville": 11.99,
    "dick": 12.99,
    "barzan": 15.99,
    "baby_jesus": 17.99,
}

# Mounting type info
MOUNTING_INFO = {
    "self_adhesive": {
        "description": "Self-adhesive backing with peel-off liner",
        "title_suffix": "Self Adhesive",
        "bullet_point": "Easy peel-and-stick installation - no tools required",
    },
    "screw_mount": {
        "description": "Pre-drilled holes for screw mounting",
        "title_suffix": "Screw Mount",
        "bullet_point": "Pre-drilled mounting holes for secure permanent installation",
    },
}


@dataclass
class AmazonContent:
    """Generated Amazon listing content."""
    title: str
    description: str
    bullet_points: list[str]
    search_terms: str


def generate_content_for_product(
    product: dict,
    api_key: str,
    brand_name: str = "NorthByNorthEast",
    theme: str = "",
    use_cases: str = "",
) -> AmazonContent:
    """
    Generate Amazon SEO-optimized content using Claude API.
    
    Args:
        product: Product dict from database
        api_key: Anthropic API key
        brand_name: Brand name for listings
        theme: Human-provided signage theme/description
        use_cases: Target use cases for the signage
        
    Returns:
        AmazonContent with title, description, bullets, and search terms
    """
    client = anthropic.Anthropic(api_key=api_key)
    
    # Extract sign text from product
    if theme:
        sign_text = theme
    else:
        text_lines = [
            product.get("text_line_1", ""),
            product.get("text_line_2", ""),
            product.get("text_line_3", ""),
        ]
        sign_text = " ".join([t for t in text_lines if t])
        if not sign_text and product.get("description"):
            sign_text = product["description"]
    
    size = product.get("size", "dracula").lower()
    color = product.get("color", "silver").lower()
    mounting_type = product.get("mounting_type", "self_adhesive")
    
    length_cm, width_cm = SIZE_DIMENSIONS_CM.get(size, (10, 10))
    color_display = COLOR_DISPLAY_NAMES.get(color, color.title())
    mounting = MOUNTING_INFO.get(mounting_type, MOUNTING_INFO["self_adhesive"])
    
    use_cases_str = use_cases if use_cases else "offices, warehouses, car parks, shops, public spaces"
    
    prompt = f"""Generate Amazon UK product listing content for a sign product.

PRODUCT DETAILS:
- Sign Theme/Message: "{sign_text}"
- Size: {length_cm} x {width_cm} cm
- Color/Finish: {color_display}
- Material: Brushed Aluminium
- Mounting: {mounting["description"]}
- Features: Weatherproof, UV-resistant print, rounded corners
- Target Use Cases: {use_cases_str}

REQUIREMENTS:
1. TITLE (max 200 characters): Include primary keyword, key features, size in cm. Format: "[Sign Text] Sign – [dimensions]cm [Material], Weatherproof, {mounting["title_suffix"]}". Do NOT include brand name in title.

2. DESCRIPTION (150-300 words): Detailed, persuasive product description. Emphasise the mounting method ({mounting["description"]}). Include material, dimensions, features, and use cases.

3. BULLET POINTS (exactly 5): Benefit-focused, keyword-rich. Each bullet should be 150-250 characters. Cover:
   - Material quality and finish
   - UV printing durability
   - {mounting["bullet_point"]}
   - Weatherproof construction
   - Clear messaging/visibility

4. SEARCH TERMS (max 250 characters): Backend keywords separated by spaces. Do NOT repeat words from title. Include synonyms, related terms, misspellings.

Respond in JSON format:
{{
    "title": "...",
    "description": "...",
    "bullet_points": ["...", "...", "...", "...", "..."],
    "search_terms": "..."
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = message.content[0].text
    
    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        raise ValueError(f"Could not parse JSON from Claude response: {response_text[:200]}")
    
    data = json.loads(json_match.group())
    
    return AmazonContent(
        title=data["title"][:200],
        description=data["description"],
        bullet_points=data["bullet_points"][:5],
        search_terms=data["search_terms"][:250],
    )


def generate_content_job(
    job: Job,
    products: list[dict],
    theme: str = "",
    use_cases: str = "",
) -> dict:
    """
    Background job to generate content for multiple products.
    
    Args:
        job: Job object for progress updates
        products: List of product dicts
        theme: Theme for content generation
        use_cases: Target use cases
    
    Returns:
        Dict with results per product
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    job.total = len(products)
    results = {}
    
    for i, product in enumerate(products):
        m_number = product["m_number"]
        job.message = f"Generating content for {m_number}..."
        job.progress = i
        
        try:
            content = generate_content_for_product(
                product, api_key, theme=theme, use_cases=use_cases
            )
            results[m_number] = {
                "success": True,
                "title": content.title,
                "description": content.description,
                "bullet_points": content.bullet_points,
                "search_terms": content.search_terms,
            }
        except Exception as e:
            logging.error(f"Failed to generate content for {m_number}: {e}")
            results[m_number] = {"success": False, "error": str(e)}
    
    job.progress = job.total
    job.message = f"Completed {len(products)} products"
    return results


if __name__ == "__main__":
    # Test content generation
    from dotenv import load_dotenv
    load_dotenv()
    
    test_product = {
        "m_number": "TEST001",
        "description": "No Entry Without Permission",
        "size": "saville",
        "color": "silver",
        "mounting_type": "self_adhesive",
        "text_line_1": "NO ENTRY",
        "text_line_2": "WITHOUT PERMISSION",
        "text_line_3": "",
    }
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        content = generate_content_for_product(test_product, api_key)
        print(f"Title: {content.title}")
        print(f"Description: {content.description[:100]}...")
        print(f"Bullets: {len(content.bullet_points)}")
        print(f"Search terms: {content.search_terms[:50]}...")
    else:
        print("ANTHROPIC_API_KEY not set - skipping test")
