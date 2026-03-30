# Insights tab — Amazon sales feedback loop with AI recommendations
Tags: insights sales feedback loop amazon csv claude recommendations categories
Date: 2026-03-30

## Feature

New "Insights" tab in the Render UI that closes the loop between what sells on Amazon
and what products to make next.

## Data sources analysed

- Amazon Business Report (Dec 1 2025 – Mar 29 2026): 495 rows, £138,488 total revenue
- Render products list: 1,029 products, only 57 appeared in the sales report (955 never got traffic yet)
- Render products = 1.5% of total revenue (£2,054) — very early stage

## Key findings from analysis

### Top render categories by CVR (conversion rate)
- No Smoking/Vaping: 58–200% CVR — best performer
- Customer Parking: 43–80% CVR
- No Dogs Allowed: 50–100% CVR
- No Entry/Access: 50% CVR
- No Cold Callers: 50% CVR

### Biggest gaps (legacy revenue not yet covered by render)
- Push/Pull Door Signs: £19,000+ revenue, 63–74% CVR — render has ZERO products in this category
- Personalised Memorial Plaques: £15,000+ revenue — only 2 render products
- Parcel Box Signs: £4,292 revenue — nothing in render
- Caution Hot Water signs: £2,447 — nothing in render

### Why 955 render products show zero sessions
Quartile advertising hasn't driven traffic to them yet, or products listed after report period.
Not a product quality issue.

## Implementation

### DB tables added (models.py)
- `sales_imports` — tracks each CSV upload (filename, report_start, report_end, row_count, imported_by)
- `sales_data` — individual product rows (asin, sku, title, sessions, units, revenue, cvr, buy_box_pct)
- Indexed on sku and asin for fast cross-referencing

### API endpoints (app.py)
- `POST /api/sales/import` — parses Amazon Business Report CSV, deduplicates by date range
- `GET /api/sales/performance` — aggregated totals, category breakdown, top 50 performers
- `POST /api/sales/recommend` — Claude Opus analyses top sellers and returns 12 structured recommendations
- `GET /api/sales/imports` — list all import batches

### Category inference (_infer_category)
Rule-based from title keywords covering:
Push/Pull Door Signs, No Smoking/Vaping, Parking, Memorial, Dogs/Pets,
Access/Restricted, Private Property, No Cold Callers, CCTV/Security,
Fire Safety, Photography/Filming, Bathroom/WC, Hazard/Warning, Delivery/Parcel

### Recommendation prompt
Claude Opus receives:
- Top 15 products by revenue with units, revenue, CVR
- Category breakdown (top 10 by revenue)
- Blank sizes available (dracula/saville/dick/barzan/baby_jesus)
Returns 12 structured recommendations: PRODUCT / SIZE / REASON

### Frontend
- Import form: date range pickers + file input → POST /api/sales/import
- Totals row: revenue, units, import count
- Category bar chart: horizontal bars scaled to max category revenue
- Top performers table: CVR colour-coded (green ≥40%, amber ≥15%)
- Recommendation cards: 12-up grid with blank size badge

## CSV parsing note
Amazon Business Report uses en-dash (–) in column headers e.g. "Sessions – Total".
Must use unicode \u2013 in Python dict key lookups, not ASCII hyphen.
