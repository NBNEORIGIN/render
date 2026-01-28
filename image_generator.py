"""Image generator for SignMaker - creates product images from SVG templates.

Uses Playwright for SVG rendering (replaces Inkscape dependency).
"""
import base64
import csv
import logging
import math
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from lxml import etree
from PIL import Image

# Disable PIL decompression bomb check for large product images
Image.MAX_IMAGE_PIXELS = None

from svg_renderer import render_svg_to_bytes
from r2_storage import upload_png_and_jpeg
from jobs import Job

# Namespaces
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

NSMAP = {
    None: SVG_NS,
    "xlink": XLINK_NS,
}

# Size definitions (width_mm, height_mm, is_circular)
SIZES = {
    "saville": (115, 95, False),
    "dick": (140, 90, False),
    "barzan": (194, 143, False),
    "dracula": (95, 95, True),
    "baby_jesus": (290, 190, False),
}

COLORS = ["silver", "gold", "white"]
LAYOUT_MODES = ["A", "B", "C", "D", "E", "F"]

# Template sign positions (extracted from SVG structure)
TEMPLATE_SIGN_BOUNDS = {
    "saville": (30, 24, 93, 73),
    "dick": (25, 30, 110, 60),
    "barzan": (25, 25, 164, 113),
    "dracula": (37, 27, 85, 85),
    "baby_jesus": (25, 25, 240, 140),
}

# Peel and stick template has different sign positions for baby_jesus only
# Other sizes work correctly with the main template bounds
PEEL_AND_STICK_SIGN_BOUNDS = {
    "baby_jesus": (8, 120, 130, 85),
}

FONTS = {
    "arial_bold": ("Arial", "bold"),
    "arial_heavy": ("Arial Black", "normal"),
}

# Base directory for assets
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = BASE_DIR / "icons"


@dataclass
class SignBounds:
    """Defines the drawable area on the sign."""
    x: float
    y: float
    width: float
    height: float
    is_circular: bool = False
    padding: float = 5.0

    @property
    def inner_x(self) -> float:
        return self.x + self.padding

    @property
    def inner_y(self) -> float:
        return self.y + self.padding

    @property
    def inner_width(self) -> float:
        return self.width - 2 * self.padding

    @property
    def inner_height(self) -> float:
        return self.height - 2 * self.padding

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass
class LayoutResult:
    """Result of layout calculation."""
    icon_x: float
    icon_y: float
    icon_width: float
    icon_height: float
    text_elements: list[dict]


# Layout bounds from CSV - reload on every app start
LAYOUT_BOUNDS = {}

# Force reload on module import
def _load_layout_bounds():
    """Load layout bounding boxes from CSV file."""
    global LAYOUT_BOUNDS
    csv_path = ASSETS_DIR / "layout_modes.csv"
    if not csv_path.exists():
        return
    
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row.get("template", "main"),
                row.get("size", ""),
                row.get("orientation", "landscape"),
                row.get("layout_mode", ""),
                row.get("element", ""),
            )
            LAYOUT_BOUNDS[key] = {
                "x": float(row.get("x", 0)),
                "y": float(row.get("y", 0)),
                "width": float(row.get("width", 0)),
                "height": float(row.get("height", 0)),
            }


def _get_sign_bounds(size: str, orientation: str = "landscape", template_type: str = "main") -> SignBounds:
    """Get the drawable bounds for a sign size."""
    width_mm, height_mm, is_circular = SIZES[size]

    # Use peel_and_stick specific bounds if available
    if template_type == "peel_and_stick" and size in PEEL_AND_STICK_SIGN_BOUNDS:
        sign_x, sign_y, sign_w, sign_h = PEEL_AND_STICK_SIGN_BOUNDS[size]
    elif size in TEMPLATE_SIGN_BOUNDS:
        sign_x, sign_y, sign_w, sign_h = TEMPLATE_SIGN_BOUNDS[size]
    else:
        margin = 20
        sign_x = margin
        sign_y = margin
        sign_w = width_mm - 2 * margin
        sign_h = height_mm - 2 * margin

    if size == "baby_jesus" and orientation == "portrait":
        sign_w, sign_h = sign_h, sign_w

    return SignBounds(
        x=sign_x,
        y=sign_y,
        width=sign_w,
        height=sign_h,
        is_circular=is_circular,
        padding=4.0 if is_circular else 3.0,
    )


def _calculate_layout(
    bounds: SignBounds,
    layout_mode: str,
    num_icons: int,
    text_lines: list[str],
    icon_scale: float = 1.0,
    text_scale: float = 1.0,
    size: str = "",
    orientation: str = "landscape",
    template_type: str = "main",
) -> LayoutResult:
    """Calculate positions and sizes for icons and text based on layout mode."""
    # Always reload CSV to pick up changes
    _load_layout_bounds()
    
    active_lines = [t for t in text_lines if t]
    
    # Check CSV-defined bounds - try template-specific first, then fall back to main
    icon_key = (template_type, size, orientation, layout_mode, "icon")
    if icon_key not in LAYOUT_BOUNDS:
        icon_key = ("main", size, orientation, layout_mode, "icon")
    
    if icon_key in LAYOUT_BOUNDS:
        icon_bounds = LAYOUT_BOUNDS[icon_key]
        base_width = icon_bounds["width"]
        base_height = icon_bounds["height"]
        base_x = icon_bounds["x"]
        base_y = icon_bounds["y"]
        
        icon_width = base_width * icon_scale
        icon_height = base_height * icon_scale
        icon_x = base_x + (base_width - icon_width) / 2
        icon_y = base_y + (base_height - icon_height) / 2
        
        text_elements = []
        for idx, line in enumerate(active_lines):
            text_key = (template_type, size, orientation, layout_mode, f"text_{idx + 1}")
            if text_key not in LAYOUT_BOUNDS:
                text_key = ("main", size, orientation, layout_mode, f"text_{idx + 1}")
            if text_key in LAYOUT_BOUNDS:
                tb = LAYOUT_BOUNDS[text_key]
                num_chars = len(line) if line else 1
                font_size = tb["width"] / (num_chars * 3.2)
                max_by_height = tb["height"] / 3.0
                font_size = min(font_size, max_by_height) * text_scale
                text_elements.append({
                    "text": line,
                    "x": tb["x"] + tb["width"] / 2,
                    "y": tb["y"] + tb["height"] * 0.75,
                    "font_size": font_size,
                    "anchor": "middle",
                })
        
        return LayoutResult(
            icon_x=icon_x,
            icon_y=icon_y,
            icon_width=icon_width,
            icon_height=icon_height,
            text_elements=text_elements,
        )
    
    # Fallback to calculated positions
    inner_w = bounds.inner_width
    inner_h = bounds.inner_height
    inner_x = bounds.inner_x
    inner_y = bounds.inner_y
    
    max_font_size = 5.0 * text_scale
    text_elements = []

    if layout_mode == "A":
        icon_width = inner_w * 0.7 * icon_scale
        icon_height = inner_h * 0.7 * icon_scale
        icon_x = bounds.center_x - icon_width / 2
        icon_y = bounds.center_y - icon_height / 2
    elif layout_mode in ("B", "C"):
        # For layout B/C, the icon contains both graphic and text
        # Use most of the inner area and center it
        icon_height = inner_h * 0.90 * icon_scale
        icon_width = icon_height
        icon_x = bounds.center_x - icon_width / 2
        # Center the icon vertically - add offset because SVG content is top-heavy
        # The SVG viewBox is 0-100 but content is weighted toward top (y=8-95)
        icon_y = bounds.center_y - icon_height / 2 + (icon_height * 0.08)
        
        # Text elements are part of the SVG icon, so no separate text needed
        # But keep this for cases where text_lines are provided separately
        if active_lines:
            icon_bottom = icon_y + icon_height
            text_y = icon_bottom + inner_h * 0.05
            for line in active_lines:
                text_elements.append({
                    "text": line,
                    "x": bounds.center_x,
                    "y": text_y,
                    "font_size": max_font_size,
                    "anchor": "middle",
                })
                text_y += max_font_size + 2
    else:
        # Default fallback
        icon_width = inner_w * 0.6 * icon_scale
        icon_height = inner_h * 0.6 * icon_scale
        icon_x = bounds.center_x - icon_width / 2
        icon_y = bounds.center_y - icon_height / 2

    return LayoutResult(
        icon_x=icon_x,
        icon_y=icon_y,
        icon_width=icon_width,
        icon_height=icon_height,
        text_elements=text_elements,
    )


def _load_icon(icon_filename: str) -> tuple[str, any]:
    """Load an icon file (SVG or PNG)."""
    icon_path = ICONS_DIR / icon_filename
    if not icon_path.exists():
        # Try with different extensions
        for ext in [".svg", ".png", ".SVG", ".PNG"]:
            alt_path = ICONS_DIR / (icon_path.stem + ext)
            if alt_path.exists():
                icon_path = alt_path
                break
    
    if not icon_path.exists():
        logging.warning(f"Icon not found: {icon_filename}")
        return None, None
    
    suffix = icon_path.suffix.lower()
    
    if suffix == ".svg":
        tree = etree.parse(str(icon_path))
        return "svg", tree.getroot()
    elif suffix == ".png":
        with open(icon_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("ascii")
        img = Image.open(icon_path)
        return "png", (b64, img.width, img.height, "image/png")
    
    return None, None


def _inject_icon(root: etree._Element, icon_root: etree._Element, x: float, y: float, width: float, height: float):
    """Inject an SVG icon into the template."""
    icon_w = float(icon_root.get("width", "100").replace("mm", "").replace("px", ""))
    icon_h = float(icon_root.get("height", "100").replace("mm", "").replace("px", ""))
    
    scale_x = width / icon_w if icon_w else 1
    scale_y = height / icon_h if icon_h else 1
    scale = min(scale_x, scale_y)
    
    scaled_w = icon_w * scale
    scaled_h = icon_h * scale
    offset_x = x + (width - scaled_w) / 2
    offset_y = y + (height - scaled_h) / 2
    
    icon_group = etree.SubElement(root, f"{{{SVG_NS}}}g")
    icon_group.set("id", "injected_icon")
    icon_group.set("transform", f"translate({offset_x},{offset_y}) scale({scale})")
    
    for child in icon_root:
        # Skip non-element nodes (comments, processing instructions)
        if not isinstance(child.tag, str):
            continue
        tag_local = etree.QName(child).localname
        if tag_local not in ("defs", "namedview", "metadata"):
            # Deep copy the child to avoid modifying the original
            import copy
            icon_group.append(copy.deepcopy(child))


def _inject_png_icon(root: etree._Element, png_data: tuple, x: float, y: float, width: float, height: float):
    """Inject a PNG icon as embedded image."""
    b64_data, orig_w, orig_h, mime = png_data
    
    scale_x = width / orig_w if orig_w else 1
    scale_y = height / orig_h if orig_h else 1
    scale = min(scale_x, scale_y)
    
    scaled_w = orig_w * scale
    scaled_h = orig_h * scale
    offset_x = x + (width - scaled_w) / 2
    offset_y = y + (height - scaled_h) / 2
    
    img_elem = etree.SubElement(root, f"{{{SVG_NS}}}image")
    img_elem.set("x", str(offset_x))
    img_elem.set("y", str(offset_y))
    img_elem.set("width", str(scaled_w))
    img_elem.set("height", str(scaled_h))
    img_elem.set(f"{{{XLINK_NS}}}href", f"data:{mime};base64,{b64_data}")


def _add_text_element(root: etree._Element, text: str, x: float, y: float, font_size: float, 
                      anchor: str = "middle", font_family: str = "Arial", font_weight: str = "bold"):
    """Add a text element to the SVG."""
    text_elem = etree.SubElement(root, f"{{{SVG_NS}}}text")
    text_elem.set("x", str(x))
    text_elem.set("y", str(y))
    text_elem.set("style", f"font-family:{font_family};font-weight:{font_weight};font-size:{font_size}mm;text-anchor:{anchor};fill:#000000;")
    text_elem.text = text


def generate_product_image(product: dict, template_type: str = "main") -> bytes:
    """
    Generate a product image from template.
    
    Args:
        product: Product dict from database
        template_type: 'main', 'dimensions', 'peel_and_stick', 'rear'
    
    Returns:
        PNG image as bytes
    """
    size = product.get("size", "saville").lower()
    color = product.get("color", "silver").lower()
    orientation = product.get("orientation", "landscape").lower()
    layout_mode = product.get("layout_mode", "A").upper()
    icon_files = (product.get("icon_files") or "").split(",")
    icon_files = [f.strip() for f in icon_files if f.strip()]
    
    text_lines = [
        product.get("text_line_1", ""),
        product.get("text_line_2", ""),
        product.get("text_line_3", ""),
    ]
    
    icon_scale = float(product.get("icon_scale", 1.0) or 1.0)
    text_scale = float(product.get("text_scale", 1.0) or 1.0)
    icon_offset_x = float(product.get("icon_offset_x", 0.0) or 0.0)
    icon_offset_y = float(product.get("icon_offset_y", 0.0) or 0.0)
    font = product.get("font", "arial_heavy")
    
    # Build template filename
    if size == "baby_jesus" and orientation == "portrait":
        template_name = f"{color}_{size}_portrait_{template_type}.svg"
    else:
        template_name = f"{color}_{size}_{template_type}.svg"
    
    template_path = ASSETS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    # Parse template
    tree = etree.parse(str(template_path))
    root = tree.getroot()
    
    # For 'rear' template type, do NOT inject icons or text - just render the template as-is
    # The rear image shows the 3M adhesive backing without any product graphics
    if template_type == "rear":
        svg_content = etree.tostring(root, encoding="unicode")
        # Use scale=2 for balance between quality and performance (was scale=4)
        png_bytes = render_svg_to_bytes(svg_content, scale=2)
        return png_bytes
    
    # For 'peel_and_stick' template, render with transparency to show full template graphics
    # (EASY text, arrow, PEEL & STICK text) - these are part of the SVG template
    render_transparent = (template_type == "peel_and_stick")
    
    # Get bounds and calculate layout (pass template_type for proper bounds lookup)
    bounds = _get_sign_bounds(size, orientation, template_type)
    layout = _calculate_layout(
        bounds, layout_mode, len(icon_files), text_lines,
        icon_scale, text_scale, size, orientation, template_type
    )
    
    # Apply QA position offsets to icon position
    final_icon_x = layout.icon_x + icon_offset_x
    final_icon_y = layout.icon_y + icon_offset_y
    
    # Inject icons
    for icon_file in icon_files:
        icon_type, icon_data = _load_icon(icon_file)
        if icon_type == "svg":
            _inject_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
        elif icon_type == "png":
            _inject_png_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
    
    # Add text elements
    font_family, font_weight = FONTS.get(font, ("Arial", "bold"))
    for text_elem in layout.text_elements:
        _add_text_element(
            root, text_elem["text"], text_elem["x"], text_elem["y"],
            text_elem["font_size"], text_elem.get("anchor", "middle"),
            font_family, font_weight
        )
    
    # Convert to string and render
    svg_content = etree.tostring(root, encoding="unicode")
    # For peel_and_stick, use full_page to capture elements outside viewBox (EASY, arrow, PEEL & STICK text)
    use_full_page = (template_type == "peel_and_stick")
    # Use scale=2 for balance between quality and performance (was scale=4)
    png_bytes = render_svg_to_bytes(svg_content, scale=2, transparent=render_transparent, full_page=use_full_page)
    
    return png_bytes


def generate_product_image_preview(product: dict) -> bytes:
    """
    Generate a low-resolution preview image for thumbnails.
    Uses scale=1 instead of scale=4 for faster rendering.
    """
    size = product.get("size", "saville").lower()
    color = product.get("color", "silver").lower()
    orientation = product.get("orientation", "landscape").lower()
    layout_mode = product.get("layout_mode", "A").upper()
    icon_files = (product.get("icon_files") or "").split(",")
    icon_files = [f.strip() for f in icon_files if f.strip()]
    
    text_lines = [
        product.get("text_line_1", ""),
        product.get("text_line_2", ""),
        product.get("text_line_3", ""),
    ]
    
    icon_scale = float(product.get("icon_scale", 1.0) or 1.0)
    text_scale = float(product.get("text_scale", 1.0) or 1.0)
    icon_offset_x = float(product.get("icon_offset_x", 0.0) or 0.0)
    icon_offset_y = float(product.get("icon_offset_y", 0.0) or 0.0)
    font = product.get("font", "arial_heavy")
    
    # Build template filename
    if size == "baby_jesus" and orientation == "portrait":
        template_name = f"{color}_{size}_portrait_main.svg"
    else:
        template_name = f"{color}_{size}_main.svg"
    
    template_path = ASSETS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    # Parse template
    tree = etree.parse(str(template_path))
    root = tree.getroot()
    
    # Get bounds and calculate layout
    bounds = _get_sign_bounds(size, orientation)
    layout = _calculate_layout(
        bounds, layout_mode, len(icon_files), text_lines,
        icon_scale, text_scale, size, orientation, "main"
    )
    
    # Apply QA position offsets to icon position
    final_icon_x = layout.icon_x + icon_offset_x
    final_icon_y = layout.icon_y + icon_offset_y
    
    # Inject icons
    for icon_file in icon_files:
        icon_type, icon_data = _load_icon(icon_file)
        if icon_type == "svg":
            _inject_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
        elif icon_type == "png":
            _inject_png_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
    
    # Add text elements
    font_family, font_weight = FONTS.get(font, ("Arial", "bold"))
    for text_elem in layout.text_elements:
        _add_text_element(
            root, text_elem["text"], text_elem["x"], text_elem["y"],
            text_elem["font_size"], text_elem.get("anchor", "middle"),
            font_family, font_weight
        )
    
    # Convert to string and render at LOW resolution (scale=1)
    svg_content = etree.tostring(root, encoding="unicode")
    png_bytes = render_svg_to_bytes(svg_content, scale=1, transparent=False, full_page=False)
    
    return png_bytes


def generate_transparent_product_image(product: dict) -> bytes:
    """
    Generate a transparent PNG of the main product image.
    Used for lifestyle image compositing.
    
    This uses the actual main template and renders it with transparency,
    so the product looks exactly like the main image but with transparent background.
    
    Args:
        product: Product dict from database
    
    Returns:
        PNG image with transparency as bytes
    """
    # Use the main template but render with transparency
    # This ensures the lifestyle image looks like the actual product
    size = product.get("size", "saville").lower()
    color = product.get("color", "silver").lower()
    orientation = product.get("orientation", "landscape").lower()
    layout_mode = product.get("layout_mode", "A").upper()
    icon_files = (product.get("icon_files") or "").split(",")
    icon_files = [f.strip() for f in icon_files if f.strip()]
    
    text_lines = [
        product.get("text_line_1", ""),
        product.get("text_line_2", ""),
        product.get("text_line_3", ""),
    ]
    
    icon_scale = float(product.get("icon_scale", 1.0) or 1.0)
    text_scale = float(product.get("text_scale", 1.0) or 1.0)
    icon_offset_x = float(product.get("icon_offset_x", 0.0) or 0.0)
    icon_offset_y = float(product.get("icon_offset_y", 0.0) or 0.0)
    font = product.get("font", "arial_heavy")
    
    # Load the main template (same as generate_product_image with template_type="main")
    # Build template filename using same logic as generate_product_image
    if size == "baby_jesus" and orientation == "portrait":
        template_name = f"{color}_{size}_portrait_main.svg"
    else:
        template_name = f"{color}_{size}_main.svg"
    
    template_path = ASSETS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    tree = etree.parse(str(template_path))
    root = tree.getroot()
    
    # Get bounds and calculate layout
    bounds = _get_sign_bounds(size, orientation)
    layout = _calculate_layout(
        bounds, layout_mode, len(icon_files), text_lines,
        icon_scale, text_scale, size, orientation, "main"
    )
    
    # Apply QA position offsets
    final_icon_x = layout.icon_x + icon_offset_x
    final_icon_y = layout.icon_y + icon_offset_y
    
    # Inject icons
    for icon_file in icon_files:
        icon_type, icon_data = _load_icon(icon_file)
        if icon_type == "svg":
            _inject_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
        elif icon_type == "png":
            _inject_png_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
    
    # Add text elements
    font_family, font_weight = FONTS.get(font, ("Arial", "bold"))
    for text_elem in layout.text_elements:
        _add_text_element(
            root, text_elem["text"], text_elem["x"], text_elem["y"],
            text_elem["font_size"], text_elem.get("anchor", "middle"),
            font_family, font_weight
        )
    
    # Render to PNG with transparency
    svg_content = etree.tostring(root, encoding="unicode")
    png_bytes = render_svg_to_bytes(svg_content, scale=4, transparent=True)
    
    return png_bytes


def generate_all_images_for_product(product: dict) -> dict[str, bytes]:
    """Generate all image types for a product."""
    images = {}
    template_types = ["main", "dimensions", "peel_and_stick", "rear"]
    
    for template_type in template_types:
        try:
            images[template_type] = generate_product_image(product, template_type)
        except FileNotFoundError as e:
            logging.warning(f"Template not found for {product['m_number']}: {e}")
        except Exception as e:
            logging.error(f"Error generating {template_type} for {product['m_number']}: {e}")
    
    return images


def generate_master_svg_for_product(product: dict) -> bytes:
    """
    Generate the master design SVG file for a product.
    This is the SVG with icons and text injected, used for manufacturing.
    
    Args:
        product: Product dict from database
    
    Returns:
        SVG content as bytes
    """
    size = product.get("size", "saville").lower()
    color = product.get("color", "silver").lower()
    orientation = product.get("orientation", "landscape").lower()
    layout_mode = product.get("layout_mode", "A").upper()
    icon_files = (product.get("icon_files") or "").split(",")
    icon_files = [f.strip() for f in icon_files if f.strip()]
    
    text_lines = [
        product.get("text_line_1", ""),
        product.get("text_line_2", ""),
        product.get("text_line_3", ""),
    ]
    
    icon_scale = float(product.get("icon_scale", 1.0) or 1.0)
    text_scale = float(product.get("text_scale", 1.0) or 1.0)
    icon_offset_x = float(product.get("icon_offset_x", 0.0) or 0.0)
    icon_offset_y = float(product.get("icon_offset_y", 0.0) or 0.0)
    font = product.get("font", "arial_heavy")
    
    # Use master_design_file template
    if size == "baby_jesus" and orientation == "portrait":
        template_name = f"{color}_{size}_portrait_master_design_file.svg"
    else:
        template_name = f"{color}_{size}_master_design_file.svg"
    
    template_path = ASSETS_DIR / template_name
    if not template_path.exists():
        # Fall back to main template if master doesn't exist
        if size == "baby_jesus" and orientation == "portrait":
            template_name = f"{color}_{size}_portrait_main.svg"
        else:
            template_name = f"{color}_{size}_main.svg"
        template_path = ASSETS_DIR / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    # Parse template
    tree = etree.parse(str(template_path))
    root = tree.getroot()
    
    # Get bounds and calculate layout
    bounds = _get_sign_bounds(size, orientation)
    layout = _calculate_layout(
        bounds, layout_mode, len(icon_files), text_lines,
        icon_scale, text_scale, size, orientation
    )
    
    # Apply QA position offsets to icon position
    final_icon_x = layout.icon_x + icon_offset_x
    final_icon_y = layout.icon_y + icon_offset_y
    
    # Inject icons
    for icon_file in icon_files:
        icon_type, icon_data = _load_icon(icon_file)
        if icon_type == "svg":
            _inject_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
        elif icon_type == "png":
            _inject_png_icon(root, icon_data, final_icon_x, final_icon_y, layout.icon_width, layout.icon_height)
    
    # Add text elements
    font_family, font_weight = FONTS.get(font, ("Arial", "bold"))
    for text_elem in layout.text_elements:
        _add_text_element(
            root, text_elem["text"], text_elem["x"], text_elem["y"],
            text_elem["font_size"], text_elem.get("anchor", "middle"),
            font_family, font_weight
        )
    
    # Return SVG as bytes
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)


def generate_images_job(job: Job, products: list[dict], upload_to_r2: bool = True) -> dict:
    """
    Background job to generate images for multiple products.
    
    Args:
        job: Job object for progress updates
        products: List of product dicts
        upload_to_r2: Whether to upload to R2 storage
    
    Returns:
        Dict with results per product
    """
    job.total = len(products)
    results = {}
    
    for i, product in enumerate(products):
        m_number = product["m_number"]
        job.message = f"Generating images for {m_number}..."
        job.progress = i
        
        try:
            images = generate_all_images_for_product(product)
            
            if upload_to_r2 and images:
                urls = {}
                for img_type, png_bytes in images.items():
                    key = f"{m_number}/{m_number}_{img_type}"
                    png_url, jpeg_url = upload_png_and_jpeg(png_bytes, key)
                    urls[img_type] = {"png": png_url, "jpeg": jpeg_url}
                results[m_number] = {"success": True, "urls": urls}
            else:
                results[m_number] = {"success": True, "images": len(images)}
                
        except Exception as e:
            logging.error(f"Failed to generate images for {m_number}: {e}")
            results[m_number] = {"success": False, "error": str(e)}
    
    job.progress = job.total
    job.message = f"Completed {len(products)} products"
    return results


if __name__ == "__main__":
    # Test image generation
    logging.basicConfig(level=logging.INFO)
    
    test_product = {
        "m_number": "TEST001",
        "size": "saville",
        "color": "silver",
        "layout_mode": "A",
        "icon_files": "no_entry.png",
        "text_line_1": "",
        "text_line_2": "",
        "text_line_3": "",
        "orientation": "landscape",
        "font": "arial_heavy",
        "icon_scale": 1.0,
        "text_scale": 1.0,
    }
    
    try:
        png_bytes = generate_product_image(test_product, "main")
        output_path = Path("test_generated.png")
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        print(f"Generated test image: {output_path} ({len(png_bytes)} bytes)")
    except Exception as e:
        print(f"Error: {e}")
