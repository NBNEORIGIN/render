# SignMaker - Development Summary

**Last Updated:** January 9, 2026  
**Repository:** `https://github.com/NBNEORIGIN/signmaker.git`  
**Status:** Ready for production deployment

---

## Overview

SignMaker is a Flask-based web application for generating, managing, and publishing signage products to marketplaces (Amazon, Etsy, eBay). It provides an end-to-end workflow from product creation to flatfile generation and image hosting.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask (Python) |
| Database | SQLite (`signmaker.db`) |
| Frontend | Inline HTML/CSS/JS (embedded in `app.py`) |
| SVG Rendering | Playwright (headless Chromium) |
| Image Storage | Cloudflare R2 |
| AI Assistant | OpenAI API |

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application with embedded HTML/CSS/JS UI |
| `models.py` | SQLite database models (Product class) |
| `image_generator.py` | SVG template manipulation and product image generation |
| `svg_renderer.py` | Playwright-based SVG to PNG rendering |
| `r2_storage.py` | Cloudflare R2 upload/download functions |
| `export_etsy.py` | Etsy CSV flatfile generation |
| `export_images.py` | M Number folder ZIP generation |
| `config.py` | Configuration and environment variables |
| `requirements.txt` | Python dependencies |

---

## Features Implemented

### 1. Product Management
- **Editable data table** with Excel-style paste support (Ctrl+V)
- CRUD operations for products
- Product fields: M Number, description, color, size, orientation, layout mode, icon files, text lines, scales, offsets

### 2. AI Product Assistant
- **8 category-specific prompts** for product development guidance:
  1. Private Boundary & Exclusion
  2. Pet Control & Animal Signage
  3. Property Misuse & Nuisance
  4. Commercial Intrusion
  5. Privacy & Surveillance Awareness
  6. Waste, Bin & Fly-Tipping Control
  7. Smoking & Vaping Control
  8. Noise & Disturbance Control
- **Chat memory persistence** per category using localStorage
- OpenAI API integration

### 3. Image Generation
- **4 image types per product:**
  - `001` - Main product image
  - `002` - Dimensions overlay
  - `003` - Peel & Stick instruction
  - `004` - Rear/backing view
- **5 size variants:** Dracula (circular), Saville, Dick, Barzan, Baby Jesus
- **3 color variants:** Silver, Gold, White
- **2 mounting types:** Self Adhesive, Pre-Drilled
- SVG template-based generation with icon injection and text rendering
- Template-specific bounds for peel_and_stick (Baby Jesus has unique positioning)

### 4. Export & Publishing
- **Amazon Flatfile Generation** - XLSX format with correct image URLs
- **Etsy CSV Generation** - Marketplace-ready format
- **R2 Image Upload** - Automatic JPEG conversion, resizing (max 2000px), quality optimization
- **Google Drive Integration** - Automatic M Number folder creation with proper structure:
  ```
  {M Number} {Mounting} {Description} aluminium sign {Color} {Size}/
  ├── 000 Archive/
  ├── 001 Design/
  │   ├── 000 Archive/
  │   ├── 001 MASTER FILE/
  │   │   └── {M Number} MASTER FILE.svg
  │   ├── 002 MUTOH/
  │   ├── 003 MIMAKI/
  │   ├── 004 ROLAND/
  │   ├── 005 IMAGE GENERATION/
  │   ├── 006 HULK/
  │   ├── 007 EPSON/
  │   └── 008 ROLF/
  ├── 002 Images/
  │   ├── {M Number} - 001.jpg
  │   ├── {M Number} - 001.png
  │   └── ... (all image types)
  ├── 003 Blanks/
  └── 004 SOPs/
  ```

### 5. QA Review
- Side-by-side image preview for all 4 image types
- Adjustment controls for icon scale, text scale, and position offsets
- Real-time preview regeneration

---

## Environment Variables

```env
OPENAI_API_KEY=sk-...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=https://....r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-....r2.dev
```

---

## Image URL Format

All marketplace image URLs follow this format:
```
https://pub-f0f96448c91147489e7b6c6b22ed5010.r2.dev/{M_NUMBER}%20-%20{NNN}.jpg
```
- Spaces are URL-encoded as `%20`
- Extension is `.jpg` (converted from PNG during upload)
- Image numbers: 001, 002, 003, 004, 006 (no 005)

---

## Known Configurations

### Layout Bounds
- Defined in `assets/layout_modes.csv`
- Controls icon and text positioning per size/layout combination
- Layout modes: A, B, C, D, E, F

### Template Sign Bounds
- Defined in `image_generator.py`
- `TEMPLATE_SIGN_BOUNDS` - Main template positions
- `PEEL_AND_STICK_SIGN_BOUNDS` - Special bounds for Baby Jesus peel_and_stick only

### Google Drive Export Path
```
G:\My Drive\001 NBNE\001 M
```

---

## Recent Bug Fixes

1. **Amazon flatfile URLs** - Fixed to match Etsy format (URL-encoded spaces, .jpg extension)
2. **Image sizing** - Reduced to max 2000px for Amazon compliance
3. **Peel & Stick rendering** - Fixed Baby Jesus size with template-specific bounds
4. **SVG full-page capture** - Improved getBBox handling for templates with content outside viewBox
5. **M Number folder structure** - Added proper subdirectories and SVG master file generation

---

## Deployment Notes

### Local Development
```bash
cd "G:\My Drive\003 APPS\020 - SIGNMAKER"
python app.py
# Runs on http://127.0.0.1:5000
```

### Production Deployment
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn app:app`
- **Note:** Playwright requires headless Chromium - ensure deployment environment supports it
- **Database:** SQLite file needs persistent storage, or migrate to PostgreSQL

---

## Future Considerations

1. **Database Migration** - Move from SQLite to PostgreSQL for production scalability
2. **Google Drive API** - Replace local file system access with API for web deployment
3. **User Authentication** - Add login system for multi-user support
4. **Batch Operations** - Bulk product import/export
5. **Template Editor** - Visual SVG template editing interface

---

## Git Workflow

All changes are made in this workspace and pushed to GitHub:
```bash
git add -A
git commit -m "Description of changes"
git push
```

The repository is connected to a Render → Vercel pipeline for automatic deployment to the production website.
