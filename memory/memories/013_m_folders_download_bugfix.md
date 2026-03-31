# Bug fix — M Number folders ZIP "file not found" (2026-03-31)
Tags: bugfix export m-folders zip download stream tempdir path-mismatch
Date: 2026-03-31

## Symptom
Step 2b "Download M Number Folders (ZIP)" returned "file not found".

## Root cause
Two-step flow had a path mismatch:
1. `POST /api/export/m-folders` saved the ZIP to the **app directory**: `/app/m_number_folders_YYYYMMDD_HHMM.zip`
2. `GET /api/export/m-folders/download` looked for the file in **system tempdir**: `/tmp/`

These are different directories, so the download route never found the file.

## Fix
Removed the save-then-redirect pattern entirely.
`POST /api/export/m-folders` now streams the ZIP bytes directly as a blob response
using `send_file(BytesIO(zip_bytes), ...)` — the same pattern used by all other
export routes in app.py (single product ZIP, images ZIP, Etsy XLSX, eBay CSV).

The `/api/export/m-folders/download` route was also removed (no longer needed).

JS updated to receive the blob and trigger browser download via object URL:
```js
const blob = await resp.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `m_number_folders_${date}.zip`;
a.click();
URL.revokeObjectURL(url);
```

## Pattern
All file exports should stream directly via `send_file(BytesIO(...))`.
Never save to disk then redirect — the save path and download path will diverge,
especially inside Docker where the filesystem layout differs from the host.
