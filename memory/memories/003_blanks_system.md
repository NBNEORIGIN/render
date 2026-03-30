# Blanks system — database-driven, extensible
Tags: blanks database schema config seeds extensible
Date: 2026-03-30

## Decision

Replaced hardcoded `SIZES` dicts (spread across app.py, image_generator.py, content_generator.py)
with a DB-driven `blanks` table, seeded on first run from `config.BLANK_SEEDS`.

## Why

The original codebase had five hardcoded sign sizes in multiple files that had to be
kept in sync manually. The new system allows new blanks to be added without code changes.

## Blank fields

| Field | Type | Description |
|---|---|---|
| slug | TEXT | Unique ID (e.g. `dracula`, `baby_jesus`) |
| width_mm | INTEGER | Physical width |
| height_mm | INTEGER | Physical height |
| is_circular | BOOLEAN | Circle blanks get different rendering |
| display | TEXT | Human label (`"11 x 9.5 cm"`) |
| amazon_code | TEXT | Size tier (XS/S/M/L/XL) |
| sign_x/y/w/h | INTEGER | Print area bounds in pixels |
| peel_x/y/w/h | INTEGER | Peel-and-stick tab bounds (nullable) |
| has_portrait | BOOLEAN | Whether a portrait SVG template exists |

## Seed data flow

1. `config.BLANK_SEEDS` dict defines initial blanks with all fields
2. `models.init_db()` calls `_seed_blanks()` which inserts from `BLANK_SEEDS` if the table is empty
3. After first run, source of truth is the DB (edit via API or directly)

## Adding a new blank

1. Add to `config.BLANK_SEEDS` (for fresh installs / documentation)
2. POST to `/api/blanks` on the live server with the blank data, OR
3. Drop the blanks table and restart the container to re-seed
4. Add SVG templates: `assets/{color}_{slug}_landscape.svg`
   (and `_portrait.svg` if `has_portrait=True`)

## API

- `GET /api/blanks` — list all
- `GET /api/blanks/<slug>` — get one
- `POST /api/blanks` — create
- `PATCH /api/blanks/<slug>` — update

## Current blanks (2026-03-30)

| Slug | Size | Amazon code |
|---|---|---|
| dracula | 9.5 × 9.5 cm circular | XS |
| saville | 11 × 9.5 cm | S |
| dick | 14 × 9 cm (has portrait) | M |
| barzan | 19 × 14 cm | L |
| baby_jesus | 29 × 19 cm (has portrait, peel tab) | XL |
