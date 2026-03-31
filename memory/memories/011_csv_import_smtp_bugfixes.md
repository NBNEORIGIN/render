# Bug fixes — CSV import broken, bug report emails failing (2026-03-31)
Tags: bugfix csv import smtp docker-compose regex quoted-fields
Date: 2026-03-31

## Bug 1: CSV product import importing 0 rows

### Symptom
Gabby reported "Signmaker Template csv file with barcodes and M numbers will not import/upload.
The system is trying to upload it but it gets stuck and doesn't complete."
Import status showed "Imported 0 products".

### Root cause
In `importCsvFile()` in templates/index.html, the line-split regex was:
```js
text.trim().split(/\\r?\\n/)
```
The double-escaped backslash `\\r` is a literal string `\r` not a regex escape,
so the regex never matched newlines and treated the entire file as one line.

### Fix
```js
text.trim().split(/\r?\n/)  // single backslash — correct regex
```

### Second issue: naive comma split
The original code used `lines[i].split(',')` which breaks on any field
containing a comma (e.g. descriptions like "Push, Pull Door Sign").

### Fix
Replaced with a proper quoted-field CSV parser `parseCsvLine()` that respects
double-quoted fields and escaped quotes (`""`), matching CSV spec.

Also added: skip blank lines, report skipped count, handle 409 (already exists) gracefully.

## Bug 2: Bug report emails failing

### Symptom
"Failed to send. Please email toby@nbnesigns.com directly."
Server log: `(501, b'5.5.2 Authentication failed: Client bug (User name required) [MSG0043]')`

### Root cause
`SMTP_USER` and `SMTP_PASSWORD` were in `/opt/nbne/render/.env` on the server
but were **not listed in docker-compose.yml environment block**.
Docker Compose only forwards env vars that are explicitly listed.
The container saw `None` for both.

### Fix
Added to docker-compose.yml app environment:
```yaml
SMTP_HOST: ${SMTP_HOST:-smtp.ionos.co.uk}
SMTP_PORT: ${SMTP_PORT:-587}
SMTP_USER: ${SMTP_USER}
SMTP_PASSWORD: ${SMTP_PASSWORD}
```

## Lessons
- Any env var needed inside the container MUST be listed in docker-compose.yml — being in .env alone is not enough.
- JS regex in template literals: `/\r?\n/` not `/\\r?\\n/` — the latter is a literal string match.
- Always use a proper CSV parser for user-uploaded files; naive comma-split breaks on quoted fields.
