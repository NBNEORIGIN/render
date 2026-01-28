"""Cloudflare R2 storage utilities."""
import os
from io import BytesIO
from pathlib import Path

import boto3
from botocore.config import Config
from PIL import Image

from config import (
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_URL
)


def get_r2_client():
    """Get Cloudflare R2 S3 client."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",  # R2 requires 'auto' as region
        config=Config(signature_version="s3v4"),
    )


def upload_image(image_bytes: bytes, key: str, content_type: str = "image/png") -> str:
    """
    Upload image bytes to R2.
    
    Args:
        image_bytes: Image data as bytes
        key: Object key (filename) in R2
        content_type: MIME type
    
    Returns:
        Public URL of uploaded image
    """
    client = get_r2_client()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )
    return f"{R2_PUBLIC_URL}/{key}"


def upload_image_file(file_path: Path, key: str = None) -> str:
    """
    Upload image file to R2.
    
    Args:
        file_path: Path to image file
        key: Object key (defaults to filename)
    
    Returns:
        Public URL of uploaded image
    """
    if key is None:
        key = file_path.name
    
    content_type = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    
    with open(file_path, "rb") as f:
        return upload_image(f.read(), key, content_type)


def upload_png_and_jpeg(png_bytes: bytes, base_key: str) -> tuple[str, str]:
    """
    Upload PNG and also create/upload JPEG version.
    
    Args:
        png_bytes: PNG image data
        base_key: Base filename without extension
    
    Returns:
        Tuple of (png_url, jpeg_url)
    """
    # Upload PNG
    png_key = f"{base_key}.png"
    png_url = upload_image(png_bytes, png_key, "image/png")
    
    # Convert to JPEG and upload
    img = Image.open(BytesIO(png_bytes))
    if img.mode == "RGBA":
        # Create white background for transparency
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    jpeg_buffer = BytesIO()
    img.save(jpeg_buffer, format="JPEG", quality=95)
    jpeg_bytes = jpeg_buffer.getvalue()
    
    jpeg_key = f"{base_key}.jpg"
    jpeg_url = upload_image(jpeg_bytes, jpeg_key, "image/jpeg")
    
    return png_url, jpeg_url


def delete_image(key: str):
    """Delete image from R2."""
    client = get_r2_client()
    client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)


def list_images(prefix: str = "") -> list[str]:
    """List images in R2 with optional prefix."""
    client = get_r2_client()
    response = client.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]
