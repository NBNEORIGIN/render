# Image storage — moved from Cloudflare R2 to own server
Tags: images storage nginx r2 cloudflare local filesystem
Date: 2026-03-30

## Decision

Removed Cloudflare R2 (S3-compatible object storage) entirely.
Images are now stored on the server's local filesystem and served directly by nginx.

## Why

- Removes external dependency and per-request R2 costs
- nginx serves static files faster than going through Flask
- Amazon, Etsy, and eBay crawlers get fast image loads via direct nginx alias
- Simpler architecture — no boto3, no R2 credentials to manage

## Implementation

`local_storage.py` replaces `r2_storage.py`:
- `save_image(image_bytes, relative_key, content_type) -> str` — saves to IMAGES_DIR, returns `/images/{key}`
- `save_png_and_jpeg(png_bytes, base_key) -> (png_path, jpg_path)`
- `delete_image(relative_key)`, `list_images(prefix)`

nginx config serves `/images/` with:
```nginx
location /images/ {
    alias /opt/nbne/render/images/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    add_header Access-Control-Allow-Origin "*";
}
```

The directory is bind-mounted: `/opt/nbne/render/images/` → container `/images`.

Public URLs use `PUBLIC_BASE_URL` env var (= `https://render.nbnesigns.co.uk`).
Marketplace image links are therefore `https://render.nbnesigns.co.uk/images/...`
