"""Local filesystem image storage — replaces Cloudflare R2."""
from io import BytesIO
from pathlib import Path

from PIL import Image

from config import IMAGES_DIR


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_image(image_bytes: bytes, relative_key: str, content_type: str = "image/png") -> str:
    """
    Save image bytes to local storage.

    Args:
        image_bytes: Raw image data.
        relative_key: Path relative to IMAGES_DIR, e.g. "M1234/M1234-001.jpg"
        content_type: Unused — kept for API compatibility with r2_storage.

    Returns:
        URL path served by the app, e.g. "/images/M1234/M1234-001.jpg"
    """
    dest = IMAGES_DIR / relative_key
    _ensure_dir(dest.parent)
    dest.write_bytes(image_bytes)
    return f"/images/{relative_key}"


def save_png_and_jpeg(png_bytes: bytes, base_key: str) -> tuple[str, str]:
    """
    Save PNG and a JPEG-converted copy.

    Args:
        png_bytes: PNG image data.
        base_key: Key without extension, e.g. "M1234/M1234-001"

    Returns:
        (png_url, jpeg_url) — URL paths served by the app.
    """
    png_url = save_image(png_bytes, f"{base_key}.png", "image/png")

    img = Image.open(BytesIO(png_bytes))
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    jpeg_buffer = BytesIO()
    img.save(jpeg_buffer, format="JPEG", quality=95)
    jpeg_url = save_image(jpeg_buffer.getvalue(), f"{base_key}.jpg", "image/jpeg")

    return png_url, jpeg_url


def delete_image(relative_key: str) -> None:
    """Delete an image from local storage."""
    path = IMAGES_DIR / relative_key
    if path.exists():
        path.unlink()


def list_images(prefix: str = "") -> list[str]:
    """List image keys under an optional prefix."""
    search_dir = IMAGES_DIR / prefix if prefix else IMAGES_DIR
    if not search_dir.exists():
        return []
    return [
        str(p.relative_to(IMAGES_DIR)).replace("\\", "/")
        for p in search_dir.rglob("*")
        if p.is_file()
    ]
