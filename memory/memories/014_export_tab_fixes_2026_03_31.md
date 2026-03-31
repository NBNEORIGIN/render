# Export tab fixes (2026-03-31)
Tags: bugfix export flatfile-preview r2 ebay csv download label
Date: 2026-03-31

## Issues fixed

### 1. Amazon Flatfile Preview — "NO FILE AVAILABLE"
`flatfile_preview()` in app.py was missing `from config import PUBLIC_BASE_URL`.
Same root cause as generate_amazon_flatfile() (see 012). Pattern: every function
using config values must have its own inline import.

Fix: added `from config import PUBLIC_BASE_URL` to flatfile_preview().

### 2. Step 2a label — "Upload to R2" renamed to "Save Images to Server"
R2 was removed; images are now stored on render.nbnesigns.co.uk local filesystem.
The button, heading, status messages, and exportLog() calls all said "R2".

Fix: updated all text in templates/index.html to say "Save Images to Server".

Note on performance: image saving takes ~4 minutes for a full batch. This is expected —
Playwright renders each product image sequentially. Not a bug, but could be parallelised
in future if it becomes a pain point.

### 3. eBay "Publish to eBay API" doesn't work
The publish route (`POST /api/ebay/publish`) requires eBay OAuth tokens and policies
to be configured via `ebay_setup_policies.py`. These have not been run on the server.
This is an infrastructure/setup issue, not a code bug.

### 4. eBay CSV download added
`POST /api/export/ebay` already existed and returns eBay File Exchange CSV as a
direct download. It just needed a UI button.

Added:
- `downloadEbayFile()` JS function — fetches /api/export/ebay, streams blob, triggers download
- "Download eBay CSV" button in Step 2b section (alongside "Publish to eBay API")
- "Download eBay CSV" button in quick-download bar at top of Export tab
- Filename: `ebay_listings_YYYY-MM-DD.csv`

## Commit
8aa84f6 fix(export): flatfile preview PUBLIC_BASE_URL, R2→server labels, eBay CSV download
