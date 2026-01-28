# SignMaker

Hosted web application for generating signage products and Amazon flatfiles.

## Features

- **Product Management**: Add, edit, delete products with M numbers, sizes, colors, EANs
- **QA Review**: Approve/reject products with visual preview
- **Image Generation**: Render SVG templates to PNG using Playwright (no Inkscape needed)
- **AI Content**: Generate titles, descriptions, bullet points using Claude API
- **Lifestyle Images**: Generate AI lifestyle backgrounds using OpenAI
- **Amazon Flatfile**: Export ready-to-upload Amazon flatfiles with proper format

## Local Development

1. Copy `.env.example` to `.env` and fill in your API keys
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Initialize database:
   ```bash
   python models.py
   ```
4. Run the app:
   ```bash
   python app.py
   ```
5. Open http://localhost:5000

## Deploy to Render

1. Push this folder to a GitHub repository
2. Create a new Web Service on Render
3. Connect to your GitHub repo
4. Render will auto-detect the `render.yaml` configuration
5. Add environment variables in Render dashboard:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `R2_ACCOUNT_ID`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`
   - `R2_PUBLIC_URL`

## Project Structure

```
020 - SIGNMAKER/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── models.py           # Database models (SQLite/PostgreSQL)
├── svg_renderer.py     # Playwright SVG to PNG renderer
├── r2_storage.py       # Cloudflare R2 upload utilities
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
├── .env.example        # Environment variables template
└── assets/             # SVG templates and icons (to be added)
```

## Migration from Local Version

To migrate products from the local CSV-based version:

1. Export products from the old system
2. Use the `/api/products` POST endpoint to import each product
3. Upload SVG templates and icons to the `assets/` folder or R2

## Tech Stack

- **Backend**: Flask + Gunicorn
- **Database**: SQLite (local) / PostgreSQL (Render)
- **SVG Rendering**: Playwright (headless Chromium)
- **Image Storage**: Cloudflare R2
- **AI**: Anthropic Claude (content) + OpenAI (lifestyle images)
