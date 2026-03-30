# Architecture overview
Tags: architecture flask gunicorn postgresql playwright pillow
Date: 2026-03-30

Render is a Flask 3.0 web app served by Gunicorn (single worker) behind nginx.
It generates sign product images and publishes them to Amazon, Etsy, and eBay.

## Stack

- **Flask 3.0** — web framework
- **Gunicorn** — WSGI server, locked to 1 worker because job state lives in-memory (multi-worker causes silent job loss)
- **PostgreSQL 16** — production database (SQLite for local dev)
- **Playwright + headless Chromium** — SVG template → PNG rendering
- **Pillow** — image processing, MAX_IMAGE_PIXELS set to 100_000_000 (needed for large sign blanks)
- **Anthropic Claude** — AI content generation (descriptions, titles, bullet points)
- **OpenAI DALL-E** — lifestyle background image generation

## Module layout

```
app.py               — Flask routes, auth, job dispatch
config.py            — env var loading, BLANK_SEEDS, DEFAULT_USERS
models.py            — DB schema (init_db, Product, Blank, User models)
jobs.py              — in-memory job queue, worker threads
image_generator.py   — Playwright rendering, Pillow compositing
content_generator.py — Anthropic API calls for product copy
local_storage.py     — saves images to IMAGES_DIR filesystem
svg_renderer.py      — SVG template manipulation
templates/index.html — full single-page frontend (extracted from app.py)
assets/              — SVG blank templates, icons
```

## Gunicorn single-worker constraint

The job system (jobs.py) uses Python threading and in-memory dicts for job state.
Running multiple Gunicorn workers would mean each worker has its own memory space
and jobs submitted to worker A would be invisible to worker B.
The fix is to move job state to the DB — tracked as a future improvement.
Until then, always run with `--workers 1`.
