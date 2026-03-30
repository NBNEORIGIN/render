# Refactor — app.py reduced from 4,598 to 1,796 lines
Tags: refactor html extraction templates monolithic app.py
Date: 2026-03-30

## What was done

The original `signmaker/app.py` was a 4,598-line monolith containing:
- All Flask routes
- All HTML (inline strings — the full SPA frontend)
- Hardcoded SIZES dicts duplicated from image_generator.py
- R2 storage upload logic
- Single-token auth logic

## Changes

1. **HTML extracted** to `templates/index.html` (2,794 lines)
   - Flask now uses `render_template('index.html')`
   - Allows the frontend to be edited independently

2. **SIZES dicts removed** from app.py, image_generator.py, content_generator.py
   - Replaced with `Blank.get(slug)` DB calls everywhere
   - Single source of truth: the blanks table

3. **R2 storage replaced** — all `upload_to_r2` / `R2_PUBLIC_URL` references
   replaced with `local_storage.save_png_and_jpeg` / `PUBLIC_BASE_URL`

4. **Auth replaced** — flask-httpauth Bearer token → Flask session email/password

5. **Path traversal fixed** — `download_m_folders` route now validates
   the target path against `tempfile.gettempdir()` to prevent directory traversal

## Result

app.py: 4,598 → 1,796 lines (61% reduction)
