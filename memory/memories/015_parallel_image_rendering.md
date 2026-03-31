# Parallel image rendering — 4x speedup (2026-03-31)
Tags: performance images playwright parallel threading svg-renderer
Date: 2026-03-31

## Problem
`Save Images to Server` (Step 2a) took ~4 minutes for 15 products.

## Root cause
Two layers of serialization:
1. `svg_renderer.py` used `ThreadPoolExecutor(max_workers=1)` — one Playwright thread
2. `save_product_images()` in app.py looped sequentially — 15 products × 4 types = 60 serial renders

## Fix

### svg_renderer.py
- Changed from `max_workers=1` to `max_workers=4`
- Replaced global `_browser` with `threading.local()` per-thread browser instances
- Each worker thread lazily initialises its own `sync_playwright()` + `chromium.launch()`
- `close_browser()` now submits shutdown to all 4 workers and waits

### app.py — save_product_images()
- Builds a list of all (product, img_type, img_num) tasks upfront
- Submits all renders concurrently via `ThreadPoolExecutor(max_workers=4)`
- Uses `as_completed()` to collect results and accumulate errors

## Expected result
~1 minute instead of ~4 minutes for a full batch (4x parallelism).

## Commit
01ffe88 perf(images): parallel renders — 4 concurrent Playwright workers (~4x speedup)
