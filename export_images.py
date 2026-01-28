"""Image export utilities - download M Number folders as ZIP.

Generates proper folder structure for staff use:
- {M Number} {Description} {Color} {Size}/
  - 001 Design/
    - 001 MASTER FILE/
      - {M Number} MASTER FILE.svg
  - 002 Images/
    - {M Number} - 001.png (main)
    - {M Number} - 002.png (dimensions)
    - {M Number} - 003.png (peel_and_stick)
    - {M Number} - 004.png (rear)
"""
import io
import zipfile
import logging
from pathlib import Path

from image_generator import generate_all_images_for_product, generate_master_svg_for_product
from jobs import Job


# Image type to numbered filename mapping
IMAGE_TYPE_NUMBERS = {
    "main": "001",
    "dimensions": "002",
    "peel_and_stick": "003",
    "rear": "004",
    "lifestyle": "006",
}

# Size display names
SIZE_DISPLAY = {
    "dracula": "Dracula",
    "saville": "Saville",
    "dick": "Dick",
    "barzan": "Barzan",
    "baby_jesus": "Baby_Jesus",
}

# Color display names
COLOR_DISPLAY = {
    "silver": "Silver",
    "gold": "Gold",
    "white": "White",
}


def _get_folder_name(product: dict) -> str:
    """Generate the full folder name for a product."""
    m_number = product.get("m_number", "UNKNOWN")
    description = product.get("description", "Sign")
    color = product.get("color", "silver").lower()
    size = product.get("size", "dracula").lower()
    mounting = product.get("mounting_type", "self_adhesive")
    
    # Format mounting type
    mounting_display = "Self Adhesive" if mounting == "self_adhesive" else "Pre-Drilled"
    
    # Build folder name
    color_display = COLOR_DISPLAY.get(color, color.title())
    size_display = SIZE_DISPLAY.get(size, size.title())
    
    return f"{m_number} {mounting_display} {description} aluminium sign {color_display} {size_display}"


def _png_to_jpeg(png_bytes: bytes) -> bytes:
    """Convert PNG bytes to JPEG bytes."""
    from PIL import Image
    from io import BytesIO
    
    img = Image.open(BytesIO(png_bytes))
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    jpeg_buffer = BytesIO()
    img.save(jpeg_buffer, format="JPEG", quality=95)
    return jpeg_buffer.getvalue()


def generate_m_number_folder_zip(products: list[dict], include_master_svg: bool = True) -> bytes:
    """
    Generate a ZIP file with proper M Number folder structure for staff.
    
    Structure:
    - {M Number} {Description} {Color} {Size}/
      - 001 Design/
        - 001 MASTER FILE/
          - {M Number} MASTER FILE.svg
      - 002 Images/
        - {M Number} - 001.png
        - {M Number} - 002.png
        - etc.
    
    Args:
        products: List of product dicts
        include_master_svg: Whether to include master SVG file
    
    Returns:
        ZIP file as bytes
    """
    zip_buffer = io.BytesIO()
    total_products = len(products)
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, product in enumerate(products):
            m_number = product.get("m_number", "UNKNOWN")
            folder_name = _get_folder_name(product)
            logging.info(f"Processing {m_number} ({idx + 1}/{total_products})...")
            
            try:
                # NOTE: Image generation removed due to scale=2 performance issues
                # Images should be generated via R2 upload instead
                # This folder only includes master SVG and structure
                
                # Check for lifestyle image (generated separately)
                lifestyle_path = Path(__file__).parent / f"{m_number}_lifestyle.jpg"
                if lifestyle_path.exists():
                    with open(lifestyle_path, 'rb') as lf:
                        lifestyle_bytes = lf.read()
                    zf.writestr(f"{folder_name}/002 Images/{m_number} - 006.jpg", lifestyle_bytes)
                
                # Add master SVG to 001 Design/001 MASTER FILE
                if include_master_svg:
                    try:
                        master_svg = generate_master_svg_for_product(product)
                        svg_path = f"{folder_name}/001 Design/001 MASTER FILE/{m_number} MASTER FILE.svg"
                        zf.writestr(svg_path, master_svg)
                    except Exception as e:
                        logging.warning(f"Could not generate master SVG for {m_number}: {e}")
                
                # Add README explaining image generation
                readme_content = f"""M Number Folder: {m_number}

IMAGES:
Product images (001-004.jpg) are generated via the R2 Upload feature.
Use the "Upload Images to R2" button in the Export tab to generate and upload all images.

Images will be automatically saved to:
G:\\My Drive\\001 NBNE\\001 M\\{folder_name}\\002 Images\\

This folder structure is ready for staff use.
"""
                zf.writestr(f"{folder_name}/README.txt", readme_content)
                
                # Create empty placeholder folders (matching original structure)
                zf.writestr(f"{folder_name}/000 Archive/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/000 Archive/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/002 MUTOH/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/003 MIMAKI/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/004 ROLAND/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/005 IMAGE GENERATION/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/006 HULK/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/007 EPSON/.gitkeep", "")
                zf.writestr(f"{folder_name}/001 Design/008 ROLF/.gitkeep", "")
                zf.writestr(f"{folder_name}/003 Blanks/.gitkeep", "")
                zf.writestr(f"{folder_name}/004 SOPs/.gitkeep", "")
                
            except Exception as e:
                import traceback
                logging.error(f"Failed to generate folder for {m_number}: {e}")
                logging.error(traceback.format_exc())
                zf.writestr(f"{folder_name}/ERROR.txt", f"Failed to generate: {e}")
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def generate_images_zip(products: list[dict]) -> bytes:
    """
    Generate a ZIP file containing all product images organized by M Number.
    Simple flat structure for quick downloads.
    
    Args:
        products: List of product dicts
    
    Returns:
        ZIP file as bytes
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for product in products:
            m_number = product.get("m_number", "UNKNOWN")
            
            try:
                images = generate_all_images_for_product(product)
                
                for img_type, png_bytes in images.items():
                    zf.writestr(f"{m_number}/{m_number}_{img_type}.png", png_bytes)
                    zf.writestr(f"{m_number}/{m_number}_{img_type}.jpg", _png_to_jpeg(png_bytes))
                    
            except Exception as e:
                logging.error(f"Failed to generate images for {m_number}: {e}")
                zf.writestr(f"{m_number}/ERROR.txt", f"Failed to generate images: {e}")
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def generate_single_product_zip(product: dict, full_structure: bool = False) -> bytes:
    """
    Generate a ZIP file for a single product's images.
    
    Args:
        product: Product dict
        full_structure: If True, use full M Number folder structure for staff
    
    Returns:
        ZIP file as bytes
    """
    if full_structure:
        return generate_m_number_folder_zip([product])
    return generate_images_zip([product])


def generate_single_m_number_folder_zip(product: dict) -> bytes:
    """
    Generate a ZIP with full M Number folder structure for a single product.
    
    Args:
        product: Product dict
    
    Returns:
        ZIP file as bytes
    """
    return generate_m_number_folder_zip([product])


def generate_images_zip_job(job: Job, products: list[dict], full_structure: bool = False) -> bytes:
    """
    Background job to generate images ZIP.
    
    Args:
        job: Job object for progress updates
        products: List of product dicts
        full_structure: If True, use full M Number folder structure
    
    Returns:
        ZIP file as bytes
    """
    if full_structure:
        # Use full folder structure
        job.total = len(products)
        job.message = "Generating M Number folders..."
        result = generate_m_number_folder_zip(products)
        job.progress = job.total
        job.message = f"Generated {len(products)} M Number folders"
        return result
    
    # Simple flat structure
    job.total = len(products)
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, product in enumerate(products):
            m_number = product.get("m_number", "UNKNOWN")
            job.message = f"Generating images for {m_number}..."
            job.progress = i
            
            try:
                images = generate_all_images_for_product(product)
                
                for img_type, png_bytes in images.items():
                    zf.writestr(f"{m_number}/{m_number}_{img_type}.png", png_bytes)
                    zf.writestr(f"{m_number}/{m_number}_{img_type}.jpg", _png_to_jpeg(png_bytes))
                    
            except Exception as e:
                logging.error(f"Failed to generate images for {m_number}: {e}")
                zf.writestr(f"{m_number}/ERROR.txt", f"Failed to generate images: {e}")
    
    job.progress = job.total
    job.message = f"Generated ZIP for {len(products)} products"
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
