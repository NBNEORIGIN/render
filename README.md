# SignMaker - Automated Signage Product Management & Marketplace Export System

A comprehensive Flask-based web application for managing aluminum signage products, generating product images from SVG templates, creating AI-powered content, and exporting to multiple marketplaces (Amazon, eBay, Etsy).

---

## 🎯 Project Overview

**Purpose**: Streamline the entire workflow for creating, managing, and selling custom aluminum safety signs across multiple e-commerce platforms.

**Business Context**: 
- Products are aluminum signs with various sizes, colors, mounting types, and custom text/icons
- Each product has an M number (e.g., M2280) as the primary identifier
- Products are sold on Amazon, eBay, and Etsy with AI-generated content
- Images are stored on Cloudflare R2 and organized in Google Drive M number folders

---

## 🏗️ Architecture

### Tech Stack
- **Backend**: Flask 3.0+ with Gunicorn
- **Database**: SQLite (local development) / PostgreSQL (production on Render)
- **Image Generation**: Playwright (headless Chromium) for SVG → PNG rendering
- **Cloud Storage**: Cloudflare R2 for marketplace images
- **AI Services**: 
  - Anthropic Claude Sonnet 4 for Amazon listing content
  - OpenAI GPT-4 Vision for product analysis
  - OpenAI DALL-E 3 for lifestyle background images
- **Frontend**: Vanilla JavaScript with Bootstrap styling (single-page app embedded in Flask template)
- **Deployment**: Docker on Render.com

### Key Design Patterns
- **Single-file application**: `app.py` contains Flask routes, HTML template, and JavaScript (4600+ lines)
- **Database abstraction**: `models.py` with dynamic SQL placeholder selection (SQLite `?` vs PostgreSQL `%s`)
- **Background jobs**: `jobs.py` for long-running tasks (image generation, content creation)
- **Modular exports**: Separate modules for Amazon, eBay, Etsy exports

---

## 📁 Project Structure

```
020 - SIGNMAKER/
├── app.py                      # Main Flask app (routes + HTML + JS)
├── models.py                   # Database models (Product, connection pooling)
├── config.py                   # Environment configuration
├── image_generator.py          # SVG template processing & image generation
├── svg_renderer.py             # Playwright SVG to PNG renderer
├── r2_storage.py               # Cloudflare R2 upload utilities
├── content_generator.py        # AI content generation (Claude, OpenAI)
├── export_images.py            # M number folder ZIP generation
├── export_etsy.py              # Etsy CSV/XLSX export
├── export_ebay.py              # eBay CSV export
├── ebay_api.py                 # eBay Trading API integration
├── ebay_auth.py                # eBay OAuth authentication
├── import_flatfile.py          # Amazon flatfile import
├── generate_lifestyle_images.py # DALL-E lifestyle image generation
├── jobs.py                     # Background job management
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker container config
├── render.yaml                 # Render.com deployment config
├── .env                        # Environment variables (not in git)
├── assets/                     # SVG templates
│   ├── silver_saville_main.svg
│   ├── silver_saville_dimensions.svg
│   ├── silver_saville_peel_and_stick.svg
│   ├── silver_saville_rear.svg
│   ├── silver_saville_master_design_file.svg
│   └── ... (templates for all size/color combinations)
└── icons/                      # Icon SVG/PNG files
    ├── No Entry Without Permission.svg
    ├── icon_template_100mm_2.svg
    └── ... (user-uploaded icons)
```

---

## 🔑 Core Concepts

### Product Data Model
Each product has the following attributes:
- **m_number**: Primary identifier (e.g., "M2280")
- **description**: Product description (e.g., "No Entry Without Permission")
- **size**: Sign size (dracula, saville, dick, barzan, baby_jesus)
- **color**: Aluminum finish (silver, gold, white)
- **orientation**: Layout orientation (landscape, portrait)
- **layout_mode**: Text/icon layout (A-F)
- **icon_files**: Comma-separated icon filenames
- **text_line_1/2/3**: Custom text lines
- **font**: Font family (arial_heavy, arial_narrow, etc.)
- **material**: Material type (1mm_aluminium, 3mm_dibond, etc.)
- **mounting_type**: Mounting method (self_adhesive, pre_drilled)
- **ean**: European Article Number (barcode)
- **qa_status**: Quality assurance status (pending, approved, rejected)
- **icon_scale**: Icon size multiplier (0.5 - 2.0)
- **text_scale**: Text size multiplier (0.5 - 2.0)
- **icon_offset_x/y**: Fine-tune icon position

### Image Types
Each product generates 4 main image types:
1. **main** (001): Full product with icon and text
2. **dimensions** (002): Product with dimension annotations
3. **peel_and_stick** (003): Transparent background version
4. **rear** (004): Back side of sign
5. **lifestyle** (006): Product composited on AI-generated background

### SVG Template System
- Templates are stored in `assets/` directory
- Naming convention: `{color}_{size}_{type}.svg`
- Example: `silver_saville_main.svg`
- Templates contain placeholder areas for icons and text
- Layout bounds are defined in `image_generator.py` (TEMPLATE_SIGN_BOUNDS)

### Layout Modes
- **Mode A**: Icon only (no text)
- **Mode B**: Icon + 1 text line
- **Mode C**: Icon + 2 text lines
- **Mode D**: Icon + 3 text lines
- **Mode E**: Text only (no icon)
- **Mode F**: Custom layout

---

## 🚀 Key Features & Workflows

### 1. Product Management Tab
- **Import CSV**: Bulk import products from CSV file
- **Import SVG Icons**: Upload icon files to `icons/` directory
- **Product List**: View all products with thumbnails
- **Edit Product**: Modify product details inline
- **QA Review**: Approve/reject products with visual preview
- **Icon Management**: Upload, delete, apply icons to products
- **Scale & Position**: Fine-tune icon/text placement with live preview

### 2. Generate Tab
- **Step 1: Generate Images**: Create all 4 image types for approved products
- **Step 2: Generate AI Content**: Use Claude to create Amazon titles, descriptions, bullet points
- **Step 3: Generate Amazon Flatfile**: Create Excel file for Amazon Seller Central upload
- **AI Product Assistant**: Chat interface for product-specific questions

### 3. Export Tab
- **Step 1: Generate Lifestyle Images**: 
  - Create AI background with DALL-E 3
  - Composite product images onto background
  - Upload to R2 as image 006
- **Step 2a: Upload Images to R2**: 
  - Generate all product images
  - Convert to JPEG
  - Upload to Cloudflare R2 for marketplace URLs
- **Step 2b: Create M Number Folders**: 
  - Generate ZIP with proper folder structure
  - Includes master SVG files and all images
  - Manual upload to Google Drive
- **Step 3: Export to Marketplaces**:
  - Amazon: Download flatfile Excel
  - eBay: Publish via Trading API with promoted listings
  - Etsy: Download CSV/XLSX for bulk upload

### 4. QA Tab
- Visual review interface
- Side-by-side comparison of all image types
- Approve/reject with notes
- Bulk approval for variants (silver/gold/white)

---

## 🔧 Technical Implementation Details

### Database Connection Management
- Uses `psycopg2.pool.SimpleConnectionPool` for PostgreSQL
- Falls back to SQLite for local development
- Dynamic SQL placeholder selection: `get_placeholder()` returns `%s` or `?`
- Connection pooling prevents resource exhaustion

### Image Generation Pipeline
1. **Load SVG Template**: Parse with `lxml.etree`
2. **Calculate Layout**: Determine icon/text positions based on layout mode
3. **Inject Icons**: Embed SVG or PNG icons into template
4. **Add Text**: Create text elements with proper font/size
5. **Render to PNG**: Use Playwright to render SVG in headless Chromium
6. **Convert to JPEG**: Add white background, resize for marketplaces
7. **Upload to R2**: Store with key format `{m_number} - {image_num}.jpg`

### AI Content Generation
- **Amazon Listings**: Claude Sonnet 4 with structured prompts
- **Product Analysis**: GPT-4 Vision analyzes product images
- **Lifestyle Backgrounds**: DALL-E 3 creates themed backgrounds
- Content is cached in database to avoid regeneration

### R2 Storage Integration
- Bucket: Configured via `R2_BUCKET_NAME` environment variable
- Public URL: `R2_PUBLIC_URL` for marketplace image links
- Upload function: `r2_storage.upload_image(bytes, key, content_type)`
- Images are publicly accessible via `{R2_PUBLIC_URL}/{key}`

### eBay API Integration
- Uses Trading API (XML-based)
- OAuth 2.0 authentication flow
- Automatic promoted listings (ads) for new products
- Handles rate limiting and error responses

---

## 🌐 API Endpoints

### Product Management
- `GET /api/products` - List all products
- `GET /api/products/<m_number>` - Get single product
- `POST /api/products` - Create new product
- `PATCH /api/products/<m_number>` - Update product
- `DELETE /api/products/<m_number>` - Delete product
- `POST /api/products/<m_number>/approve` - Approve product
- `POST /api/products/<m_number>/reject` - Reject product

### Image Generation
- `GET /api/preview/<m_number>` - Get product preview thumbnail
- `POST /api/generate/images` - Generate all images for products
- `GET /api/export/images/<m_number>` - Download product images
- `POST /api/upload-images-to-r2` - Upload images to R2

### Content Generation
- `POST /api/generate/content` - Generate AI content for products
- `POST /api/chat` - AI assistant chat endpoint

### Export
- `POST /api/generate/amazon-flatfile` - Generate Amazon flatfile
- `GET /api/generate/amazon-flatfile-download` - Download flatfile
- `POST /api/export/etsy` - Generate Etsy CSV
- `POST /api/ebay/publish` - Publish to eBay via API
- `POST /api/export/lifestyle-background` - Generate DALL-E background
- `POST /api/export/lifestyle-images` - Generate lifestyle images
- `POST /api/export/m-folders` - Generate M number folders ZIP

### Icons
- `GET /api/icons` - List available icons
- `POST /api/icons/upload` - Upload new icon
- `DELETE /api/icons/<filename>` - Delete icon
- `POST /api/icons/apply-to-all` - Apply icon to all products

---

## 🔐 Environment Variables

Required for production:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# AI Services
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=signmaker-images
R2_ENDPOINT_URL=https://....r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-....r2.dev

# eBay API (optional)
EBAY_APP_ID=...
EBAY_CERT_ID=...
EBAY_DEV_ID=...
EBAY_USER_TOKEN=...
```

---

## 🚢 Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
python models.py

# Run development server
python app.py
# Access at http://localhost:5000
```

### Production (Render.com)
1. Push to GitHub repository
2. Create new Web Service on Render
3. Connect to GitHub repo
4. Render auto-detects `render.yaml`
5. Add environment variables in Render dashboard
6. Deploy (uses Dockerfile)

**Dockerfile highlights**:
- Base: `python:3.11-slim`
- Installs Playwright with Chromium dependencies
- Uses Gunicorn with 2 workers, 120s timeout
- Binds to dynamic `PORT` environment variable

---

## 📊 Database Schema

### products table
```sql
CREATE TABLE products (
    m_number TEXT PRIMARY KEY,
    description TEXT,
    size TEXT,
    color TEXT,
    orientation TEXT DEFAULT 'landscape',
    layout_mode TEXT DEFAULT 'A',
    icon_files TEXT,
    text_line_1 TEXT,
    text_line_2 TEXT,
    text_line_3 TEXT,
    font TEXT DEFAULT 'arial_heavy',
    material TEXT DEFAULT '1mm_aluminium',
    mounting_type TEXT DEFAULT 'self_adhesive',
    ean TEXT,
    qa_status TEXT DEFAULT 'pending',
    icon_scale REAL DEFAULT 1.0,
    text_scale REAL DEFAULT 1.0,
    icon_offset_x REAL DEFAULT 0.0,
    icon_offset_y REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🐛 Common Issues & Solutions

### Issue: Preview images are blank
- **Cause**: Icon file not found or incorrect filename in database
- **Solution**: Check icon exists in `icons/` directory, verify `icon_files` field

### Issue: "Unexpected token '<'" error
- **Cause**: JavaScript function calling undefined endpoint or HTML error page returned
- **Solution**: Check browser console, verify endpoint exists in Flask routes

### Issue: SQLite vs PostgreSQL errors
- **Cause**: SQL placeholder mismatch (`?` vs `%s`)
- **Solution**: Use `get_placeholder()` function in all SQL queries

### Issue: Playwright rendering fails
- **Cause**: Missing Chromium dependencies in Docker
- **Solution**: Ensure `playwright install --with-deps chromium` in Dockerfile

### Issue: R2 upload fails
- **Cause**: Missing or incorrect R2 credentials
- **Solution**: Verify all R2_* environment variables are set correctly

---

## 🔄 Recent Changes & Evolution

### Latest Updates (Feb 2026)
1. **Split Export Step 2**: Separated R2 upload from M folder download
2. **Fixed Master SVG**: Changed file write mode from text to binary
3. **Removed Auto-Save**: No longer automatically saves to Google Drive
4. **Added Missing Function**: Created `uploadImagesToR2()` JavaScript function

### Historical Context
- Originally used Inkscape for SVG rendering (replaced with Playwright)
- Migrated from CSV-based storage to database
- Added PostgreSQL support for Render deployment
- Implemented connection pooling to prevent database exhaustion
- Added extensive logging for debugging icon loading issues

---

## 📝 Code Style & Conventions

- **Python**: PEP 8 compliant, type hints where beneficial
- **JavaScript**: ES6+ features, async/await for API calls
- **SQL**: Parameterized queries, no string concatenation
- **Logging**: Use `logging` module, not `print()`
- **Error Handling**: Try/except with specific error messages
- **Comments**: Explain "why", not "what"

---

## 🎓 Learning Resources

To understand this codebase:
1. **Flask Basics**: Official Flask documentation
2. **Playwright**: Playwright Python API docs
3. **SVG Manipulation**: lxml.etree documentation
4. **Cloudflare R2**: S3-compatible API documentation
5. **Amazon Flatfiles**: Amazon Seller Central template guides
6. **eBay Trading API**: eBay Developer documentation

---

## 🤝 Contributing Guidelines

When modifying this project:
1. Test locally with SQLite before deploying to Render
2. Use `get_placeholder()` for all SQL queries
3. Add logging for debugging (especially image generation)
4. Update this README if adding major features
5. Commit frequently with descriptive messages
6. Test all 4 image types after template changes

---

## 📞 Support & Maintenance

**Repository**: https://github.com/NBNEORIGIN/signmaker  
**Deployment**: https://signmaker-app.onrender.com  
**Local Development**: http://localhost:5000

For issues or questions, review:
1. Browser console for JavaScript errors
2. Flask logs for backend errors
3. Render logs for deployment issues
4. This README for architecture understanding

---

## 🎯 Future Enhancements

Potential improvements:
- [ ] Migrate to React/Vue for better frontend structure
- [ ] Add user authentication and multi-tenancy
- [ ] Implement real-time progress updates with WebSockets
- [ ] Add automated testing (pytest, Playwright tests)
- [ ] Create admin dashboard for analytics
- [ ] Add batch operations for bulk updates
- [ ] Implement caching layer (Redis) for previews
- [ ] Add version control for product changes

---

**Last Updated**: February 2, 2026  
**Version**: 2.0  
**Maintainer**: NBNE Team
